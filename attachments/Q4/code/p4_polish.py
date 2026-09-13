"""Move scan stops inside their exact assigned coverage constraints."""
from dataclasses import dataclass
import math
import numpy as np
from p4_search import P4SearchRobot,P4SearchConfig


@dataclass
class P4PolishConfig(P4SearchConfig):
    tier: str = 'polish'
    certificate_step_m: float = 20.
    certificate_n_dir: int = 48
    polish_target_duties: bool = True
    polish_rounds: int = 2
    polish_move: bool = True


class P4PolishRobot(P4SearchRobot):
    def __init__(self,arena,cfg=None,**kwargs):
        super().__init__(arena,cfg or P4PolishConfig(),**kwargs)
        self._full=np.packbits(np.ones(self.certificate.shape,bool))

    def _bits(self,w):
        if w['kind']=='station':return self._station_bits[w['si']]
        return np.packbits(self.certificate.station_mask(w['xy']))

    def _slide(self,start,z,missing):
        cert=self.certificate
        mask=np.unpackbits(missing,count=int(np.prod(cert.shape))).reshape(cert.shape)
        ci,ai=np.nonzero(mask)
        if not len(ci):return z
        centers=cert.centers[ci];theta=cert.angles[ai]
        delta=np.array(start)-centers;v=z-start;aa=float(v@v)
        if aa<1e-9:return start
        bb=2*delta@v;cc=np.einsum('ij,ij->i',delta,delta)-(1000-cert.rho)**2
        roots=(-bb+np.sqrt(np.maximum(0,bb*bb-4*aa*cc)))/(2*aa)
        t=float(min(1.,roots.min()))
        for side in [-1,1]:
            angles=theta+side*cert.angle_half_width
            normals=np.column_stack([np.cos(angles),np.sin(angles)])
            slack=np.einsum('ij,ij->i',delta,normals)-cert.rho
            change=normals@v;bad=change<0
            if np.any(bad):t=min(t,float(np.min(slack[bad]/-change[bad])))
        return start+max(0.,t-1e-6)*v

    def _route(self):
        targets=[]
        for ch in self.heard_pending():
            c,_,_=self.estimate(ch)
            if c is not None:targets.append(dict(kind='clear',ch=ch,xy=tuple(c),duty=self.cfg.polish_target_duties))
        if not self.unheard():return self._ordered(targets)
        scans=[dict(kind='station',si=i,xy=p,duty=True) for i,p in enumerate(self.stations) if i not in self.visited_stations]
        seq=self._ordered(scans+targets)
        for _ in range(self.cfg.polish_rounds):
            for w in list(seq):
                if not w.get('duty'):continue
                covered=self._covered_bits.copy()
                for v in seq:
                    if v is not w and v.get('duty'):covered |= self._bits(v)
                must=self._full & ~covered
                if not np.any(must):
                    if w['kind']=='station':seq.remove(w)
                    else:w['duty']=False
                    continue
                if not self.cfg.polish_move or w['kind']!='station':continue
                # A target may shift after service, so only commit movement
                # now; every following plan checks the actual measured mask.
                if np.any(must & ~self._bits(w)):continue
                i=seq.index(w);a=np.array(self.pos if i==0 else seq[i-1]['xy']);start=np.array(w['xy'])
                ends=[a]
                if i+1<len(seq):
                    b=np.array(seq[i+1]['xy']);v=b-a
                    t=np.clip((start-a)@v/max(float(v@v),1e-8),0,1)
                    ends=[a+t*v,a,b,(a+b)/2]
                    def cost(p):return np.linalg.norm(p-a)+np.linalg.norm(p-b)
                else:
                    def cost(p):return np.linalg.norm(p-a)
                opts=[self._slide(start,z,must) for z in ends]
                p=min(opts,key=cost)
                if cost(p)<cost(start)-.01:
                    bits=np.packbits(self.certificate.station_mask(p))
                    if not np.any(must & ~bits):
                        w['xy']=tuple(p)
                        self.stations[w['si']]=tuple(p);self._station_bits[w['si']]=bits
            seq=self._ordered(seq)
        covered=self._covered_bits.copy()
        for w in seq:
            if w.get('duty'):covered |= self._bits(w)
        if np.any(self._full & ~covered):
            # Target coordinates change after localization: restore the
            # original certified anchor set, preserving all actual evidence.
            from p4_certificate import strict_layout
            for p in strict_layout()[1:]:
                if p not in self.stations:
                    i=len(self.stations);self.stations.append(p)
                    bits=np.packbits(self.certificate.station_mask(p));self._station_bits.append(bits)
                    seq.append(dict(kind='station',si=i,xy=p,duty=True));covered |= bits
            if np.any(self._full & ~covered):raise RuntimeError('Coverage repair failed')
            seq=self._ordered(seq)
        return seq
