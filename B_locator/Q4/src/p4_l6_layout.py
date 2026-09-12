"""L6 档（a=1100，无外环）的布局：站位坐标、覆盖半径、以及漏源的方位。

    python src/p4_l6_layout.py
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
from p4_grid import cov_stats, dir_cov_stats, eval_grid, triangular_lattice  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402
from p4_run import _DummyArena  # noqa: E402

cfg = P4Config(grid_a=1100.0, outer_rings=())
rb = P4GridRobot(_DummyArena(), cfg)
pts = [(0.0, 0.0)] + list(rb.stations)
print(f"L6 档：a={cfg.grid_a:.0f} m，outer_rings={cfg.outer_rings}")
print(f"格点集合 = 原点 + {len(rb.stations)} 个格点 = {len(pts)} 站\n")
print(f"{'#':>3}{'x (m)':>10}{'y (m)':>10}{'极径':>8}{'极角':>9}")
for k, (x, y) in enumerate(pts):
    print(f"{k:>3}{x:>10.1f}{y:>10.1f}{math.hypot(x, y):>8.0f}"
          f"{math.degrees(math.atan2(y, x)) % 360:>9.1f}")

GX, GY = eval_grid(20.0)
c, cu = cov_stats(pts, GX, GY)
_dw, db, hd = dir_cov_stats(pts, GX, GY, n_dir=24)
print(f"\n覆盖半径（靶区内任一点到最近站位的最大距离）= {c:.0f} m"
      f"   [判据 ≤ 1000 ⇒ 全向源必被听到]")
print(f"未覆盖占比 {cu:.2%}；定向盲区 {db:.2%}；半平面硬伤 {hd:.2%}")

# 每个站的服务区域（Voronoi）在靶区内的面积占比 —— 说明"分布均匀"
D = np.sqrt(((GX[:, None] - np.array([p[0] for p in pts])[None, :]) ** 2
             + (GY[:, None] - np.array([p[1] for p in pts])[None, :]) ** 2))
who = np.argmin(D, axis=1)
print("\n各站的 Voronoi 服务面积占比（靶区网格点数）：")
for k, (x, y) in enumerate(pts):
    share = float(np.count_nonzero(who == k)) / who.size
    print(f"  站{k} ({x:7.1f},{y:7.1f})  r={math.hypot(x, y):5.0f}  "
          f"服务面积 {share:6.2%}")

# 扫描航线长度（绕圈排法）
sk = rb.spiral_tour()
st = rb.stations
cur = np.asarray((0.0, 0.0), float)
d = 0.0
seq = []
for si in sk:
    q = np.asarray(st[si], float)
    step = float(np.hypot(*(q - cur)))
    d += step
    seq.append((int(si), round(step), round(float(np.hypot(*q)))))
    cur = q
print(f"\n绕圈航线（站号顺序）：{list(sk)}")
print(f"  每跳（距离 m, 该站半径 m）= {[(s[1], s[2]) for s in seq]}")
print(f"  骨架航程 = {d:.0f} m")
