"""量化扫描航线的绕路：当前"骨架顺序" vs 几种就近进入的排法。

    python src/p4_route_audit.py
"""
from __future__ import annotations

import math
import os
import statistics as S
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from p4_arena_ext import directed_case  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402
from p4_run import _DummyArena  # noqa: E402


def tour_len(seq, stations, start=(0.0, 0.0)):
    cur = np.asarray(start, float)
    d = 0.0
    for si in seq:
        p = np.asarray(stations[si], float)
        d += float(np.hypot(*(p - cur)))
        cur = p
    return d


def nn_from(pts, start):
    """给定点集与起点，最近邻排序，返回 (顺序下标, 长度)。"""
    left = list(range(len(pts)))
    cur = np.asarray(start, float)
    seq, d = [], 0.0
    while left:
        j = min(left, key=lambda i: float(np.hypot(*(np.asarray(pts[i], float) - cur))))
        d += float(np.hypot(*(np.asarray(pts[j], float) - cur)))
        cur = np.asarray(pts[j], float)
        seq.append(j)
        left.remove(j)
    return seq, d


def two_opt(pts, seq, start):
    def cost(order):
        cur = np.asarray(start, float)
        d = 0.0
        for i in order:
            d += float(np.hypot(*(np.asarray(pts[i], float) - cur)))
            cur = np.asarray(pts[i], float)
        return d
    best = cost(seq)
    improved = True
    while improved:
        improved = False
        for i in range(len(seq) - 1):
            for j in range(i + 1, len(seq)):
                cand = seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]
                c = cost(cand)
                if c < best - 1e-9:
                    seq, best, improved = cand, c, True
    return seq, best


def main():
    cfg = P4Config()
    rb = P4GridRobot(_DummyArena(), cfg)
    st = rb.stations
    n = len(st)
    radii = [math.hypot(*p) for p in st]
    bands = sorted({round(r / (cfg.grid_a * 0.4)) for r in radii})
    print(f"站位 {n} 个；半径分布：")
    for b in bands:
        idx = [i for i in range(n) if round(radii[i] / (cfg.grid_a * 0.4)) == b]
        print(f"  档 {b}：半径 {min(radii[i] for i in idx):6.0f}–"
              f"{max(radii[i] for i in idx):6.0f} m，{len(idx):2d} 个")

    # 1) 当前实现（骨架顺序）
    sk = rb.scan_skeleton()
    cur_len = tour_len(sk, st)
    # 2) 同一顺序的最后 20 个站之间是否有跨档往返
    cross = 0
    for a, b in zip(sk, sk[1:]):
        ra, rbb = radii[a], radii[b]
        if abs(ra - rbb) > 400.0:
            cross += 1
    print(f"\n当前骨架顺序：{len(sk)} 站，直线航程 {cur_len:.0f} m，"
          f"其中跨半径档（>400 m）的相邻跳 {cross} 次")

    # 3) 按档就近进入：档间按半径递增，档内最近邻 + 2-opt
    seq2, total2 = [], 0.0
    cur = np.asarray((0.0, 0.0), float)
    for b in bands:
        idx = [i for i in range(n) if round(radii[i] / (cfg.grid_a * 0.4)) == b]
        pts = [st[i] for i in idx]
        s, d = nn_from(pts, cur)
        s, d = two_opt(pts, s, cur)
        seq2 += [idx[i] for i in s]
        total2 += d
        cur = np.asarray(st[seq2[-1]], float)
    cross2 = sum(1 for a, b in zip(seq2, seq2[1:])
                 if abs(radii[a] - radii[b]) > 400.0)
    print(f"按档就近进入（档内 NN+2opt）：{len(seq2)} 站，直线航程 {total2:.0f} m，"
          f"跨档跳 {cross2} 次")

    # 4) 纯最近邻（不分档，只看距离）
    pts = [st[i] for i in range(n)]
    s3, d3 = nn_from(pts, (0.0, 0.0))
    s3, d3 = two_opt(pts, s3, (0.0, 0.0))
    print(f"纯最近邻 + 2-opt（不分档）  ：{len(s3)} 站，直线航程 {d3:.0f} m")

    # 5) 实测：现在一局的扫描段行程
    print("\n实测（20 局）：")
    scan_travel, tot_travel = [], []
    for i in range(20):
        arena, _ = directed_case(20260914 + 100 * i)
        r = P4GridRobot(arena, P4Config())
        rep = r.run()
        # 按动作类型拆：扫描停在站上做的那一串 measure 的位移
        acts = [a for a in arena.actions if "x" in a]
        prev = np.asarray((0.0, 0.0), float)
        d_scan = d_probe = 0.0
        for a in acts:
            p = np.asarray((a["x"], a["y"]), float)
            dd = float(np.hypot(*(p - prev)))
            if a.get("kind") == "clear":
                d_probe += dd
            else:
                d_scan += dd
            prev = p
        scan_travel.append(d_scan)
        tot_travel.append(rep["travel_m"])
    print(f"  扫描段（measure 段位移）均值 {S.mean(scan_travel):.0f} m")
    print(f"  总行程均值              {S.mean(tot_travel):.0f} m")


if __name__ == "__main__":
    main()
