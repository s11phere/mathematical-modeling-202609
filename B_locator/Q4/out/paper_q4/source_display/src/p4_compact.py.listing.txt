"""Compact directional survey with adaptively refined continuous proof."""
from dataclasses import dataclass, asdict
import math
import numpy as np
from p4_search import P4SearchRobot,P4SearchConfig,tier_config
from p4_certificate import ring_layout
from p4_layout_v2 import adaptive_complete
from p4_route_v2 import P4RouteV2Mixin
from p4_posterior import P4PosteriorMixin


@dataclass
class P4CompactConfig(P4SearchConfig):
    tier: str = 'strict'
    compact_rings: tuple = ((998.,8,0.),(1867.,12,15.))
    stronger_route: bool = True
    route_service_entry: bool = False
    route_v2_rounds: int = 4
    route_v2_starts: int = 5
    route_information: bool = True
    extra_bearings: bool = False
    opportunistic_baseline_m: float = 300.
    defer_single: bool = False
    defer_distance_m: float = 1100.
    defer_angle_deg: float = 70.
    posterior_estimate: bool = True
    posterior_omni_prior: float = .5
    rotate_layout: bool = False
    rotation_candidates: int = 14


class P4CompactRobot(P4PosteriorMixin,P4RouteV2Mixin,P4SearchRobot):
    def __init__(self,arena,cfg=None,**kwargs):
        cfg=cfg or P4CompactConfig()
        if cfg.certify and not adaptive_complete(ring_layout(cfg.compact_rings)):
            raise ValueError('Compact layout lacks a continuous certificate')
        super().__init__(arena,cfg,**kwargs)

    def _build_stations(self):
        return ring_layout(self.cfg.compact_rings,False)

    def _opening_baseline(self):
        if self.cfg.rotate_layout and self.heard_pending():
            base=np.array(self.stations)
            targets=[dict(kind='clear',ch=ch,xy=tuple(self.estimate(ch)[0])) for ch in self.heard_pending()]
            best=None
            # The certified arena is a disk, so a rigid rotation preserves
            # its geometric validity. Pick phase using observed targets only.
            symmetry=math.gcd(*(int(n) for _,n,_ in self.cfg.compact_rings))
            for phi in np.arange(self.cfg.rotation_candidates)*2*math.pi/(symmetry*self.cfg.rotation_candidates):
                mat=np.array([[math.cos(phi),-math.sin(phi)],[math.sin(phi),math.cos(phi)]])
                pts=base@mat.T
                items=[dict(kind='station',si=i,xy=tuple(p)) for i,p in enumerate(pts)]+targets
                self._route_v2_previous=[]
                seq=self._ordered(items)
                cost=self._length(seq,self.pos)
                if best is None or cost<best[0]:best=(cost,pts)
            self.stations=[tuple(p) for p in best[1]]
            self._station_bits=[np.packbits(self.certificate.station_mask(p)) for p in self.stations]
            self._route_v2_previous=[]
        return super()._opening_baseline()

    def _ordered(self,items):
        if self.cfg.stronger_route:return P4RouteV2Mixin._ordered(self,items)
        return P4SearchRobot._ordered(self,items)

    def _route(self):
        seq=super()._route()
        if not self.cfg.defer_single:return seq
        scans=[w for w in seq if w['kind']=='station']
        if not scans:return seq
        keep=[]
        for w in seq:
            if w['kind']!='clear' or self.recs[w['ch']].n_bearings!=1:
                keep.append(w);continue
            rec=self.recs[w['ch']];c=np.array(w['xy']);old=np.array(rec.pts[-1])-c
            can_defer=False
            for scan in scans:
                q=np.array(scan['xy']);v=q-c;dist=np.linalg.norm(v)
                if dist>self.cfg.defer_distance_m or math.dist(q,rec.pts[-1])<300:continue
                angle=math.degrees(math.acos(float(np.clip((old@v)/max(1e-9,np.linalg.norm(old)*dist),-1,1))))
                if angle<=self.cfg.defer_angle_deg:can_defer=True;break
            if not can_defer:keep.append(w)
        return self._ordered(keep)

    def _certify_remaining(self):
        cache={}
        for rec in self.recs.values():
            if rec.cleared:continue
            if rec.n_bearings or rec.near_hits:return False
            points=tuple(sorted(set(tuple(row[:2]) for row in rec.meas_log if row[3]=='no_signal')))
            if points not in cache:cache[points]=adaptive_complete(points)
            if not cache[points]:return False
        return True

    def _scan_actual(self,p,extra=True):
        n=super()._scan_actual(p,extra)
        if self.cfg.extra_bearings and extra:
            for ch in self.heard_pending():
                rec=self.recs[ch]
                if rec.n_bearings<2:continue
                c,rad,_=self.estimate(ch)
                if rad<20 or c is None or math.dist(c,p)>1000:continue
                if math.dist(rec.pts[-1],p)<self.cfg.opportunistic_baseline_m:continue
                self.scan_at(*p,[ch])
        return n


def compact_config(tier='strict'):
    """Second-round presets; fast tier labels are empirical targets only."""
    base=tier_config(tier)
    options=asdict(base)
    options.update(stronger_route=True,posterior_estimate=True,route_information=True)
    if tier=='strict':
        options['compact_rings']=((998.,8,0.),(1867.,12,15.))
    else:
        options['compact_rings']=tuple((r,n,0. if k%2==0 else 180./n)
                                       for k,(r,n) in enumerate(base.search_rings))
    return P4CompactConfig(**options)
