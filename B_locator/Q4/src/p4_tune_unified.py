"""统一航路的参数扫描（边扫描边清理的"绕行激进度"）。

    python src/p4_tune_unified.py --cases 20
    python src/p4_tune_unified.py --cases 20 --scenario only
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

GRIDS = [
    ("detour 0（只在第二遍清）", {"interleave_detour_max_m": 0.0}),
    ("detour 300", {"interleave_detour_max_m": 300.0}),
    ("detour 500", {"interleave_detour_max_m": 500.0}),
    ("detour 700（默认）", {"interleave_detour_max_m": 700.0}),
    ("detour 1100", {"interleave_detour_max_m": 1100.0}),
    ("detour 1e9（听到就绕）", {"interleave_detour_max_m": 1e9}),
    ("探测半径 60 m", {"interleave_probe_m": 60.0}),
    ("探测半径 120 m", {"interleave_probe_m": 120.0}),
    ("定位门限 70 m", {"interleave_loc_radius_m": 70.0}),
    ("定位门限 160 m", {"interleave_loc_radius_m": 160.0}),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="mixed", choices=["mixed", "only", "edge", "omni"])
    a = ap.parse_args()
    frac = {"mixed": 0.5, "only": 1.0, "edge": 0.5, "omni": 0.0}[a.scenario]

    print(f"场景 {a.scenario}，{a.cases} 局（seed {a.seed}+100i），统一航路（边扫边清）")
    hdr = (f"{'配置':<26}{'清除率':>8}{'全清':>7}{'平均定位清除':>13}"
           f"{'虚拟':>8}{'行程':>9}{'动作':>7}{'墙钟':>7}")
    print(hdr)
    print("-" * len(hdr))
    for (label, over) in GRIDS:
        cfg = P4Config(unified=True, **over)
        t0 = time.time()
        tot = cl = full = 0
        vt, tv, ac = [], [], []
        for i in range(a.cases):
            arena, _ = directed_case(a.seed + 100 * i, directed_frac=frac)
            rb = P4GridRobot(arena, cfg)
            rep = rb.run()
            tot += rep["n_sources"]
            cl += rep["cleared"]
            vt.append(rep["virtual_time_s"])
            tv.append(rep["travel_m"])
            ac.append(rep["n_measure"] + rep["n_clear"])
            if rep["cleared"] == rep["n_sources"]:
                full += 1
        print(f"{label:<26}{cl / tot:>8.4f}{f'{full}/{a.cases}':>7}"
              f"{S.mean(vt) / (cl / a.cases):>13.0f}{S.mean(vt):>8.0f}"
              f"{S.mean(tv):>9.0f}{S.mean(ac):>7.0f}{time.time() - t0:>7.1f}",
              flush=True)


if __name__ == "__main__":
    main()
