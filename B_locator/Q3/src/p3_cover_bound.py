"""覆盖下界分析：若"预知全部源位、且在每个源位上测过一次"，
还需要多少个额外检测点才能覆盖环带？

    python src/p3_cover_bound.py --cases 30
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


def grid(step=25.0):
    R = R_ARENA
    xs = np.arange(-R, R + 1e-9, step)
    GX, GY = np.meshgrid(xs, xs)
    rr = np.hypot(GX, GY)
    m = (rr <= R + 1e-9) & (rr >= R_RECV_MIN - 1e-9)
    return GX[m], GY[m]


def dmin(gx, gy, P):
    P = np.asarray(P, float)
    if P.size == 0:
        return np.full(gx.size, np.inf)
    d2 = (gx[:, None] - P[None, :, 0]) ** 2 + (gy[:, None] - P[None, :, 1]) ** 2
    return np.sqrt(np.min(d2, axis=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--scenario", default="random")
    a = ap.parse_args()
    gx, gy = grid()
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
        P = [(0.0, 0.0)] + [(x.x, x.y) for x in aren.sources]
        d = dmin(gx, gy, P)
        # 贪心补点：从环带格点里选（半径 900-1300）
        cand = []
        for r in (900.0, 1000.0, 1100.0, 1200.0, 1300.0, 1400.0):
            for k in range(36):
                ang = 2 * math.pi * k / 36
                cand.append((r * math.cos(ang), r * math.sin(ang)))
        cand = np.asarray(cand, float)
        left = d > 1000.0
        extra = 0
        while left.any():
            best, bi = -1, -1
            for j in range(cand.shape[0]):
                m = ((gx - cand[j, 0]) ** 2 + (gy - cand[j, 1]) ** 2) <= 1e6
                g = int(np.count_nonzero(m & left))
                if g > best:
                    best, bi = g, j
            if best <= 0:
                break
            extra += 1
            p = cand[bi]
            m = ((gx - p[0]) ** 2 + (gy - p[1]) ** 2) <= 1e6
            left = left & ~m
        rows.append((s, len(aren.sources), float(d.max()), extra,
                     float((d > 1000).mean())))
    print(f"{a.scenario}：{a.cases} 局")
    print(f"{'seed':>10}{'源数':>6}{'源位覆盖最大未覆盖':>20}{'还需补点':>10}{'未覆盖占比':>12}")
    for r in rows:
        print(f"{r[0]:>10}{r[1]:>6}{r[2]:>20.0f}{r[3]:>10}{r[4]:>12.1%}")
    print(f"\n均值：源位覆盖最大未覆盖 {st.mean(r[2] for r in rows):.0f} m；"
          f"平均还需补 {st.mean(r[3] for r in rows):.2f} 个检测点；"
          f"初始未覆盖占比 {st.mean(r[4] for r in rows):.1%}")


if __name__ == "__main__":
    main()
