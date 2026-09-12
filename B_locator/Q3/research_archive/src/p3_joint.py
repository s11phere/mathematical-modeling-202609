"""Q3 joint routing and scan scheduling with continuous coverage certificates.

Only actual replies enter decisions. Probability gates affect optional bearing
measurements, never mandatory clearance or the deterministic completion proof.
"""
from dataclasses import dataclass
import math
import numpy as np
from p3_adaptive import AdaptiveRobot,AdaptiveConfig


@dataclass
class JointConfig(AdaptiveConfig):
    after_service_scan: str = 'duty'
    reachable_filter: bool = True
    polish_small_routes: bool = True
    candidate_radii: tuple = (1050.,1200.,1350.,1500.)
    speculative_radius_m: float = 400.0
    cover_polish: bool = True
    planner_multistart: bool = True
    opportunistic_receive_probability: float = 0.5
    continuous_cover: bool = True
    probe_fail_measure: bool = True
    min_move: float = 0.0


class JointRobot(AdaptiveRobot):
    def __init__(self,arena,cfg=None,base=None,log=None):
        super().__init__(arena,cfg or JointConfig(),base=base,log=log)


    def clear_target(self,ch,rec):
        if self.cfg.speculative_radius_m and rec.n_bearings>=2 and not rec.cleared:
            br=self.region_info(rec)
            if br and br['radius'] <= self.cfg.speculative_radius_m:
                cost=math.dist(self.pos,br['center'])/5+15
                if self.can_afford(cost):
                    if self.do_clear(*br['center'],ch):
                        return True
                    if self.cfg.probe_fail_measure and self.can_afford(8):
                        resp=self.measure(*self.pos,ch)
                        if resp.get('measure_result')=='near':
                            return self.do_clear(*self.pos,ch)
        return super().clear_target(ch,rec)


    def nn_2opt(self,seq):
        if self.cfg.polish_small_routes and len(seq)<4:
            from itertools import permutations
            return list(min(permutations(seq),key=self._route_length)) if seq else []
        return super().nn_2opt(seq)


    def assemble_route(self,dir_sign,targets=None,cursor=None):
        if self.cfg.planner_multistart:
            from dataclasses import replace
            cfg=self.cfg
            proposals=[]
            try:
                for power,weight in ((1.,.3),(1.,1.),(2.,.3),(2.,1.),(3.,.3)):
                    self.cfg=replace(cfg,planner_multistart=False,gain_power=power,scan_cost_weight=weight)
                    seq,length=self.assemble_route(dir_sign,targets=targets,cursor=cursor)
                    proposals.append((self._plan_cost(seq),seq,length))
            finally:
                self.cfg=cfg
            _cost,seq,length=min(proposals,key=lambda q:q[0])
            return seq,length
        seq,length=super().assemble_route(dir_sign,targets=targets,cursor=cursor)
        if not self.cfg.cover_polish or not seq:
            return seq,length
        pts,covers=self._candidate_cover()
        gx,gy,needed=self.uncovered_mask()
        if not needed.any():
            return seq,length
        r2=self.cfg.cover_radius_m**2
        for _ in range(3):
            changed=False
            for w in list(seq):
                if not w.get('cover_duty'):
                    continue
                others=np.zeros(len(gx),bool)
                for v in seq:
                    if v is not w and v.get('cover_duty'):
                        x,y=v['xy'];others |= (gx-x)**2+(gy-y)**2<=r2
                must=needed&~others
                if not must.any():
                    if w['kind']=='cover':
                        seq.remove(w)
                    else:
                        w['cover_duty']=False
                    changed=True
                    continue
                if w['kind']!='cover':
                    continue
                allowed=np.all(covers[:,must],axis=1)
                if not allowed.any():
                    continue
                reduced=[v for v in seq if v is not w]
                costs,places=self._insert_cost(pts,reduced)
                costs[~allowed]=np.inf
                j=int(np.argmin(costs))
                old_cost=self._route_length(seq)-self._route_length(reduced)
                if costs[j] < old_cost-1e-5:
                    w['xy']=tuple(pts[j]);reduced.insert(int(places[j]),w)
                    seq=reduced;changed=True
                if self.cfg.continuous_cover:
                    reduced=[v for v in seq if v is not w]
                    start=np.asarray(w['xy'],float)
                    Q=np.column_stack([gx[must],gy[must]])
                    delta=start-Q
                    c=np.einsum('ij,ij->i',delta,delta)-r2
                    if c.max(initial=-np.inf)>1e-5:
                        continue
                    chain=np.array([self.pos]+[v['xy'] for v in reduced])
                    destinations=[chain[-1]]
                    for a,b in zip(chain,chain[1:]):
                        v=b-a;den=v@v
                        t=float(np.clip((start-a)@v/max(den,1e-12),0,1))
                        destinations.append(a+t*v)
                    candidates=[]
                    for z in destinations:
                        v=z-start;aa=float(v@v)
                        if aa<1e-10:continue
                        bb=2*delta@v
                        roots=(-bb+np.sqrt(np.maximum(0,bb*bb-4*aa*c)))/(2*aa)
                        t=max(0.,min(1.,float(roots.min()))-1e-8)
                        candidates.append(start+t*v)
                    if candidates:
                        P=np.asarray(candidates)
                        costs,places=self._insert_cost(P,reduced)
                        j=int(np.argmin(costs))
                        old_cost=self._route_length(seq)-self._route_length(reduced)
                        if costs[j]<old_cost-1e-5:
                            w['xy']=tuple(P[j]);reduced.insert(int(places[j]),w)
                            seq=reduced;changed=True
            seq=self.nn_2opt(seq)
            if not changed:
                break
        return seq,self._route_length(seq)

    def _plan_cost(self,seq):
        gx,gy=self.annulus_grid();r2=self.cfg.cover_radius_m**2
        pending={ch:self.unsafe_of(ch).copy() for ch in self.unheard()}
        scans=0
        for w in seq:
            if not w.get('cover_duty'):
                continue
            x,y=w['xy'];mask=(gx-x)**2+(gy-y)**2<=r2
            for ch,m in pending.items():
                if np.any(m&mask):
                    scans+=1;pending[ch]=m&~mask
        return self._route_length(seq)/5+6*scans

    def _cross_ok(self,rec,x,y):
        if self.cfg.opportunistic_receive_probability>0 and rec.n_bearings==1:
            s=np.array(rec.pts[0]);a=math.radians(rec.svds[0])
            t=np.linspace(5.,1500.,151);u=np.array([math.cos(a),math.sin(a)])
            p=s+t[:,None]*u
            lo=np.maximum(1000.,t);hi=np.full(len(t),1500.)
            for qx,qy,_t,res in rec.meas_log:
                if res=='no_signal':hi=np.minimum(hi,np.linalg.norm(p-(qx,qy),axis=1))
            density=t*(np.linalg.norm(p,axis=1)<=1800.)
            total=np.sum(density*np.maximum(0.,hi-lo))
            heard=np.sum(density*np.maximum(0.,hi-np.maximum(lo,np.linalg.norm(p-(x,y),axis=1))))
            if total>0 and heard/total < self.cfg.opportunistic_receive_probability:
                return False
        if self.cfg.reachable_filter and rec.n_bearings==1:
            br=self.region_info(rec)
            if br:
                poly=br['poly']
                from p3_robot import _dist_point_polygon
                if poly and _dist_point_polygon(np.array([x,y]),np.array(poly))>1500.:
                    return False
        return super()._cross_ok(rec,x,y)

    def visit(self,wp):
        ch=wp.get('ch')
        if ch is None or self.cfg.after_service_scan=='off':
            return super().visit(wp)
        rec=self.recs[ch]
        before=self.stats['n_measure']
        self.clear_target(ch,rec)
        # The route's target was an estimate; perform its scan at the actual
        # endpoint after localization, then replan using that measured position.
        wp['xy']=tuple(self.pos)
        chans=[]
        duty=wp.get('cover_duty') or self.cfg.after_service_scan=='all'
        if self.cfg.after_service_scan=='replan':
            here=dict(kind='scan_here',ch=None,xy=tuple(self.pos),r=None)
            route,_=self.assemble_route(1.,targets=[here]+self.target_waypoints())
            duty=any(w['kind']=='scan_here' and w.get('cover_duty') for w in route)
        for k in self.pending():
            r=self.recs[k]
            if not r.n_bearings and duty and self.adds_coverage(k,*self.pos):
                chans.append(k)
            elif r.n_bearings==1 and self._cross_ok(r,*self.pos):
                chans.append(k)
        if chans:
            self.scan_at(*self.pos,chans)
        self.note_pos()
        # The inherited loop also accepts a successful clear as progress.
        return max(1,self.stats['n_measure']-before)
