"""覆盖 ↔ 用时的最终 Pareto 前沿（模拟器口径，多种子大批量）。

    python src/p4_pareto_sim.py --cases 100
    python src/p4_pareto_sim.py --cases 100 --scenario only
"""
from __future__ import annotations

import argparse
import os
import statistics as S
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p4_arena_ext import directed_case  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402

# (名字, 站数, 盲区%, 配置覆盖)
ROWS = [
    ("P0 全覆盖（现默认 24 站）", 24, 0.00, dict(outer_rings=((1850.0, 12),))),
    ("P1 外环 1900×10", 23, 0.66, dict(outer_rings=((1900.0, 10),))),
    ("P2 外环 1900×6（=格网铺到2000）", 20, 1.91, dict(outer_rings=((1900.0, 6),))),
    ("P3 只铺域内 a=1000（12 站）", 13, 38.66, dict(outer_rings=())),
]


def sim(name, nst, blind, over, cases, seed, frac):
    cfg = P4Config(**over)
    tot = cl = full = 0
    vt, tv, stn = [], [], []
    t0 = time.time()
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
    return {"name": name, "n": nst, "blind": blind, "ratio": cl / tot,
            "full": full, "cases": cases,
            "avg": S.mean(vt) / (cl / cases) if cl else 0.0,
            "vtime": S.mean(vt), "travel": S.mean(tv), "stn": S.mean(stn),
            "miss": tot - cl, "wall": time.time() - t0}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="mixed",
                    choices=["mixed", "only", "edge", "omni"])
    a = ap.parse_args()
    frac = {"mixed": 0.5, "only": 1.0, "edge": 0.5, "omni": 0.0}[a.scenario]
    print(f"场景 {a.scenario}（定向占比 {frac}），{a.cases} 局，seed {a.seed}+100i\n")
    hdr = (f"{'配置':<30}{'站数':>5}{'盲区%':>8}{'清除率':>8}{'全清':>9}"
           f"{'漏源':>5}{'平均定位清除':>12}{'虚拟':>8}{'行程':>9}{'站次':>7}")
    print(hdr)
    print("-" * len(hdr))
    for (name, nst, blind, over) in ROWS:
        r = sim(name, nst, blind, over, a.cases, a.seed, frac)
        full = f"{r['full']}/{r['cases']}"
        print(f"{name:<30}{nst:>5}{blind:>8.2f}{r['ratio']:>8.4f}{full:>9}"
              f"{r['miss']:>5}{r['avg']:>12.0f}{r['vtime']:>8.0f}"
              f"{r['travel']:>9.0f}{r['stn']:>7.1f}", flush=True)
    print("\n注：'盲区%' 是几何口径（任意朝向都听不到的格点占比）；")
    print("    实际漏源还取决于源恰好落在哪、朝向如何，所以清除率与盲区不是线性关系。")
