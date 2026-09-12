"""在绕圈航路下重扫 station_min_gain（站次 ↔ 清除率/指标）。

    python src/p4_gain_ab.py --cases 50
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

from p4_arena_ext import directed_case  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="mixed",
                    choices=["mixed", "only"])
    ap.add_argument("--gains", default="90,200,400,800,1500")
    a = ap.parse_args()
    frac = {"mixed": 0.5, "only": 1.0}[a.scenario]
    print(f"场景 {a.scenario}，{a.cases} 局；绕圈航路 + 全覆盖站位（外环1850×12）")
    hdr = (f"{'gain':>7}{'清除率':>9}{'全清':>8}{'平均定位清除':>12}"
           f"{'虚拟':>8}{'行程':>9}{'站次':>7}{'检测':>7}")
    print(hdr)
    print("-" * len(hdr))
    for gs in a.gains.split(","):
        g = float(gs)
        cfg = P4Config(station_min_gain=g)
        tot = cl = full = 0
        vt, tv, stn, ms = [], [], [], []
        for i in range(a.cases):
            arena, _ = directed_case(a.seed + 100 * i, directed_frac=frac)
            rb = P4GridRobot(arena, cfg)
            rep = rb.run()
            tot += rep["n_sources"]
            cl += rep["cleared"]
            vt.append(rep["virtual_time_s"])
            tv.append(rep["travel_m"])
            stn.append(len(rb.visited_stations))
            ms.append(rep["n_measure"])
            if rep["cleared"] == rep["n_sources"]:
                full += 1
        print(f"{g:>7.0f}{cl / tot:>9.4f}{f'{full}/{a.cases}':>8}"
              f"{S.mean(vt) / (cl / a.cases):>12.0f}{S.mean(vt):>8.0f}"
              f"{S.mean(tv):>9.0f}{S.mean(stn):>7.1f}{S.mean(ms):>7.0f}",
              flush=True)
