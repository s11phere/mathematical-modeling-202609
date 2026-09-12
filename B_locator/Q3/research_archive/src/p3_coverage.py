"""Conservative continuous-disk coverage from actual no-signal replies.

Closed square cells tile [-1800,1800]^2, including every cell intersecting
the arena disk. A center covered at radius 1000 - step/sqrt(2) - epsilon
certifies the entire cell by the triangle inequality. No positive/near
reply is ever used to certify absence. This may over-cover boundary cells.
"""
import math
import numpy as np
from p3_arena import R_ARENA, R_RECV_MIN


class CertifiedCoverageMixin:
    def annulus_grid(self):
        if self._ag is None:
            requested = float(self.cfg.cover_grid_step_m)
            if requested <= 0:
                raise ValueError('cover_grid_step_m must be positive')
            n = int(math.ceil(2 * R_ARENA / requested))
            step = 2 * R_ARENA / n
            xs = -R_ARENA + (np.arange(n)+0.5)*step
            gx, gy = np.meshgrid(xs,xs)
            intersects = (np.maximum(np.abs(gx)-step/2,0)**2 +
                          np.maximum(np.abs(gy)-step/2,0)**2 <= R_ARENA**2+1e-6)
            self._ag = (gx[intersects],gy[intersects])
            self._cert_radius = R_RECV_MIN-step/math.sqrt(2)-1e-6
            if self._cert_radius <= 0:
                raise ValueError('coverage cells are too large')
        return self._ag

    def certified_radius(self):
        self.annulus_grid()
        return self._cert_radius

    def unsafe_of(self,ch):
        rec = self.recs[int(ch)]
        key = (int(ch),len(rec.meas_log))
        if key not in self._unsafe_cache:
            gx,gy = self.annulus_grid()
            out = np.ones(len(gx),dtype=bool)
            r2 = self.certified_radius()**2
            for x,y,_t,result in rec.meas_log:
                if result == 'no_signal':
                    out &= (gx-x)**2+(gy-y)**2 > r2
            self._unsafe_cache[key] = out
        return self._unsafe_cache[key]

    def heard_pending(self):
        return [int(ch) for ch,r in self.recs.items()
                if not r.cleared and (r.n_bearings or r.near_hits)]

    def unheard(self):
        return [int(ch) for ch,r in self.recs.items()
                if not r.cleared and not r.n_bearings and not r.near_hits]

    def adds_coverage(self,ch,x,y):
        gx,gy = self.annulus_grid()
        return bool(np.any(self.unsafe_of(ch) &
                    ((gx-x)**2+(gy-y)**2 <= self.certified_radius()**2)))

    def adds_any_coverage(self,x,y):
        return any(self.adds_coverage(ch,x,y) for ch in self.unheard())

    def is_complete(self):
        return (not self.heard_pending() and
                all(not self.unsafe_of(ch).any() for ch in self.unheard()))
