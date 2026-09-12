"""把一局的行程拆成"站间"与"站内"两部分，并给出"同样路点的最优航路"下界。"""
from __future__ import annotations

import argparse
import math
import os
import statistics as st
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena  # noqa: E402
from p3_robot import load_base  # noqa: E402
from p3_tour import TourConfig, TourRobot  # noqa: E402
from p3_bench import LIVE1, LIVE2, arena_from, outer_annulus, center_cluster  # noqa: E402


def tsp(pts, start=(0.0, 0.0)):
    P = [np.asarray(p, float) for p in pts]
    S = np.asarray(start, float)
    k = len(P)
    if k == 0:
        return 0.0
    left, cur, seq = list(range(k)), S, []
    while left:
        j = min(left, key=lambda i: float(np.linalg.norm(P[i] - cur)))
        seq.append(j)
        left.remove(j)
        cur = P[j]

    def tot(o):
        d = float(np.linalg.norm(P[o[0]] - S))
        for a, b in zip(o, o[1:]):
            d += float(np.linalg.norm(P[b] - P[a]))
        return d
    best = tot(seq)
    imp = True
    while imp:
        imp = False
        for i in range(k - 1):
            for j in range(i + 1, k):
                c = seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]
                d = tot(c)
                if d < best - 1e-9:
                    seq, best, imp = c, d, True
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--scenario", default="random")
    a = ap.parse_args()
    base = load_base()
    rows = []
    for i in range(a.cases):
        s = a.seed + 100 * i
        if a.scenario == "random":
            aren = MockArena(seed=s)
        elif a.scenario == "annulus":
            aren = outer_annulus(seed=s)
        elif a.scenario == "center":
            aren = center_cluster(seed=s)
        elif a.scenario == "live1":
            aren = arena_from(LIVE1, seed=s)
        else:
            aren = arena_from(LIVE2, seed=s)
        rb = TourRobot(aren, TourConfig(), base=base, log=None)
        rep = rb.run()
        stops = [tuple(e["xy"]) for e in rb.tour_log]
        inter = 0.0
        prev = (0.0, 0.0)
        for p in stops:
            inter += math.dist(prev, p)
            prev = p
        lb = tsp(stops)
        rows.append((s, rep["travel_m"], inter, lb, len(stops), rep["cleared"]))
    print(f"{a.scenario}：{a.cases} 局")
    print(f"{'seed':>10}{'总行程':>9}{'站间':>8}{'站内':>8}{'路点TSP':>9}"
          f"{'站数':>6}{'清除':>6}{'站间/TSP':>10}")
    for r in rows:
        print(f"{r[0]:>10}{r[1]:>9.0f}{r[2]:>8.0f}{r[1]-r[2]:>8.0f}{r[3]:>9.0f}"
              f"{r[4]:>6}{r[5]:>6}{r[2]/max(r[3],1):>10.2f}")
    m = lambda k: st.mean(r[k] for r in rows)
    print(f"\n均值：总 {m(1):.0f} m；站间 {m(2):.0f} m（其中最优航路 {m(3):.0f} m，"
          f"超 {m(2)/m(3)-1:+.1%}）；站内 {m(1)-m(2):.0f} m；站数 {m(4):.1f}")


if __name__ == "__main__":
    main()
