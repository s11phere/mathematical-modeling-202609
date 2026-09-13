"""Experimental receding-horizon covering-tour planner for B question 3.

Unlike TourRobot, this planner has no fixed ring stations or angular cursor.
At each decision it builds a route through known targets, then solves a greedy
covering-tour problem over the *remaining per-channel coverage gap*. Target
stops compete with temporary measurement stations, including their scan cost.
Only the first stop is executed; actual observations determine the next plan.

This module deliberately inherits the existing localization and clearance
procedure so routing changes can be compared separately. No truth is consulted.
The inherited completion predicate evaluates a 25 m grid; its report field
``complete_proof`` is not a continuous geometric coverage certificate.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, fields, replace
from pathlib import Path

import numpy as np

from p3_arena import MockArena, T_MEASURE, T_SWITCH, V_ROBOT
from p3_bench import (LIVE1, LIVE2, HDR, arena_from, center_cluster, fmt_row,
                      outer_annulus, run_one, summarize)
from p3_robot import load_base
from p3_tour import TourConfig, TourRobot


@dataclass
class FrontierConfig(TourConfig):
    candidate_radii: tuple = (900.0, 1100.0, 1300.0, 1500.0)
    candidate_angles: int = 72
    scan_cost_weight: float = 0.3
    travel_cost_floor_m: float = 100.0
    gain_power: float = 2.0
    target_first: bool = False
    target_cover_duty: bool = False
    route_mode: str = "tsp"
    locate_mode: str = "never"
    offroute_clear: bool = False
    enroute_spacing_m: float = 0.0


class FrontierRobot(TourRobot):
    """Dynamic set cover with cheapest insertion and unconstrained 2-opt."""

    def __init__(self, arena, cfg=None, base=None, log=None):
        super().__init__(arena, cfg or FrontierConfig(), base=base, log=log)
        self._frontier_candidates = None
        self._frontier_cover = None

    def pick_direction(self):
        # Retained only to satisfy the inherited loop; no angular restriction.
        self.ring_dir = 1.0

    def mark_served(self, x, y):
        # Coverage is recomputed from real observations, never by proximity.
        return None

    def forward_ring(self, dir_sign, cursor=None):
        # Stale-localization mode is intentionally disabled in this experiment.
        return []

    def chans_at(self, x, y, ch=None, cover_duty=False):
        out = []
        for c in self.pending():
            rec = self.recs[c]
            if rec.n_bearings == 0:
                if (cover_duty or ch is None) and self.adds_coverage(c, x, y):
                    out.append(c)
            elif rec.n_bearings == 1 and self._cross_ok(rec, x, y):
                out.append(c)
            if ch is not None and c == int(ch) and c not in out:
                out.append(c)
        if ch is not None and int(ch) in out:
            out.remove(int(ch))
            out.insert(0, int(ch))
        return out

    def _candidate_cover(self):
        if self._frontier_candidates is None:
            angles = np.arange(self.cfg.candidate_angles) * (2 * math.pi /
                      self.cfg.candidate_angles)
            self._frontier_candidates = np.asarray([
                (r * math.cos(a), r * math.sin(a))
                for r in self.cfg.candidate_radii for a in angles])
            gx, gy = self.annulus_grid()
            self._frontier_cover = ((self._frontier_candidates[:, 0, None] - gx) ** 2
                    + (self._frontier_candidates[:, 1, None] - gy) ** 2
                    <= self.cfg.cover_radius_m ** 2)
        return self._frontier_candidates, self._frontier_cover

    def _insert_cost(self, pts, seq):
        """Cost and index for inserting every candidate into the open route."""
        prev = np.asarray([self.pos] + [w["xy"] for w in seq], float)
        d = np.linalg.norm(pts[:, None, :] - prev[None, :, :], axis=2)
        cost = d.copy()
        if seq:
            cost[:, :-1] += d[:, 1:] - np.linalg.norm(np.diff(prev, axis=0), axis=1)
        ind = np.argmin(cost, axis=1)
        return cost[np.arange(len(pts)), ind], ind

    def assemble_route(self, dir_sign, targets=None, cursor=None):
        seq = [dict(w, cover_duty=False) for w in
               (self.target_waypoints() if targets is None else targets)]
        seq = self.nn_2opt(seq)
        lattice, lattice_cover = self._candidate_cover()
        gx, gy, unsafe = self.uncovered_mask()
        if not unsafe.any():
            return seq, self._route_length(seq)

        if self.cfg.enroute_spacing_m > 0.0 and seq:
            path = [self.pos] + [w["xy"] for w in seq]
            extras = []
            for a, b in zip(path, path[1:]):
                parts = int(math.ceil(math.dist(a, b) / self.cfg.enroute_spacing_m))
                extras.extend(((1-t)*a[0] + t*b[0], (1-t)*a[1] + t*b[1])
                              for t in np.arange(1, parts) / parts)
            if extras:
                extra_pts = np.asarray(extras, float)
                extra_cover = ((extra_pts[:, 0, None] - gx) ** 2
                         + (extra_pts[:, 1, None] - gy) ** 2
                         <= self.cfg.cover_radius_m ** 2)
                lattice = np.concatenate((lattice, extra_pts), axis=0)
                lattice_cover = np.concatenate((lattice_cover, extra_cover), axis=0)

        # Known targets are mandatory route stops but their coverage scan is
        # optional. The set-cover objective decides which should perform it.
        targets_copy = list(seq)
        if targets_copy:
            target_pts = np.asarray([w["xy"] for w in targets_copy], float)
            target_cover = ((target_pts[:, 0, None] - gx) ** 2
                    + (target_pts[:, 1, None] - gy) ** 2
                    <= self.cfg.cover_radius_m ** 2)
            pts = np.concatenate((lattice, target_pts), axis=0)
            covers = np.concatenate((lattice_cover, target_cover), axis=0)
        else:
            pts, covers = lattice, lattice_cover
        available = np.ones(len(pts), bool)
        n_lattice = len(lattice)
        scan_cost = (T_MEASURE + T_SWITCH) * max(1, len(self.unheard())) * V_ROBOT
        scan_cost *= self.cfg.scan_cost_weight

        # Retain the inherited grid coverage requirement, without early stopping.
        # The score decides route shape only.
        for _ in range(30):
            if not unsafe.any():
                break
            gains = np.count_nonzero(covers[:, unsafe], axis=1).astype(float)
            costs, inserts = self._insert_cost(pts, seq)
            costs[n_lattice:] = 0.0
            score = gains ** self.cfg.gain_power / (scan_cost +
                    self.cfg.travel_cost_floor_m + np.maximum(0.0, costs))
            score[~available] = -1.0
            best = int(np.argmax(score))
            if gains[best] == 0:
                break
            available[best] = False
            if best >= n_lattice:
                targets_copy[best - n_lattice]["cover_duty"] = True
            else:
                seq.insert(int(inserts[best]), {"kind": "cover", "ch": None,
                    "xy": tuple(pts[best]), "r": None, "cover_duty": True})
            unsafe = unsafe & ~covers[best]

        # Reorder the joint route without the original angular constraints.
        seq = self.nn_2opt(seq)
        if self.cfg.target_first and targets_copy:
            nearest = min(targets_copy, key=lambda w: math.dist(self.pos, w["xy"]))
            seq.remove(nearest)
            seq.insert(0, nearest)
        return seq, self._route_length(seq)

    def _route_length(self, seq):
        pts = [self.pos] + [w["xy"] for w in seq]
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


class OriginalTourRobot(TourRobot):
    """Freeze the user's original singleton measurement behavior for controls."""

    def _singleton_reachable(self, rec, x, y):
        return True


def original_config():
    vals = dict(cover_rings=((1000.0, 8),), route_mode="polish",
                locate_mode="stale", offroute_clear=True, target_cover_duty=True)
    return TourConfig(**{k: v for k, v in vals.items() if k in
                         {f.name for f in fields(TourConfig)}})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--step", type=int, default=100)
    ap.add_argument("--scenarios", default="random,annulus,center,live1,live2")
    ap.add_argument("--variants", default="original,tour,frontier")
    ap.add_argument("--cfg", default="{}")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()
    makers = {"random": lambda s: MockArena(seed=s), "annulus": outer_annulus,
              "center": center_cluster, "live1": lambda s: arena_from(LIVE1, seed=s),
              "live2": lambda s: arena_from(LIVE2, seed=s)}
    cfg = replace(FrontierConfig(), **json.loads(args.cfg))
    variants = {"original": (OriginalTourRobot, original_config()),
                "tour": (TourRobot, TourConfig(cover_rings=((1050.0, 7),),
                         route_mode="tsp", locate_mode="never", offroute_clear=False)),
                "frontier": (FrontierRobot, cfg)}
    base = load_base()
    output = {"arguments": vars(args), "results": {}}
    for scenario in args.scenarios.split(","):
        print(scenario, flush=True)
        print(HDR, flush=True)
        for name in args.variants.split(","):
            cls, config = variants[name]
            reps = [run_one(cls, config, makers[scenario](args.seed + i * args.step),
                            base, want_path=True) for i in range(args.cases)]
            summary = summarize(reps)
            summary["complete_proof_cases"] = sum(bool(r["complete_proof"]) for r in reps)
            print(fmt_row(name, summary) + " proof=" + str(summary["complete_proof_cases"]),
                  flush=True)
            output["results"][scenario + "/" + name] = {**summary,
                "per_case": [{k: v for k, v in r.items() if not k.startswith("_")
                    and k not in ("truth", "channels", "mock_stats")} for r in reps]}
            if args.json_out:
                p = Path(args.json_out)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str),
                             encoding="utf-8")


if __name__ == "__main__":
    main()
