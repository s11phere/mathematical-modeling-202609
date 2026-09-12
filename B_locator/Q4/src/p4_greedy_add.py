"""在"只铺域内 a=1000（12 站）"的基础上，按覆盖收益**逐个加站**，找更细的 Pareto 点。

思路：全覆盖配置的 24 站里，很多站对"定向盲区"的贡献只有一点点（§3.2 的增益分布）。
从 12 站出发贪心补站，能在"站数 ↔ 盲区"上给出比"整圈外环"更细的刻度。

    python src/p4_greedy_add.py
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from p3_arena import R_ARENA, R_RECV_MIN  # noqa: E402
from p4_grid import cov_stats, dir_cov_stats, eval_grid, ring_set, triangular_lattice  # noqa: E402

GX, GY = eval_grid(25.0)


def base_stations():
    return [(0.0, 0.0)] + list(triangular_lattice(1000.0, r_cover=R_ARENA))


def candidates():
    """候选补站：外环 r=1850/1900/1950/2000/2100 上每 10° 一个点。"""
    out = []
    for r in (1800.0, 1850.0, 1900.0, 1950.0, 2000.0, 2100.0):
        for k in range(36):
            a = 2 * math.pi * k / 36
            out.append((r * math.cos(a), r * math.sin(a)))
    return out


def blind(pts):
    _c, _cu = cov_stats(pts, GX, GY)
    dw, db, hd = dir_cov_stats(pts, GX, GY, n_dir=24)
    return db, hd, dw


def main():
    P = base_stations()
    cand = candidates()
    print(f"起点：{len(P)} 站（原点 + 域内三角格网 a=1000）")
    db0, hd0, dw0 = blind(P)
    print(f"  定向盲区 {db0:.2%}  半平面硬伤 {hd0:.2%}  最坏朝向 {dw0:.0f} m\n")
    print(f"{'加站数':>6}{'总站数':>7}{'定向盲区%':>11}{'半平面硬伤%':>13}{'新增站点':>22}")
    for k in range(1, 13):
        best = None
        for q in cand:
            if any(math.hypot(q[0] - p[0], q[1] - p[1]) < 50.0 for p in P):
                continue
            db, hd, _dw = blind(P + [q])
            key = (db, hd)
            if best is None or key < best[0]:
                best = (key, q, db, hd)
        if best is None:
            break
        _key, q, db, hd = best
        P = P + [q]
        print(f"{k:>6}{len(P):>7}{db:>11.2%}{hd:>13.2%}"
              f"   ({q[0]:7.0f},{q[1]:7.0f})  r={math.hypot(*q):.0f}")


if __name__ == "__main__":
    main()
