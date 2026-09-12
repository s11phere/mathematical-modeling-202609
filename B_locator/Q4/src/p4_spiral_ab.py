"""问题 3 式"绕圈（spiral）" vs "几何最短（tsp）"航路的实测对照。

    python src/p4_spiral_ab.py --cases 30
"""
from __future__ import annotations

import argparse
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


def run(mode, cases, seed, frac, gain=90.0):
    cfg = P4Config(route_mode=mode, station_min_gain=gain)
    tot = cl = full = 0
    vt, tv, mx, nj, stn = [], [], [], [], []
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
        st = rb.stations
        order = []
        for e in rb.events:
            m = e["msg"]
            if m.startswith("站位 ") and "｜待测" in m:
                order.append(int(m.split("站位 ")[1].split("/")[0]))
        cur = np.asarray((0.0, 0.0))
        mm = 0.0
        nb = 0
        for si in order:
            q = np.asarray(st[si], float)
            d = float(np.hypot(*(q - cur)))
            mm = max(mm, d)
            nb += d > 1300
            cur = q
        mx.append(mm)
        nj.append(nb)
    return {"ratio": cl / tot, "full": full, "cases": cases,
            "avg": S.mean(vt) / (cl / cases), "vtime": S.mean(vt),
            "travel": S.mean(tv), "jump": S.mean(mx), "njump": S.mean(nj),
            "stn": S.mean(stn)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="mixed",
                    choices=["mixed", "only", "edge", "omni"])
    a = ap.parse_args()
    frac = {"mixed": 0.5, "only": 1.0, "edge": 0.5, "omni": 0.0}[a.scenario]
    print(f"场景 {a.scenario}，{a.cases} 局（seed {a.seed}+100i）")
    print(f"{'航路':<22}{'清除率':>8}{'全清':>8}{'平均定位清除':>12}"
          f"{'虚拟':>8}{'行程':>9}{'站间单跳':>10}{'长跳/局':>9}{'站次':>7}")
    print("-" * 96)
    for lbl, mode in (("tsp（几何最短）", "tsp"),
                      ("spiral（问题3式绕圈）", "spiral")):
        r = run(mode, a.cases, a.seed, frac)
        print(f"{lbl:<22}{r['ratio']:>8.4f}{f'{r[chr(102)+chr(117)+chr(108)+chr(108)]}/{r[chr(99)+chr(97)+chr(115)+chr(101)+chr(115)]}':>8}"
              f"{r['avg']:>12.0f}{r['vtime']:>8.0f}{r['travel']:>9.0f}"
              f"{r['jump']:>10.0f}{r['njump']:>9.2f}{r['stn']:>7.1f}", flush=True)
