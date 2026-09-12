"""Q4 joint routing, directional coverage, and reply-only homing.

The legacy radial half-plane coverage model is deliberately not used here.
All scheduled stations are actually measured once on every unheard channel.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import time
import numpy as np
from p3_arena import ArenaError
from p4_homing import P4HomingMixin, P4HomingConfig
from p4_robot import P4GridRobot
from p4_certificate import DirectionalCertificate, strict_layout


@dataclass
class P4SearchConfig(P4HomingConfig):
    tier: str = 'strict'
    search_rings: tuple = ((900.,6),(1900.,12))
    search_layout: str = 'certified'
    joint_route: bool = True
    after_clear_scan: bool = False
    scan_heard: bool = True
    route_polish: bool = True
    immediate_service: bool = False
    certify: bool = True
    certificate_step_m: float = 40.
    certificate_n_dir: int = 48
    prune_stations: bool = False
    endpoint_scan_min_saved: float = 0.0
    min_move: float = 0.
    opening_baseline_m: float = 0.
    jointly_scan_targets: bool = False


def tier_config(name='strict'):
    configs={
        'strict':dict(search_layout='certified',certify=True,prune_stations=False),
        'compact':dict(search_rings=((900.,6),(1900.,12))),
        'dense':dict(search_layout='legacy'),
        'fast99':dict(search_rings=((1000.,6),(1850.,9))),
        'fast98':dict(search_rings=((1000.,4),(1750.,8))),
        'fast95':dict(search_rings=((1100.,4),(1650.,8))),
        'fast90':dict(search_rings=((1450.,8),)),
        'inner':dict(search_rings=((1100.,6),)),
    }
    if name not in configs:raise ValueError(name)
    options=dict(search_layout='rings',certify=False,prune_stations=True)
    options.update(configs[name])
    return P4SearchConfig(tier=name,**options)


class P4SearchRobot(P4HomingMixin, P4GridRobot):
    def __init__(self,arena,cfg=None,base=None,log=None):
        super().__init__(arena,cfg or P4SearchConfig(),base=base,log=log)
        self._search_visits=0
        self.certificate=DirectionalCertificate(self.cfg.certificate_step_m,self.cfg.certificate_n_dir)
        self._station_bits=[np.packbits(self.certificate.station_mask(p)) for p in self.stations]
        self._covered_bits=np.packbits(self.certificate.empty())
        self._desired_bits=self._covered_bits.copy()
        self._desired_bits |= np.packbits(self.certificate.station_mask((0.,0.)))
        for bits in self._station_bits:self._desired_bits |= bits

    def _build_stations(self):
        if self.cfg.search_layout=='certified':return strict_layout()[1:]
        if self.cfg.search_layout=='legacy':return super()._build_stations()
        points=[]
        for k,(r,n) in enumerate(self.cfg.search_rings):
            offset=0. if k%2==0 else math.pi/n
            points.extend((r*math.cos(offset+2*math.pi*i/n),
                           r*math.sin(offset+2*math.pi*i/n)) for i in range(n))
        return points

    @staticmethod
    def _length(seq,start):
        return sum(math.dist(a,b['xy']) for a,b in zip([start]+[w['xy'] for w in seq],seq))

    def _ordered(self,items):
        if not items:return []
        pts=np.array([self.pos]+[w['xy'] for w in items]);d=np.linalg.norm(pts[:,None]-pts[None,:],axis=2)
        left=list(range(1,len(pts)));seq=[0]
        while left:
            k=min(left,key=lambda j:d[seq[-1],j]);seq.append(k);left.remove(k)
        if self.cfg.route_polish:
            for _ in range(8):
                changed=False
                for i in range(1,len(seq)-1):
                    for j in range(i+1,len(seq)):
                        delta=d[seq[i-1],seq[j]]-d[seq[i-1],seq[i]]
                        if j+1<len(seq):delta+=d[seq[i],seq[j+1]]-d[seq[j],seq[j+1]]
                        if delta < -1e-7:seq[i:j+1]=seq[i:j+1][::-1];changed=True
                if not changed:break
        return [items[i-1] for i in seq[1:]]

    def _route(self):
        scans=[dict(kind='station',si=i,xy=p) for i,p in enumerate(self.stations)
               if i not in self.visited_stations] if self.unheard() else []
        targets=[]
        for ch in self.heard_pending():
            c,_,_=self.estimate(ch)
            if c is not None:targets.append(dict(kind='clear',ch=ch,xy=tuple(c)))
        if self.cfg.jointly_scan_targets and scans:
            scans,targets=self._joint_duties(scans,targets)
        elif self.cfg.prune_stations and scans:
            scans=self._prune(scans,targets)
        if self.cfg.immediate_service and targets:
            return self._ordered(targets)
        if self.cfg.joint_route:return self._ordered(scans+targets)
        return self._ordered(scans) or self._ordered(targets)

    def _joint_duties(self,scans,targets):
        items=[dict(w) for w in scans+targets]
        for w in items:
            w['duty']=True
            w['bits']=self._station_bits[w['si']] if w['kind']=='station' else np.packbits(self.certificate.station_mask(w['xy']))
        route=self._ordered(items)
        costs={id(w):0. for w in items}
        for i,w in enumerate(route):
            if w['kind']!='station':continue
            a=self.pos if i==0 else route[i-1]['xy']
            savings=math.dist(a,w['xy'])
            if i+1<len(route):savings+=math.dist(w['xy'],route[i+1]['xy'])-math.dist(a,route[i+1]['xy'])
            costs[id(w)]=savings
        for w in sorted(items,key=lambda w:costs[id(w)],reverse=True):
            covered=self._covered_bits.copy()
            for v in items:
                if v is not w and v['duty']:covered |= v['bits']
            if not np.any(self._desired_bits & ~covered):w['duty']=False
        for w in items:del w['bits']
        return ([w for w in items if w['kind']=='station' and w['duty']],
                [w for w in items if w['kind']=='clear'])

    def _prune(self,scans,targets,covered=None):
        covered=self._covered_bits if covered is None else covered
        scans=list(scans)
        # Prefer deleting the stations with the largest travel/scan cost.
        route=self._ordered(scans+targets)
        score={}
        for i,w in enumerate(route):
            if w['kind']!='station':continue
            prev=self.pos if i==0 else route[i-1]['xy']
            saving=math.dist(prev,w['xy'])
            if i+1<len(route):saving+=math.dist(w['xy'],route[i+1]['xy'])-math.dist(prev,route[i+1]['xy'])
            score[w['si']]=saving
        for w in sorted(scans,key=lambda w:score.get(w['si'],0),reverse=True):
            all_bits=covered.copy()
            for v in scans:
                if v is not w:all_bits |= self._station_bits[v['si']]
            if not np.any(self._desired_bits & ~all_bits):scans.remove(w)
        return scans

    def _scan_actual(self,p,extra=True):
        channels=list(self.unheard())
        if self.cfg.scan_heard and extra:
            for ch in self.heard_pending():
                rec=self.recs[ch]
                if rec.n_bearings>1:continue
                if math.dist(rec.pts[-1],p)<80.:continue
                c,_,_=self.estimate(ch)
                if c is not None and math.dist(c,p)<=1450:channels.append(ch)
        self._last_scan_complete=True
        if channels:
            self.scan_points.append(tuple(p));n=self.scan_at(*p,channels)
            self.note_meas(self.pos)
            self._last_scan_complete=n==len(channels) and not self.aborted
            if self._last_scan_complete:
                self._covered_bits |= np.packbits(self.certificate.station_mask(p))
        return len(channels)

    def scan_at(self,x,y,chans,station=None):
        n=0
        for ch in chans:
            if self.aborted or not self.can_afford(math.dist(self.pos,(x,y))/5+12):break
            reply=self.measure(x,y,ch,station=station)
            if reply.get('accepted') is not True:break
            n+=1
            if reply.get('measure_result')=='near':self.do_clear(x,y,ch)
        return n

    def _certify_remaining(self):
        cert=DirectionalCertificate(20,48)
        cache={}
        for rec in self.recs.values():
            if rec.cleared:continue
            if rec.n_bearings or rec.near_hits:return False
            points=tuple(sorted(set(tuple(row[:2]) for row in rec.meas_log if row[3]=='no_signal')))
            if points not in cache:cache[points]=cert.continuous_complete(points)
            if not cache[points]:return False
        return True

    def _endpoint_worth_scan(self):
        if not self.cfg.endpoint_scan_min_saved:return True
        if not self.unheard():return False
        scans=[dict(kind='station',si=i,xy=p) for i,p in enumerate(self.stations)
               if i not in self.visited_stations]
        before=self._prune(scans,[])
        covered=self._covered_bits | np.packbits(self.certificate.station_mask(self.pos))
        after=self._prune(scans,[],covered)
        n_saved=len(before)-len(after)
        time_saved=(self._length(self._ordered(before),self.pos)-self._length(self._ordered(after),self.pos))/5
        time_saved+=(n_saved-1)*6*len(self.unheard())
        return time_saved>=self.cfg.endpoint_scan_min_saved

    def _opening_baseline(self):
        channels=self.heard_pending()
        if len(channels)<2 or self.cfg.opening_baseline_m<=0:return
        route=self._route()
        dest=np.array(route[0]['xy']) if route else np.zeros(2)
        best=None
        for a in np.arange(24)*2*math.pi/24:
            p=self.cfg.opening_baseline_m*np.array([math.cos(a),math.sin(a)])
            error=0.
            for ch in channels:
                c,_,_=self.estimate(ch);u=c/np.linalg.norm(c)
                v=c-p;cross=abs(float(u[0]*v[1]-u[1]*v[0]))
                error+=min(500.,math.radians(1.005)*np.linalg.norm(v)*np.linalg.norm(c)/max(cross,1.))
            cost=error+0.25*np.linalg.norm(dest-p)
            if best is None or cost<best[0]:best=(cost,p)
        self.scan_at(*best[1],channels)

    def run(self):
        t0=time.perf_counter()
        reply=self.arena.enter()
        if reply.get('accepted') is not True:raise ArenaError(str(reply))
        complete=False
        try:
            self._scan_actual(self.pos,extra=False)
            self._opening_baseline()
            for _ in range(400):
                if self.aborted or not self.can_afford(15):break
                route=self._route()
                if not route:break
                w=route[0]
                if w['kind']=='station':
                    self._scan_actual(w['xy'])
                    if self._last_scan_complete:
                        self.visited_stations.add(w['si']);self._search_visits+=1
                    else:break
                else:
                    ch=w['ch']
                    before=(self.stats['n_measure'],self.stats['n_clear'])
                    self.clear_here(ch)
                    if self.recs[ch].cleared and (w.get('duty') or (self.cfg.after_clear_scan and self._endpoint_worth_scan())):
                        self._scan_actual(self.pos)
                    if before==(self.stats['n_measure'],self.stats['n_clear']):break
            self.stats['search_stations']=self._search_visits
            if self.cfg.certify:complete=self._certify_remaining()
        finally:
            self.arena.exit()
        self.stats['program_runtime_s']=time.perf_counter()-t0
        rep=self.report();rep['search_stations']=self._search_visits
        mask=np.unpackbits(self._covered_bits,count=int(np.prod(self.certificate.shape))).reshape(self.certificate.shape).astype(bool)
        rep['completion_certified']=bool(self.certificate.summarize(mask).complete and not self.heard_pending())
        if self.cfg.certify:
            rep['completion_certified']=complete
        rep['policy']=self.cfg.tier
        rep['last_clear_time_s']=self.stats['vtime_at_last_clear']
        rep['termination']='certified_complete' if complete else ('budget_or_incomplete' if self.cfg.certify else 'configured_search_complete')
        return rep
