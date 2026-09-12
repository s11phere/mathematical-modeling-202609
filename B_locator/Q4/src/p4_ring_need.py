"""外环到底需要多少站？覆盖判据 × 站数的关系（决定扫描航程的下限）。"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from p3_arena import R_ARENA  # noqa: E402
from p4_grid import cov_stats, dir_cov_stats, eval_grid, ring_set, triangular_lattice  # noqa: E402

gx, gy = eval_grid(25.0)


def build(a=1000.0, outer=((1850.0, 18),)):
    pts = list(triangular_lattice(a, r_cover=R_ARENA))
    for (r, n) in outer:
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


print(f"{'外环配置':<18}{'站数':>5}{'覆盖半径':>10}{'未覆盖%':>9}"
      f"{'定向盲区%':>10}{'半平面硬伤%':>12}")
print("-" * 66)
for outer in (((1850.0, 18),), ((1850.0, 15),), ((1850.0, 12),), ((1850.0, 9),),
              ((1900.0, 12),), ((1900.0, 9),), ((1950.0, 8),), ()):
    pts = build(outer=outer)
    allp = [(0.0, 0.0)] + pts
    c, cu = cov_stats(allp, gx, gy)
    _dw, db, hd = dir_cov_stats(allp, gx, gy, n_dir=16)
    label = ("外环 " + ",".join(f"r{r:.0f}×{n}" for r, n in outer)) if outer else "无外环"
    print(f"{label:<18}{len(allp):>5}{c:>10.0f}{cu:>9.2%}{db:>10.2%}{hd:>12.2%}")

print("\n说明：'定向盲区%' = 靶区里【任意朝向都听不到】的格点占比，0 才是完整保证。")
print("      外环站数减少会让盲区重新出现（贴边朝外的源又没站点了）。")
