"""站点方案评估：覆盖完备性 × 航程 × 估算虚拟时间。

    python src/p4_eval.py --step 20 --n-dir 24
"""
from __future__ import annotations

import argparse
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

from p3_arena import R_ARENA, R_RECV_MIN, V_ROBOT  # noqa: E402
from p4_grid import (  # noqa: E402
    cov_stats, dir_cov_stats, eval_grid, hex_cover_radius, ring_set,
    triangular_lattice, tour_len,
)


def stations_for(a, outer=((1850.0, 18),), r_max=R_ARENA):
    pts = list(triangular_lattice(a, r_cover=r_max))
    for (r, n) in outer:
        for i in range(int(n)):
            ang = 2.0 * math.pi * i / float(n)
            pts.append((r * math.cos(ang), r * math.sin(ang)))
    out, seen = [], set()
    for (x, y) in pts:
        if math.hypot(x, y) < 1.0:
            continue
        k = (round(x, 1), round(y, 1))
        if k in seen:
            continue
        seen.add(k)
        out.append((float(x), float(y)))
    out.sort(key=lambda p: (math.hypot(*p), math.atan2(p[1], p[0]) % (2 * math.pi)))
    return out


def spiral_tour_len(pts, start=(0.0, 0.0)):
    """按"半径分层的最近邻"走（由内向外螺旋）时的航程。"""
    ordered = sorted(pts, key=lambda p: (round(math.hypot(*p) / 500.0),
                                         math.atan2(p[1], p[0]) % (2 * math.pi)))
    d = 0.0
    cur = np.asarray(start, float)
    for p in ordered:
        q = np.asarray(p, float)
        d += float(np.hypot(*(q - cur)))
        cur = q
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=20.0)
    ap.add_argument("--n-dir", type=int, default=24)
    a = ap.parse_args()
    gx, gy = eval_grid(a.step)
    print(f"评估网格 {gx.size} 点（步长 {a.step:.0f} m，方向 {a.n_dir} 个）")
    hdr = (f"{'方案':<30}{'站数':>5}{'覆盖半径':>9}{'未覆盖%':>9}"
           f"{'定向盲区%':>10}{'NN航程/m':>10}{'螺旋航程/m':>11}{'估算虚拟/s':>11}")
    print(hdr)
    print("-" * len(hdr))
    for a_side, outer in ((1000.0, ((1850.0, 18),)),
                          (1000.0, ()),
                          (1200.0, ((1850.0, 18),)),
                          (1400.0, ((1850.0, 18),)),
                          (1400.0, ((1900.0, 20),)),
                          (1600.0, ((1850.0, 18),)),
                          (1732.0, ((1850.0, 18),)),
                          (1732.0, ((2000.0, 24),))):
        pts = stations_for(a_side, outer)
        allp = [(0.0, 0.0)] + pts
        c, cu = cov_stats(allp, gx, gy)
        dw, db, hd = dir_cov_stats(allp, gx, gy, n_dir=a.n_dir)
        nn, _ = tour_len(allp)
        sp = spiral_tour_len(pts)
        # 估算虚拟时间：走完所有站 + 每站测 12 个频道（空频道占多数时的估计）
        vtime = sp / V_ROBOT + len(allp) * 12 * 6.0
        name = f"a={a_side:.0f}" + (f"+外环{outer[0][0]:.0f}×{outer[0][1]}" if outer else "")
        print(f"{name:<30}{len(allp):>5}{c:>9.0f}{cu:>9.2%}{db:>10.2%}"
              f"{nn:>10.0f}{sp:>11.0f}{vtime:>11.0f}")
    print("\n注：'定向盲区%' = 靶区里【任意朝向都听不到】的格点占比（0 才是完整保证）；")
    print("    '估算虚拟/s' = 螺旋航程/5 + 站数×12×6（每站测 12 个频道的粗略模型）。")


if __name__ == "__main__":
    main()
