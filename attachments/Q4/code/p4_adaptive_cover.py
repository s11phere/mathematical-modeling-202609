"""Joint coverage/clearance planning with witness refinement and full proof.

A sparse witness subset ranks candidates cheaply. Every proposed route is
then repaired against the complete 20 m x 48 orientation certificate. Only
actual negative replies establish the final absence certificate.
"""
from dataclasses import dataclass
import math
import numpy as np
from p4_search import P4SearchConfig,P4SearchRobot
from p4_certificate import DirectionalCertificate


@dataclass
class P4AdaptiveConfig(P4SearchConfig):
    tier: str = 'adaptive'
    certificate_step_m: float = 20.
    certificate_n_dir: int = 48
    free_radii: tuple = (800.,1000.,1200.,1400.,1650.,1875.,1950.)
    free_angles: int = 24
    gain_power: float = 1.0
    scan_cost_weight: float = 1.0
    use_target_scans: bool = True
    witness_stride: int = 6
    refine_passes: int = 2


class P4AdaptiveRobot(P4SearchRobot):
    def __init__(self,arena,cfg=None,**kwargs):
        super().__init__(arena,cfg or P4AdaptiveConfig(),**kwargs)
        anchors=list(self.stations)
        for r in self.cfg.free_radii:
            for a in np.arange(self.cfg.free_angles)*2*math.pi/self.cfg.free_angles:
                p=(float(r*math.cos(a)),float(r*math.sin(a)))
                if all(math.dist(p,q)>1 for q in self.stations):self.stations.append(p)
        self._fine_cache={tuple(p):bits for p,bits in zip(anchors,self._station_bits)}
        self.witness=DirectionalCertificate(20,self.cfg.certificate_n_dir)
        ij=np.rint((self.witness.centers+1790)/20).astype(int)
        keep=np.all(ij%self.cfg.witness_stride==0,axis=1)
        self.witness.centers=self.witness.centers[keep]
        self._witness_bits=np.array([np.packbits(self.witness.station_mask(p)) for p in self.stations])
        self._witness_actual=np.zeros(self._witness_bits.shape[1],np.uint8)
        self._witness_desired=np.packbits(np.ones(self.witness.shape,bool))
        self._actual_points=[]

    def _fine(self,p):
        key=tuple(p)
        if key not in self._fine_cache:
            self._fine_cache[key]=np.packbits(self.certificate.station_mask(p,cache=False))
        return self._fine_cache[key]

    def _scan_actual(self,p,extra=True):
        n=super()._scan_actual(p,extra)
        if self._last_scan_complete and n:
            self._witness_actual |= np.packbits(self.witness.station_mask(p))
            self._actual_points.append(tuple(p))
        return n

    def _insertion_costs(self,pts,seq):
        prev=np.array([self.pos]+[w['xy'] for w in seq])
        distances=np.linalg.norm(pts[:,None]-prev[None,:],axis=2)
        cost=distances.copy()
        if seq:cost[:,:-1]+=distances[:,1:]-np.linalg.norm(np.diff(prev,axis=0),axis=1)
        inds=np.argmin(cost,axis=1)
        return cost[np.arange(len(pts)),inds],inds

    def _select(self,items,masks,missing,targets,available,initial=None):
        seq=self._ordered([dict(w) for w in targets]) if initial is None else initial
        pts=np.array([w['xy'] for w in items])
        scan_cost=5*6*len(self.unheard())*self.cfg.scan_cost_weight
        selected=[]
        for _ in range(60):
            if not np.any(missing):break
            gain=np.bitwise_count(masks & missing).sum(axis=1).astype(float)
            cost,place=self._insertion_costs(pts,seq)
            for i,w in enumerate(items):
                if w['kind']=='clear':cost[i]=0.
            score=gain**self.cfg.gain_power/(np.maximum(cost,0)+scan_cost+100.)
            score[~available]=-1.
            j=int(np.argmax(score))
            if not available[j] or gain[j]<=0:break
            available[j]=False;selected.append(j);missing &= ~masks[j]
            w=dict(items[j],duty=True)
            if w['kind']=='station':seq.insert(int(place[j]),w)
            else:
                next(v for v in seq if v.get('ch')==w['ch'])['duty']=True
        return seq,selected,missing

    def _route(self):
        targets=[]
        for ch in self.heard_pending():
            c,_,_=self.estimate(ch)
            if c is not None:targets.append(dict(kind='clear',ch=ch,xy=tuple(c),duty=False))
        if not self.unheard():return self._ordered(targets)
        items=[dict(kind='station',si=i,xy=p) for i,p in enumerate(self.stations)]
        masks=self._witness_bits
        if self.cfg.use_target_scans and targets:
            items+=targets
            masks=np.concatenate([masks,np.array([np.packbits(self.witness.station_mask(w['xy'])) for w in targets])])
        available=np.ones(len(items),bool)
        for i in self.visited_stations:available[i]=False
        missing=self._witness_desired & ~self._witness_actual
        seq,chosen,missing=self._select(items,masks,missing.copy(),targets,available)
        # Refine the sparse witness plan using all states. This is the actual
        # safety constraint, including boundary cells and interval margins.
        covered=self._covered_bits.copy()
        for j in chosen:covered |= self._fine(items[j]['xy'])
        full=np.packbits(np.ones(self.certificate.shape,bool))
        missing=full & ~covered
        if np.any(missing):
            active_bytes=np.flatnonzero(missing)
            fine_masks=np.array([self._fine(w['xy'])[active_bytes] for w in items])
            seq,extra,left=self._select(items,fine_masks,missing[active_bytes].copy(),targets,available,seq)
            chosen+=extra
            if np.any(left):raise RuntimeError('Candidate union cannot certify the proposed route')
        # Remove redundant duties, favouring stations with costly detours.
        seq=self._ordered(seq)
        selected=[w for w in seq if w.get('duty')]
        costs={id(w):0. for w in selected}
        for i,w in enumerate(seq):
            if w['kind']!='station':continue
            a=self.pos if i==0 else seq[i-1]['xy']
            costs[id(w)]=math.dist(a,w['xy'])
            if i+1<len(seq):costs[id(w)]+=math.dist(w['xy'],seq[i+1]['xy'])-math.dist(a,seq[i+1]['xy'])
        for w in sorted(selected,key=lambda w:costs[id(w)],reverse=True):
            other=self._covered_bits.copy()
            for v in selected:
                if v is not w and v.get('duty'):other |= self._fine(v['xy'])
            if not np.any(full & ~other):w['duty']=False
        return self._ordered([w for w in seq if w['kind']=='clear' or w.get('duty')])
