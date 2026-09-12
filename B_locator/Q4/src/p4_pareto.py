"""覆盖 vs 站数 的 Pareto 前沿（几何口径）。

对每种格网/外环配置，算：
* 站数（决定扫描行程与时间的下界）
* 覆盖半径（到最近站位的最大距离；> 1000 m 即"全向源也可能听不到"）
* 定向盲区（任意朝向都听不到的格点占比；0 才有"必被发现"的保证）
* 骨架航程（按当前绕圈排法算出的扫描航程）

    python src/p4_pareto.py
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
from p4_robot import P4Config, P4GridRobot  # noqa: E402
from p4_run import _DummyArena  # noqa: E402

GX, GY = eval_grid(25.0)


def stations(a, outer, r_max=R_ARENA):
    pts = list(triangular_lattice(a, r_cover=r_max))
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


def tour_km(a, outer):
    """按绕圈排法算骨架航程（km）。"""
    cfg = P4Config(grid_a=a, outer_rings=outer)
    rb = P4GridRobot(_DummyArena(), cfg)
    sk = rb.spiral_tour()
    st = rb.stations
    cur = np.asarray((0.0, 0.0), float)
    d = 0.0
    for si in sk:
        q = np.asarray(st[si], float)
        d += float(np.hypot(*(q - cur)))
        cur = q
    return d / 1000.0, len(st)


CONFIGS = [
    ("当前默认 a=1000 + 外环1850×12", 1000.0, ((1850.0, 12),)),
    ("a=1000 + 外环1850×9", 1000.0, ((1850.0, 9),)),
    ("a=1000 + 外环1850×6", 1000.0, ((1850.0, 6),)),
    ("a=1000 + 外环1800×9", 1000.0, ((1800.0, 9),)),
    ("a=1000 + 外环1800×6", 1000.0, ((1800.0, 6),)),
    ("a=1000 只铺域内（无外环）", 1000.0, ()),
    ("a=1200 + 外环1850×9", 1200.0, ((1850.0, 9),)),
    ("a=1200 + 外环1850×6", 1200.0, ((1850.0, 6),)),
    ("a=1200 只铺域内", 1200.0, ()),
    ("a=1400 + 外环1850×6", 1400.0, ((1850.0, 6),)),
    ("a=1400 只铺域内", 1400.0, ()),
    ("a=1732 只铺域内（覆盖半径顶到 1000）", 1732.0, ()),
]


def main():
    print(f"{'配置':<36}{'站数':>5}{'骨架km':>8}{'覆盖半径':>9}"
          f"{'未覆盖%':>9}{'定向盲区%':>10}")
    print("-" * 78)
    for (lbl, a, outer) in CONFIGS:
        pts = stations(a, outer)
        allp = [(0.0, 0.0)] + pts
        c, cu = cov_stats(allp, GX, GY)
        _dw, db, hd = dir_cov_stats(allp, GX, GY, n_dir=16)
        km, n = tour_km(a, outer)
        print(f"{lbl:<36}{n:>5}{km:>8.1f}{c:>9.0f}{cu:>9.2%}{db:>10.2%}")

    print("\n口径：")
    print("  覆盖半径 = 靶区内任一点到最近站位的最大距离（> 1000 m ⇒ 全向源也可能听不到）")
    print("  定向盲区 = 靶区里【任意朝向都听不到】的格点占比（0 才有'必被发现'的保证）")
    print("  骨架km   = 按当前'由内向外绕圈'排法算出的扫描航程（只算一次单程）")


if __name__ == "__main__":
    main()
