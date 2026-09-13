"""Reply-only homing for Q4, including sources with arbitrary 180 degree cones.

``P4HomingMixin`` can precede any P4GridRobot subclass in its MRO.  It replaces
estimate/region and both local clearance entry points.  Negative measurements
never exclude a distance disk: loss of signal can be caused by the cone.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from p1_intersection import clip_halfplane, wedge_halfplanes, min_enclosing_circle
from p3_arena import R_ARENA, R_RECV_MAX, R_CLEAR, V_ROBOT
from p3_robot import _dist_point_polygon
from p4_robot import P4Config, P4GridRobot


@dataclass
class P4HomingConfig(P4Config):
    home_fraction: float = 0.60
    home_lateral_m: float = 100.0
    home_max_steps: int = 8
    home_sweep_radius_m: float = 75.0
    home_clear_spacing_m: float = 28.0


class P4HomingMixin:
    """Finite positive-bearing polygon, short baseline, then adaptive approach."""

    def __init__(self, *args, **kwargs):
        self._p4_home_regions = {}
        self._p4_home_clear_points = {}
        self._p4_home_caps = {}
        super().__init__(*args, **kwargs)

    def home_region(self, rec):
        if rec.near_hits:
            row = next(row for row in reversed(rec.meas_log) if row[3] == 'near')
            return dict(center=tuple(row[:2]), radius=5.0, poly=None,
                        status='bounded', n_bearings=rec.n_bearings)
        if not rec.pts:
            return None
        caps = self._p4_home_caps.get(rec.channel, [])
        key = (rec.channel, len(rec.pts), len(caps))
        if key in self._p4_home_regions:
            return self._p4_home_regions[key]
        poly = [np.array(p, float) for p in
                [(-R_ARENA, -R_ARENA), (R_ARENA, -R_ARENA),
                 (R_ARENA, R_ARENA), (-R_ARENA, R_ARENA)]]
        # Circumscribed disk approximations retain every physically possible
        # source.  The extra 0.005 degrees covers bearing serialization rounding.
        for station, radius in [(np.zeros(2), R_ARENA)] + [
                (np.array(p), R_RECV_MAX) for p in rec.pts]:
            for angle in np.arange(0, 2 * math.pi, math.pi / 16):
                u = np.array([math.cos(angle), math.sin(angle)])
                poly = clip_halfplane(poly, u, -float(u @ station) - radius)
        for station, bearing in zip(rec.pts, rec.svds):
            for normal, constant in wedge_halfplanes(station, bearing, 1.005 + 1e-8):
                poly = clip_halfplane(poly, normal, constant)
        for normal, constant in caps:
            poly = clip_halfplane(poly, normal, constant)
        if not poly:
            return None
        arr = np.asarray(poly)
        origin = arr.mean(axis=0)
        circle = min_enclosing_circle(arr - origin)
        center = np.asarray(circle[0]) + origin if circle else origin
        radius = float(np.max(np.linalg.norm(arr - center, axis=1)))
        result = dict(center=tuple(center), radius=radius, poly=arr.tolist(),
                      status='bounded', n_bearings=rec.n_bearings)
        self._p4_home_regions[key] = result
        return result

    def region(self, rec):
        br = self.home_region(rec)
        if br is None:
            return dict(status='none', n_bearings=rec.n_bearings)
        return dict(status='bounded', n_bearings=rec.n_bearings,
                    min_enclosing_center=br['center'],
                    min_enclosing_radius_m=br['radius'], vertices=br['poly'] or [])

    def bounded_region(self, rec):
        return self.home_region(rec)

    def estimate(self, ch):
        br = self.home_region(self.recs[int(ch)])
        if br is None:
            return None, float('inf'), None
        return np.asarray(br['center']), br['radius'], br

    def _home_clear(self, ch, point):
        point = tuple(map(float, point))
        tried = self._p4_home_clear_points.setdefault(int(ch), [])
        if any(math.dist(point, prev) < 0.2 for prev in tried):
            return False
        if not self.can_afford(math.dist(self.pos, point) / V_ROBOT + 6):
            return False
        if self.do_clear(*point, int(ch)):
            return True
        if not self.aborted:
            tried.append(point)
        return False

    def _home_measure(self, ch, point):
        point = tuple(map(float, point))
        if not self.can_afford(math.dist(self.pos, point) / V_ROBOT + 12):
            return None
        reply = self.measure(*point, int(ch))
        self.note_meas(point)
        self.stats['n_locate'] = self.stats.get('n_locate', 0) + 1
        if reply.get('measure_result') == 'near':
            self._home_clear(ch, point)
        return reply.get('measure_result')

    def _home_cross(self, ch, br, scale=1.0):
        """Try both sides of a short baseline, retreating after two negatives.

        All candidate coordinates come from an actual positive bearing. A
        lone negative does not change the feasible source polygon. Trying opposite
        sides avoids depending on a guessed radial emission orientation.
        """
        rec = self.recs[int(ch)]
        source_station = np.asarray(rec.pts[-1], float)
        angle = math.radians(rec.svds[-1])
        u = np.array([math.cos(angle), math.sin(angle)])
        normal = np.array([-u[1], u[0]])
        center = np.asarray(br['center'])
        along = max(0.0, float((center - source_station) @ u))
        forward = getattr(self.cfg, 'home_fraction', 0.60) * along * scale
        lateral = min(getattr(self.cfg, 'home_lateral_m', 100.0),
                      max(22.0, 0.3 * max(along, 1.0))) * scale
        midpoint = source_station + forward * u
        candidates = [midpoint + sign * lateral * normal for sign in (-1, 1)]
        candidates.sort(key=lambda p: math.dist(p, self.pos))
        old_n = rec.n_bearings
        results = []
        for point in candidates:
            result = self._home_measure(ch, point)
            results.append(result)
            if rec.cleared or result is None:
                return rec.cleared
            if rec.n_bearings > old_n:
                return True
        # Paired negatives have more information than one negative. Let S be
        # the positive station and Q+/- = S + t*u +/- l*n. If a feasible source
        # G lies beyond that cross-section, its bearing ray crosses segment
        # Q-Q+. At least one endpoint is in the same closed emission halfplane
        # as S. Moreover t >= l*(sec(e)+tan(e)) makes BOTH endpoints closer to
        # every such G than S, hence inside its actual reception radius. Thus
        # two negatives rule out the entire far part of this bearing wedge.
        # This uses neither a radial orientation assumption nor a negative
        # 1000 m exclusion disk; a lone negative never adds a constraint.
        err = math.radians(1.005 + 1e-8)
        if (results == ['no_signal', 'no_signal']
                and forward * math.tan(err) <= lateral - 1e-5
                and forward >= lateral * (1.0 / math.cos(err) + math.tan(err)) + 1e-5):
            constant = -float(u @ source_station) - forward - 1e-6
            self._p4_home_caps.setdefault(int(ch), []).append((u, constant))
            self.stats['n_home_pair_caps'] = self.stats.get('n_home_pair_caps', 0) + 1
        return False

    def _home_cover_polygon(self, ch, br):
        """Finite geometric fallback, independent of signal reception.

        A square lattice with spacing <= 20 sqrt(2) covers its entire plane
        with clear disks. Keep every lattice point whose disk meets the outer
        polygon. This also handles a source exactly on its cone boundary.
        """
        if not br['poly']:
            return self._home_clear(ch, br['center'])
        poly = np.asarray(br['poly'], float)
        step = min(getattr(self.cfg, 'home_clear_spacing_m', 28.0), 28.0)
        # Rotate to the polygon principal direction: a one-bearing wedge is
        # narrow, so this avoids a large rectangular grid of irrelevant cells.
        c = np.asarray(br['center'])
        cov = (poly - c).T @ (poly - c)
        _values, basis = np.linalg.eigh(cov)
        local = (poly - c) @ basis
        low = np.floor(local.min(axis=0) / step).astype(int) - 1
        high = np.ceil(local.max(axis=0) / step).astype(int) + 1
        candidates = []
        for i in range(low[0], high[0] + 1):
            for j in range(low[1], high[1] + 1):
                point = c + (np.array([i, j]) * step) @ basis.T
                if _dist_point_polygon(point, poly) <= R_CLEAR + 1e-7:
                    candidates.append(tuple(point))
        self.stats['n_home_fallback'] = self.stats.get('n_home_fallback', 0) + 1
        while candidates and not self.aborted:
            index = min(range(len(candidates)),
                        key=lambda k: math.dist(candidates[k], self.pos))
            point = candidates.pop(index)
            if self._home_clear(ch, point):
                return True
            if not self.can_afford(12):
                break
        return False

    def clear_here(self, ch):
        rec = self.recs[int(ch)]
        if rec.cleared:
            return True
        previous_phase = self.phase
        self.phase = 'home'
        for iteration in range(getattr(self.cfg, 'home_max_steps', 8)):
            if self.aborted or not self.can_afford(15):
                break
            br = self.home_region(rec)
            if br is None:
                break
            if rec.n_bearings >= 2 or br['radius'] <= R_CLEAR:
                if self._home_clear(ch, br['center']):
                    self.phase = previous_phase
                    return True
                if br['radius'] <= getattr(self.cfg, 'home_sweep_radius_m', 75.0):
                    result = self._home_measure(ch, br['center'])
                    if rec.cleared:
                        self.phase = previous_phase
                        return True
                    updated = self.home_region(rec)
                    if updated and updated['radius'] < br['radius'] * 0.8:
                        continue
                    ok = self._home_cover_polygon(ch, updated or br)
                    self.phase = previous_phase
                    return ok
                result = self._home_measure(ch, br['center'])
                if rec.cleared:
                    self.phase = previous_phase
                    return True
                if result in ('direction', 'near'):
                    continue
            # Retrying with a smaller forward step covers both an overshoot and
            # a cone-boundary rejection, without inferring which caused it.
            br = self.home_region(rec)
            if br is None:
                break
            before = rec.n_bearings
            for scale in (1.0, 0.5, 0.25):
                if self._home_cross(ch, br, scale) or self.aborted:
                    break
            if rec.cleared:
                self.phase = previous_phase
                return True
            if rec.n_bearings == before:
                break
        br = self.home_region(rec)
        ok = bool(br and self._home_cover_polygon(ch, br))
        self.phase = previous_phase
        if not ok:
            rec.clear_fail += 1
        return ok

    def solve_channel(self, ch):
        return self.clear_here(ch)


class P4HomingRobot(P4HomingMixin, P4GridRobot):
    def __init__(self, arena, cfg=None, **kwargs):
        super().__init__(arena, cfg or P4HomingConfig(), **kwargs)
