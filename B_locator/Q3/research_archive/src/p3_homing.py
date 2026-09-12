"""Experimental Q3 homing: plan through source estimates, localize on the way.

All decisions use measurement replies only. Ground truth is read by inherited
reporting after /exit, as in TourRobot.
"""
from dataclasses import dataclass
import math
import numpy as np

from p1_intersection import clip_halfplane, wedge_halfplanes, min_enclosing_circle
from p3_arena import R_ARENA, R_RECV_MAX, R_CLEAR
from p3_tour import TourConfig, TourRobot


@dataclass
class HomingConfig(TourConfig):
    initial_rounds: int = 0
    offroute_clear: bool = False
    route_mode: str = 'tsp'
    homing_lateral_m: float = 100.0
    homing_fraction: float = 0.55
    homing_all_single: bool = True
    homing_negatives: bool = True
    homing_max_steps: int = 12


class HomingRobot(TourRobot):
    def __init__(self, arena, cfg=None, base=None, log=None):
        super().__init__(arena, cfg or HomingConfig(), base=base, log=log)
        self._home_regions = {}

    def region(self, rec):
        br = self.region_info(rec)
        if br is None:
            return {'status':'none', 'n_bearings':rec.n_bearings}
        return dict(status='bounded', min_enclosing_center=br['center'],
                    min_enclosing_radius_m=br['radius'], vertices=br['poly'] or [])

    def region_info(self, rec):
        if rec.near_hits:
            x,y,_t,_res = next(row for row in reversed(rec.meas_log) if row[3]=='near')
            return dict(center=(x,y),radius=5.0,poly=None,status='bounded',n_bearings=rec.n_bearings)
        if not rec.pts:
            return None
        key = (rec.channel, len(rec.pts), len(rec.meas_pts))
        if key in self._home_regions:
            return self._home_regions[key]
        P = [np.array(p, float) for p in [(-1800,-1800),(1800,-1800),(1800,1800),(-1800,1800)]]
        # Tangent half planes circumscribe disks, so rounding never excludes truth.
        for S, radius in [(np.zeros(2), R_ARENA)] + [(np.array(s), R_RECV_MAX) for s in rec.pts]:
            for a in np.arange(0, 2*math.pi, math.pi/16):
                u = np.array([math.cos(a), math.sin(a)])
                P = clip_halfplane(P, u, -float(u @ S) - radius)
        for S, theta in zip(rec.pts, rec.svds):
            for a, b in wedge_halfplanes(S, theta, 1.005 + 1e-9):
                P = clip_halfplane(P, a, b)
        if not P:
            return None
        arr = np.array(P)
        origin = arr.mean(axis=0)
        circle = min_enclosing_circle(arr-origin)
        center, radius = circle if circle is not None else (np.zeros(2), np.inf)
        center = center + origin
        c = np.asarray(center, float)
        # Negative replies exclude the 1000m disk. Use them only to improve an
        # estimate, never to certify completion or shrink the outer polygon.
        if rec.n_bearings == 1 and self.cfg.homing_negatives:
            S = np.array(rec.pts[0]); a = math.radians(rec.svds[0])
            u = np.array([math.cos(a), math.sin(a)])
            t = np.linspace(5, 1500, 301)
            G = S + t[:,None]*u
            keep = np.linalg.norm(G,axis=1) <= 1800
            for x,y,_time,res in rec.meas_log:
                if res == 'no_signal':
                    keep &= np.linalg.norm(G - (x,y),axis=1) >= 1000
            if keep.any():
                c = np.average(G[keep], axis=0, weights=t[keep])
        radius = float(np.max(np.linalg.norm(arr-c,axis=1)))
        out = dict(center=tuple(c), radius=radius, poly=arr.tolist(),
                   status='bounded', n_bearings=rec.n_bearings)
        self._home_regions[key] = out
        return out

    def target_waypoints(self):
        if not self.cfg.homing_all_single:
            return super().target_waypoints()
        return [dict(kind='clear', ch=ch, xy=self._safe_point(br['center']),
                     r=br['radius'], n_bearings=self.recs[ch].n_bearings)
                for ch in self.heard_pending() if not self.on_hold(ch)
                if (br := self.region_info(self.recs[ch])) is not None]

    def _home_step(self, ch):
        rec = self.recs[ch]
        br = self.region_info(rec)
        if br is None:
            return self.pos
        c = np.array(br['center']); cur = np.array(self.pos)
        delta = c-cur; d = float(np.linalg.norm(delta))
        if rec.n_bearings == 1:
            a = math.radians(rec.svds[-1]); u = np.array([math.cos(a),math.sin(a)])
            normal = np.array([-u[1],u[0]])
            ahead = cur + self.cfg.homing_fraction*delta
            lat = min(self.cfg.homing_lateral_m, max(35., 0.25*d))
            opts = [self._safe_point(ahead + sign*lat*normal) for sign in [-1,1]]
            return min(opts,key=lambda p:math.dist(p,c)+math.dist(p,cur))
        if d > 25:
            return self._safe_point(c)
        a = math.radians(rec.svds[-1]); normal = np.array([-math.sin(a),math.cos(a)])
        lat = min(80., max(25., br['radius']*0.3))
        return self._safe_point(cur + lat*normal)

    def visit(self, wp):
        ch = wp.get('ch')
        if ch is not None and self.recs[ch].n_bearings == 1:
            p = self._home_step(ch)
            wp['xy'] = p
            chans = [ch] + [k for k in self.heard_pending() if k != ch
                           and self.recs[k].n_bearings == 1 and self._cross_ok(self.recs[k],*p)]
            n = self.scan_at(*p, chans)
            self.note_pos()
            return n
        return super().visit(wp)

    def mark_served(self, x, y):
        # The actual channel observations, not proximity, certify coverage.
        pass

    def clear_target(self, ch, rec):
        for _ in range(self.cfg.homing_max_steps):
            if rec.cleared or self.aborted or not self.can_afford(15):
                break
            br = self.region_info(rec)
            if br is None:
                break
            c, radius = br['center'], br['radius']
            if radius <= R_CLEAR or (rec.n_bearings >= 2 and radius < 65 and math.dist(self.pos,c)<100):
                if self.do_clear(*c, ch):
                    return True
            p = self._home_step(ch)
            if not self.can_afford(math.dist(self.pos,p)/5+12):
                break
            resp = self.measure(*p,ch)
            if resp.get('measure_result') == 'near':
                return self.do_clear(*p,ch)
            if resp.get('measure_result') == 'no_signal':
                # Retry toward the last positive position; never infer absence.
                S=np.array(rec.pts[-1]); p=(np.array(p)+S)/2
                resp = self.measure(*p,ch)
                if resp.get('measure_result') == 'near':
                    return self.do_clear(*p,ch)
        if not rec.cleared:
            return super().clear_target(ch,rec)
        return True
