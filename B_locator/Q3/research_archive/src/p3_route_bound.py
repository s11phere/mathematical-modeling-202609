"""结构下界：在"必须覆盖环带"的前提下，最优航路能有多短？

对比三种下界（都是"预知全部源位"的离线最优）：
  L1 = TSP(原点 + 各源位)                                  —— 完全预知、不需覆盖
  L2 = TSP(原点 + 骨架 9@950 + 各源位)                      —— 骨架 + 源位的最优航路
  L3 = L2 + 若干补漏点（贪心补齐环带覆盖）                    —— 可证明完备的最优航路
"""
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

from p3_arena import MockArena, R_ARENA, R_RECV_MIN  # noqa: E402
from p3_bench import LIVE1, LIVE2, arena_from, outer_annulus, center_cluster  # noqa: E402
from p3_tour import TourConfig, TourRobot  # noqa: E402


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


def grid(step=25.0):
    R = R_ARENA
    xs = np.arange(-R, R + 1e-9, step)
    GX, GY = np.meshgrid(xs, xs)
    rr = np.hypot(GX, GY)
    m = (rr <= R + 1e-9) & (rr >= R_RECV_MIN - 1e-9)
    return GX[m], GY[m]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--scenario", default="random")
    a = ap.parse_args()
    gx, gy = grid()
    cfg = TourConfig()
    ring = [(r * math.cos(2 * math.pi * i / cfg.cover_rings[0][1]),
             r * math.sin(2 * math.pi * i / cfg.cover_rings[0][1]))
            for i in range(cfg.cover_rings[0][1])
            for r in (cfg.cover_rings[0][0],)]
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
        src = [(x.x, x.y) for x in aren.sources]
        L1 = tsp(src)
        L2 = tsp(list(ring) + src)
        # L3：在 L2 的点集上贪心补足环带覆盖
        pts = [(0.0, 0.0)] + list(ring) + src
        P = np.asarray(pts, float)
        d = np.sqrt(np.min((gx[:, None] - P[None, :, 0]) ** 2
                           + (gy[:, None] - P[None, :, 1]) ** 2, axis=1))
        left = d > 1000.0
        extra = []
        while left.any():
            best, bp = -1, None
            for r in (900.0, 1000.0, 1100.0, 1200.0, 1300.0, 1400.0):
                for k in range(24):
                    ang = 2 * math.pi * k / 24
                    p = (r * math.cos(ang), r * math.sin(ang))
                    m = ((gx - p[0]) ** 2 + (gy - p[1]) ** 2) <= 1e6
                    gg = int(np.count_nonzero(m & left))
                    if gg > best:
                        best, bp = gg, p
            if bp is None or best <= 0:
                break
            extra.append(bp)
            m = ((gx - bp[0]) ** 2 + (gy - bp[1]) ** 2) <= 1e6
            left = left & ~m
        L3 = tsp(list(ring) + src + extra)
        rb = TourRobot(aren, cfg, base=None, log=None)
        rep = rb.run()
        rows.append((s, rep["travel_m"], L1, L2, L3, len(extra)))
    print(f"{a.scenario}：{a.cases} 局（骨架 {cfg.cover_rings}）")
    print(f"{'seed':>10}{'实际行程':>10}{'L1 源TSP':>10}{'L2 骨架+源':>12}"
          f"{'L3 完备':>10}{'补漏点':>8}")
    for r in rows:
        print(f"{r[0]:>10}{r[1]:>10.0f}{r[2]:>10.0f}{r[3]:>12.0f}{r[4]:>10.0f}{r[5]:>8}")
    m = lambda k: st.mean(r[k] for r in rows)
    print(f"\n均值：实际 {m(1):.0f} m；L1 {m(2):.0f} m；L2 {m(3):.0f} m；L3 {m(4):.0f} m")
    print(f"实际 / L3 = {m(1)/m(4):.2f}；L2 − L1 = {m(3)-m(2):.0f} m（骨架的代价）")


if __name__ == "__main__":
    main()
