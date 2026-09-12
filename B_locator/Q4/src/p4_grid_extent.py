"""把三角格网**整体往外铺**（单一格网，r_max 扫描）——比"格网 + 外环"更简洁的候选。

    python src/p4_grid_extent.py
"""
from __future__ import annotations

import argparse
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

from p3_arena import R_ARENA  # noqa: E402
from p4_arena_ext import directed_case  # noqa: E402
from p4_grid import cov_stats, dir_cov_stats, eval_grid, triangular_lattice  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402

GX, GY = eval_grid(25.0)


def geom(a, r_max):
    pts = [(0.0, 0.0)] + list(triangular_lattice(a, r_cover=r_max))
    c, cu = cov_stats(pts, GX, GY)
    _dw, db, hd = dir_cov_stats(pts, GX, GY, n_dir=24)
    return len(pts), c, db, hd


def sim(a, r_max, cases, seed=20260914, frac=0.5):
    cfg = P4Config(grid_a=a, outer_rings=(), grid_r_max=r_max)
    tot = cl = full = 0
    vt, tv, stn = [], [], []
    for i in range(cases):
        arena, _ = directed_case(seed + 100 * i, directed_frac=frac)
        rb = P4GridRobot(arena, cfg)
        rep = rb.run()
        tot += rep["n_sources"]
        cl += rep["cleared"]
        vt.append(rep["virtual_time_s"])
        tv.append(rep["travel_m"])
        stn.append(len(rb.visited_stations))
        if rep["cleared"] == rep["n_sources"]:
            full += 1
    return {"ratio": cl / tot, "full": full, "cases": cases,
            "avg": S.mean(vt) / (cl / cases), "vtime": S.mean(vt),
            "travel": S.mean(tv), "stn": S.mean(stn)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--sim", action="store_true", help="顺带跑模拟器（慢）")
    a = ap.parse_args()
    print(f"{'配置':<28}{'站数':>5}{'覆盖半径':>9}{'盲区%':>9}{'硬伤%':>9}")
    print("-" * 60)
    todo = [(1000.0, 1800.0), (1000.0, 1900.0), (1000.0, 2000.0),
            (1000.0, 2100.0), (1000.0, 2200.0), (1000.0, 2400.0),
            (1000.0, 2600.0)]
    for (a_, rm) in todo:
        n, c, db, hd = geom(a_, rm)
        print(f"{f'a={a_:.0f} r_max={rm:.0f}':<28}{n:>5}{c:>9.0f}"
              f"{db:>9.2%}{hd:>9.2%}")
    if a.sim:
        print(f"\n{'配置':<28}{'清除率':>8}{'全清':>9}{'平均定位清除':>12}"
              f"{'虚拟':>8}{'行程':>9}{'站次':>7}")
        print("-" * 82)
        for (a_, rm) in todo:
            r = sim(a_, rm, a.cases)
            print(f"{f'a={a_:.0f} r_max={rm:.0f}':<28}{r['ratio']:>8.4f}"
                  f"{f'{r[chr(102)+chr(117)+chr(108)+chr(108)]}/{r[chr(99)+chr(97)+chr(115)+chr(101)+chr(115)]}':>9}"
                  f"{r['avg']:>12.0f}{r['vtime']:>8.0f}{r['travel']:>9.0f}"
                  f"{r['stn']:>7.1f}", flush=True)
