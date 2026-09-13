"""Explore route-aware local service without changing completion evidence."""
from dataclasses import dataclass
import math
import numpy as np
from p4_search import P4SearchRobot,P4SearchConfig


@dataclass
class P4ServiceConfig(P4SearchConfig):
    tier: str = 'service'
    direct_single: bool = True
    direct_fraction: float = 1.
    direct_lateral: float = 0.
    single_estimate_fraction: float = 0.5
    route_center_cross: bool = False


class P4ServiceMixin:
    def estimate(self,ch):
        c,r,br=super().estimate(ch)
        rec=self.recs[ch]
        fraction=getattr(self.cfg,'single_estimate_fraction',.5)
        if c is not None and rec.n_bearings==1 and fraction!=.5:
            s=np.array(rec.pts[-1]);angle=math.radians(rec.svds[-1])
            u=np.array([math.cos(angle),math.sin(angle)])
            t=(np.array(br['poly'])-s)@u
            c=s+u*(t.min()+fraction*(t.max()-t.min()))
        return c,r,br

    def clear_here(self,ch):
        rec=self.recs[ch]
        if rec.n_bearings==1 and not rec.cleared and getattr(self.cfg,'direct_single',True):
            c,_,br=self.estimate(ch)
            if c is not None:
                s=np.array(rec.pts[-1]);p=s+self.cfg.direct_fraction*(c-s)
                u=c-s;u=u/max(np.linalg.norm(u),1e-9);normal=np.array([-u[1],u[0]])
                lat=getattr(self.cfg,'direct_lateral',0.)
                opts=[p+lat*normal,p-lat*normal]
                p=min(opts,key=lambda q:math.dist(q,self.pos))
                if lat==0 and self._home_clear(ch,p):return True
                result=self._home_measure(ch,p)
                if rec.cleared:return True
        return super().clear_here(ch)


class P4ServiceRobot(P4ServiceMixin,P4SearchRobot):
    def __init__(self,arena,cfg=None,**kwargs):
        super().__init__(arena,cfg or P4ServiceConfig(),**kwargs)
