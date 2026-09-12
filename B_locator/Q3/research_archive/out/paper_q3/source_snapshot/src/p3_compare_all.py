"""跨场景对照：统一航路(tour) vs 覆盖扫圈(sweep) vs 期望场贪心(field)。

    python src/p3_compare_all.py --cases 20
"""
from __future__ import annotations

import argparse
import math
import os
import statistics as st
import sys
from dataclasses import replace

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402
from p3_sweep import SweepConfig, SweepRobot  # noqa: E402
from p3_tour import TourConfig, TourRobot  # noqa: E402
from p3_bench import LIVE1, LIVE2, arena_from, outer_annulus, center_cluster  # noqa: E402

POLICIES = [("扫圈 sweep", SweepRobot, SweepConfig),
            ("期望场 field", P3Robot, P3Config),
            ("统一航路 tour", TourRobot, TourConfig)]


def path_metrics(acts):
    pts = [(0.0, 0.0)] + [(a["x"], a["y"]) for a in acts if "x" in a]
    P = []
    for p in pts:
        if not P or math.dist(P[-1], p) > 1.0:
            P.append(p)
    un, um = 0, 0.0
    for i in range(1, len(P) - 1):
        v1 = np.asarray(P[i], float) - np.asarray(P[i - 1], float)
        v2 = np.asarray(P[i + 1], float) - np.asarray(P[i], float)
        n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        if n1 < 30 or n2 < 30:
            continue
        ang = math.degrees(math.acos(max(-1, min(1, float((v1 / n1) @ (v2 / n2))))))
        if ang > 120.0:
            un += 1
            um += n2
    return un, um


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--scenarios", default="random,annulus,center,live1")
    a = ap.parse_args()
    base = load_base()

    def mk(scen, seed):
        if scen == "random":
            return MockArena(seed=seed)
        if scen == "annulus":
            return outer_annulus(seed=seed)
        if scen == "center":
            return center_cluster(seed=seed)
        if scen == "live1":
            return arena_from(LIVE1, seed=seed)
        return arena_from(LIVE2, seed=seed)

    hdr = (f"{'场景':<9}{'策略':<14}{'清除率':>8}{'全清':>7}{'T/N':>8}{'虚拟/s':>9}"
           f"{'末清/N':>8}{'检测':>7}{'行程/m':>9}{'折返':>6}{'折返/m':>8}")
    print(hdr)
    print("-" * len(hdr))
    for scen in [s.strip() for s in a.scenarios.split(",") if s.strip()]:
        seeds = [a.seed + 100 * i for i in range(a.cases)]
        for name, cls, cfgcls in POLICIES:
            T = cl = ns = mm = tr = 0
            last = 0.0
            full = 0
            un = um = 0.0
            for s in seeds:
                aren = mk(scen, s)
                rb = cls(aren, cfgcls(), base=base, log=None)
                rep = rb.run()
                T += rep["virtual_time_s"]
                cl += rep["cleared"]
                ns += rep["n_sources"]
                mm += rep["n_measure"]
                tr += rep["travel_m"]
                last += (rep["avg_clear_time_s"] or 0.0) * rep["cleared"]
                full += int(rep["cleared"] == rep["n_sources"])
                u1, u2 = path_metrics(getattr(aren, "actions", []))
                un += u1
                um += u2
            n = len(seeds)
            print(f"{scen:<9}{name:<14}{cl/ns:>8.4f}{full:>4}/{n:<3}{T/cl:>8.1f}"
                  f"{T/n:>9.0f}{last/cl:>8.1f}{mm/n:>7.0f}{tr/n:>9.0f}"
                  f"{un/n:>6.1f}{um/n:>8.0f}", flush=True)


if __name__ == "__main__":
    main()
