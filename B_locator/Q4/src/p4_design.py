"""问题 4 扫描几何的设计报告：比较"三角形格网"与"同心环"的覆盖能力。

    python src/p4_design.py            # 完整报告
    python src/p4_design.py --quick    # 粗网格（快）

报告口径（都在 20 m 细网格上数值计算）：
* ``cov_max``   靶区内任一点到最近停靠点的最大距离（> 1000 m 即有盲区）
* ``dir_worst`` 最坏朝向下"最近可听停靠点"的距离（定向源的关键指标）
* ``dir_bad``   连一个可听停靠点都没有的靶区点占比（几何硬伤）
* ``hard``      连半平面里都没有停靠点的占比（与距离上限无关的硬伤）
* ``tour``      从原点出发走完所有停靠点的最近邻+2-opt 航路长度
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

from p3_arena import R_ARENA, R_RECV_MIN  # noqa: E402
from p4_grid import (  # noqa: E402
    cov_stats, dir_cov_stats, eval_grid, hex_cover_radius, hex_ring_lattice,
    ring_set, tour_len, triangular_lattice,
)


def row(name, pts, gx, gy, n_dir=16):
    c, cu = cov_stats(pts, gx, gy)
    dw, db, hd = dir_cov_stats(pts, gx, gy, n_dir=n_dir)
    tl, _seq = tour_len(pts)
    return {"name": name, "n": len(pts), "cov_max": c, "cov_unc": cu,
            "dir_worst": dw, "dir_bad": db, "hard": hd, "tour": tl}


HDR = (f"{'方案':<34}{'停靠':>5}{'最大未覆盖':>11}{'未覆盖%':>9}"
       f"{'最坏朝向':>10}{'定向盲区%':>10}{'半平面硬伤%':>12}{'航路/m':>9}")


def fmt(r):
    return (f"{r['name']:<34}{r['n']:>5}{r['cov_max']:>11.0f}{r['cov_unc']:>9.2%}"
            f"{r['dir_worst']:>10.0f}{r['dir_bad']:>10.2%}{r['hard']:>12.2%}"
            f"{r['tour']:>9.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=20.0, help="评估网格步长（m）")
    ap.add_argument("--n-dir", type=int, default=16, help="方向采样数")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    step = 40.0 if a.quick else a.step
    gx, gy = eval_grid(step)
    print(f"评估网格：边长 {R_ARENA:.0f} m 的圆域，步长 {step:.0f} m，"
          f"{gx.size} 个点；方向采样 {a.n_dir} 个\n")

    rows = []

    # ---- A. 用户方案：内外两个同心环 -------------------------------------
    for rings in (((1200.0, 12), (1800.0, 12)),
                  ((1100.0, 12), (1700.0, 12)),
                  ((1200.0, 12), (1800.0, 16)),
                  ((1000.0, 10), (1500.0, 12), (1900.0, 16)),
                  ((1250.0, 8),),
                  ((1100.0, 8),)):
        rows.append(row("同心环 " + "+".join(f"r{r:.0f}×{n}" for r, n in rings),
                        ring_set(rings), gx, gy, a.n_dir))

    # ---- B. 三角形格网（用户直觉的严格版本）-----------------------------
    for side in (1000.0, 1200.0, 1400.0, 1600.0, 1700.0, 1732.0):
        pts = triangular_lattice(side, r_cover=R_ARENA)
        rows.append(row(f"三角形格网 a={side:.0f}（域内，{len(pts)} 点）",
                        pts, gx, gy, a.n_dir))

    # ---- C. 三角形格网 + 外侧一圈（救"贴边朝外"的源）--------------------
    for side in (1000.0, 1400.0, 1700.0):
        base = triangular_lattice(side, r_cover=R_ARENA)
        for extra_r, extra_n in ((1850.0, 18), (1950.0, 18), (1950.0, 24),
                                 (2000.0, 18)):
            extra = ring_set(((extra_r, extra_n),))
            pts = base + extra
            rows.append(row(f"三角形 a={side:.0f} + 外环 r{extra_r:.0f}×{extra_n}",
                            pts, gx, gy, a.n_dir))
    # 只保留 r > 1000 的格点（原点已经免费覆盖 r ≤ 1000）
    for side in (1000.0, 1200.0):
        pts = [p for p in triangular_lattice(side, r_cover=R_ARENA)
               if math.hypot(*p) > R_RECV_MIN]
        for extra_r, extra_n in ((1850.0, 18), (1950.0, 18), (1950.0, 24)):
            pp = pts + ring_set(((extra_r, extra_n),))
            rows.append(row(f"环带格网 a={side:.0f} + 外环 r{extra_r:.0f}×{extra_n}",
                            pp, gx, gy, a.n_dir))

    # ---- D. 格网按"六边形环"分组（用户的"内外两个圈"）-------------------
    for side in (1000.0, 1200.0):
        rings = hex_ring_lattice(side, rings=int(math.ceil(2 * R_ARENA / side)))
        pts = [p for ring in rings for p in ring]
        rows.append(row(f"六边形环 a={side:.0f}（{len(rings)} 环，"
                        f"各环 {[len(r) for r in rings]}）", pts, gx, gy, a.n_dir))

    print(HDR)
    print("-" * len(HDR))
    for r in rows:
        print(fmt(r))
    print()
    print("理论覆盖半径（无限格网）：")
    for side in (1000.0, 1200.0, 1400.0, 1600.0, 1700.0, 1732.0):
        print(f"  a={side:>6.0f} m -> a/√3 = {hex_cover_radius(side):>7.1f} m"
              f"{'   ← 超过 1000 m，格点自身不再保证听到' if hex_cover_radius(side) > R_RECV_MIN else ''}")
    print("\n判据：``最大未覆盖 ≤ 1000 m`` ⇒ 全向源必被听到；"
          "``定向盲区 = 0`` ⇒ 任意朝向的定向源必被听到。")


if __name__ == "__main__":
    main()
