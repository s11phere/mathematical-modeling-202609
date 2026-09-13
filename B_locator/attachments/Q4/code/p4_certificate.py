"""Conservative continuous position/orientation coverage for problem 4.

A source at p is heard at q if |q-p| <= 1000 and (q-p).d >= 0 for
some unknown unit direction d.  Reversing the protocol's direction convention
just replaces d by -d; this certificate includes all directions.

The disk is covered by square cells and the unit circle by angle intervals.
For a cell centre c, radius rho and orientation half width h, a measurement q
certifies an entire position/orientation cell when

    |q-c| + rho <= 1000,
    angle(q-c, d_center) + h <= acos(rho / |q-c|).

The first inequality is the triangle inequality.  The second gives
(q-c).d >= rho for every direction in the interval, hence (q-p).d >= 0
for every p in the square.  Thus there is no interpolation assumption.
Only actual no_signal replies may exclude states of an uncleared channel.

Partial coverage is a lower bound on area-times-angle coverage under a
uniform position and orientation reference measure, NOT a clearance-rate
guarantee or an inferred source probability.  Boundary squares are assigned
zero area in this lower bound, unless every state has been certified.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class CertificateResult:
    complete: bool
    excluded_fraction_lower_bound: float
    n_uncovered_states: int
    n_cells: int
    n_orientations: int


class DirectionalCertificate:
    """Reusable state discretisation with strict spatial and angular margins.

    ``station_mask(q)`` returns a boolean (n_cells, n_dir) array.  Union masks
    of no_signal measurements to certify an absent channel; union masks of
    intended stations to certify a static exploration layout.  Use
    ``from_log(rec.meas_log)`` for an actual ChannelRec measurement log.
    Coordinates are never read from the simulator's hidden source state.
    """

    def __init__(self, step_m=60.0, n_dir=32, arena_radius_m=1800.0,
                 reception_radius_m=1000.0):
        if step_m <= 0 or n_dir < 4 or arena_radius_m <= 0:
            raise ValueError("positive geometry and at least 4 orientations required")
        self.step_m = float(step_m)
        self.n_dir = int(n_dir)
        self.arena_radius_m = float(arena_radius_m)
        self.reception_radius_m = float(reception_radius_m)
        # An integer number of exact squares covers [-R,R]^2.  Keep every
        # square intersecting the disk, including cells whose centres lie out.
        n_side = int(math.ceil(2 * self.arena_radius_m / self.step_m))
        side = 2 * self.arena_radius_m / n_side
        self.cell_side_m = side
        ax = -self.arena_radius_m + (np.arange(n_side) + 0.5) * side
        xx, yy = np.meshgrid(ax, ax)
        pts = np.column_stack((xx.ravel(), yy.ravel()))
        closest = np.maximum(np.abs(pts) - side / 2, 0)
        keep = np.sum(closest * closest, axis=1) <= self.arena_radius_m ** 2
        self.centers = pts[keep]
        self.rho = side / math.sqrt(2.0)
        self.angles = (np.arange(self.n_dir) + 0.5) * (2 * math.pi / self.n_dir)
        self.angle_half_width = math.pi / self.n_dir
        farthest = np.abs(self.centers) + side / 2
        self.interior = np.sum(farthest * farthest, axis=1) <= self.arena_radius_m ** 2
        self._weight = side ** 2 / (math.pi * self.arena_radius_m ** 2 * self.n_dir)
        self._cache = {}

    @property
    def shape(self):
        return (len(self.centers), self.n_dir)

    def empty(self):
        return np.zeros(self.shape, dtype=bool)

    def station_mask(self, xy, *, cache=True):
        xy = (float(xy[0]), float(xy[1]))
        if not all(math.isfinite(v) for v in xy):
            raise ValueError("station coordinates must be finite")
        if cache and xy in self._cache:
            return self._cache[xy]
        delta = np.asarray(xy) - self.centers
        dist = np.hypot(delta[:, 0], delta[:, 1])
        valid = (dist + self.rho <= self.reception_radius_m - 1e-8) & (dist > self.rho)
        out = self.empty()
        if np.any(valid):
            a = np.arctan2(delta[valid, 1], delta[valid, 0])
            diff = np.abs((a[:, None] - self.angles + math.pi) % (2 * math.pi) - math.pi)
            half = np.arccos(self.rho / dist[valid]) - self.angle_half_width
            out[valid] = diff <= half[:, None] - 1e-12
        if cache:
            if len(self._cache) >= 256:
                self._cache.clear()
            out.flags.writeable = False
            self._cache[xy] = out
        return out

    def mask_for_points(self, points):
        out = self.empty()
        for xy in points:
            out |= self.station_mask(xy)
        return out

    def all_orientation_cells(self, points):
        """Certify spatial cells by exact circular-interval union.

        This stronger final check has the same strict spatial margin, but no
        angular discretisation loss.  A cell is True only when the station
        arcs cover all of [0,2*pi].  A False value means unproved, not a known
        blind spot.  Useful for final certificates with step_m=20 or 30.
        """
        points = np.asarray(list(points), dtype=float).reshape(-1, 2)
        if not len(points):
            return np.zeros(len(self.centers), dtype=bool)
        if not np.isfinite(points).all():
            raise ValueError("station coordinates must be finite")
        delta = points[None, :, :] - self.centers[:, None, :]
        dist = np.linalg.norm(delta, axis=2)
        valid = (dist + self.rho <= self.reception_radius_m - 1e-8) & (dist > self.rho)
        half = np.arccos(np.minimum(self.rho / np.maximum(dist, self.rho), 1.0))
        angle = np.arctan2(delta[:, :, 1], delta[:, :, 0])
        start = (angle - half) % (2 * math.pi)
        end = start + 2 * half
        starts = np.concatenate((start, start - 2 * math.pi), axis=1)
        ends = np.concatenate((end, end - 2 * math.pi), axis=1)
        valid2 = np.concatenate((valid, valid), axis=1)
        # Clip wrapping arcs to the interval we certify; invalid/empty arcs
        # become a zero-width interval at 2*pi.
        live = valid2 & (ends > 0) & (starts < 2 * math.pi)
        starts = np.where(live, np.maximum(starts, 0), 2 * math.pi)
        ends = np.where(live, np.minimum(ends, 2 * math.pi), 0.0)
        order = np.argsort(starts, axis=1)
        starts = np.take_along_axis(starts, order, axis=1)
        ends = np.take_along_axis(ends, order, axis=1)
        reach = np.maximum.accumulate(ends, axis=1)
        # Use a small negative tolerance: tiny numerical gaps never establish
        # coverage.  Initial/final equality is clipping at exact 0 and 2*pi.
        # Placeholders at 2*pi should not count as a required join; their end
        # is zero so they cannot extend the actual covered interval.
        joined = np.all((starts[:, 1:] == 2 * math.pi)
                        | (starts[:, 1:] <= reach[:, :-1] - 1e-12), axis=1)
        return (starts[:, 0] == 0) & joined & (reach[:, -1] == 2 * math.pi)

    def continuous_complete(self, points):
        return bool(np.all(self.all_orientation_cells(points)))

    def from_log(self, meas_log):
        """Accept ChannelRec entries (x, y, time, result) or action dicts."""
        out = self.empty()
        for rec in meas_log:
            if isinstance(rec, dict):
                result = rec.get("measure_result", rec.get("result"))
                xy = (rec.get("x", rec.get("x_m")), rec.get("y", rec.get("y_m")))
            else:
                xy, result = rec[:2], rec[3]
            if result == "no_signal":
                out |= self.station_mask(xy)
        return out

    def summarize(self, mask):
        mask = np.asarray(mask, dtype=bool)
        if mask.shape != self.shape:
            raise ValueError(f"expected coverage shape {self.shape}, got {mask.shape}")
        left = int(mask.size - np.count_nonzero(mask))
        frac = 1.0 if left == 0 else float(np.count_nonzero(mask[self.interior]) * self._weight)
        return CertificateResult(left == 0, frac, left, len(self.centers), self.n_dir)

    def gap_witnesses(self, mask, limit=20):
        """Representative uncertain (x,y,d_deg), useful for gap planning.

        These are centres of unproved cells, not asserted physical blind spots.
        In particular a centre can lie just outside the arena on boundary cells.
        """
        ii, jj = np.nonzero(~np.asarray(mask, dtype=bool))
        if len(ii) > int(limit):
            take = np.linspace(0, len(ii) - 1, int(limit), dtype=int)
            ii, jj = ii[take], jj[take]
        return [(float(self.centers[i, 0]), float(self.centers[i, 1]),
                 math.degrees(float(self.angles[j]))) for i, j in zip(ii, jj)]

    def gap_candidates(self, mask, limit=32, offset_m=650.0):
        """Stations which individually certify a representative missing state."""
        offset = float(offset_m)
        if not (self.rho / math.cos(self.angle_half_width) < offset
                < self.reception_radius_m - self.rho):
            raise ValueError("offset cannot certify a whole position/orientation cell")
        return [(x + offset * math.cos(math.radians(a)),
                 y + offset * math.sin(math.radians(a)))
                for x, y, a in self.gap_witnesses(mask, limit)]


def ring_layout(rings, include_origin=True):
    """Generate (radius,count,phase_deg) rings for static comparisons."""
    out = [(0.0, 0.0)] if include_origin else []
    for ring in rings:
        radius, count = float(ring[0]), int(ring[1])
        phase = math.radians(float(ring[2])) if len(ring) > 2 else 0.0
        out.extend((radius * math.cos(phase + 2 * math.pi * k / count),
                    radius * math.sin(phase + 2 * math.pi * k / count))
                   for k in range(count))
    return out


def strict_layout():
    """25 stations incl. origin; certified at step=20, n_dir=96.

    Origin + 950 m x 6 + 950*sqrt(3) m x 6 (30 degree phase) + 1900 m x 12.
    An open nearest-neighbour/2-opt tour from the origin is about 19.49 km.
    This is a usable certified candidate layout, not a station-count optimum.
    """
    return ring_layout(((950.0, 6, 0.0), (950.0 * math.sqrt(3.0), 6, 30.0),
                        (1900.0, 12, 0.0)))


def certify_channels(records, *, certificate=None):
    """Report each uncleared channel; a heard/near pending source prevents exit."""
    cert = certificate or DirectionalCertificate()
    out = {}
    for ch, rec in records.items():
        if rec.cleared:
            out[int(ch)] = {"complete": True, "reason": "cleared"}
            continue
        positive = any(entry[3] in ("direction", "near") for entry in rec.meas_log)
        result = cert.summarize(cert.from_log(rec.meas_log))
        out[int(ch)] = {"complete": bool(result.complete and not positive),
                        "reason": "heard_pending" if positive else "no_signal_certificate",
                        "excluded_fraction_lower_bound": result.excluded_fraction_lower_bound,
                        "n_uncovered_states": result.n_uncovered_states}
    return out
