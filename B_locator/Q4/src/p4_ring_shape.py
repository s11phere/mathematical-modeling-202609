"""扫描"单圈/双圈"的最优形状：在"站数 ↔ 定向盲区"上找更好的点。

思路：外环站位的作用是覆盖"靶区外圈那一条带"，因为定向源的覆盖半平面条件
（'朝内发射'的源必须从它外侧听）使内圈站位对它们无效。
本脚本枚举 (半径, 点数) 组合，给出每个组合的 站数 / 覆盖半径 / 定向盲区。

    python src/p4_ring_shape.py
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

from p3_arena import R_ARENA  # noqa: E402
from p4_grid import cov_stats, dir_cov_stats, eval_grid, ring_set, triangular_lattice  # noqa: E402

GX, GY = eval_grid(25.0)


def build(a=1000.0, extra=()):
    pts = list(triangular_lattice(a, r_cover=R_ARENA))
    for (r, n) in extra:
        pts += ring_set(((r, n),))
    out, seen = [], set()
    for (x, y) in pts:
        if math.hypot(x, y) < 1.0:
            continue
        k = (round(x, 1), round(y, 1))
        if k in seen:
            continue
        seen.add(k)
        out.append((float(x), float(y)))
    return out


def score(pts):
    allp = [(0.0, 0.0)] + pts
    c, cu = cov_stats(allp, GX, GY)
    _dw, db, hd = dir_cov_stats(allp, GX, GY, n_dir=16)
    return c, cu, db


print("=== A. 单圈（不加外环，只铺域内 a=1000）===")
print(f"{'配置':<26}{'站数':>5}{'覆盖半径':>9}{'定向盲区%':>11}")
p = build()
c, cu, db = score(p)
print(f"{'域内 a=1000':<26}{len(p)+1:>5}{c:>9.0f}{db:>11.2%}")

print("\n=== B. 域内 a=1000 + 一圈补漏环（半径 × 点数）===")
print(f"{'环':<26}{'站数':>5}{'覆盖半径':>9}{'定向盲区%':>11}")
best = []
for r in (1300.0, 1400.0, 1500.0, 1600.0, 1700.0, 1800.0, 1850.0):
    for n in (6, 8, 9, 10, 12, 15, 18):
        p = build(extra=((r, n),))
        c, cu, db = score(p)
        best.append((len(p) + 1, db, r, n, c))
best.sort()
for (ns, db, r, n, c) in best[:22]:
    print(f"{f'r={r:.0f} × {n}':<26}{ns:>5}{c:>9.0f}{db:>11.2%}")

print("\n=== C. 只用一圈（不铺域内，纯环）===")
print(f"{'环':<26}{'站数':>5}{'覆盖半径':>9}{'定向盲区%':>11}")
for r in (1100.0, 1250.0, 1400.0, 1600.0, 1800.0, 1850.0):
    for n in (8, 10, 12, 16):
        p = build(a=1e9, extra=((r, n),))       # a 很大 ⇒ 域内格点为空
        p = [q for q in p if abs(math.hypot(*q) - r) < 1.0]
        c, cu, db = score(p)
        print(f"{f'纯环 r={r:.0f} × {n}':<26}{len(p)+1:>5}{c:>9.0f}{db:>11.2%}")
