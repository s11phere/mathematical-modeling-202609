"""扫参：扫描途中"顺路清除"的绕行上限 clear_detour_max_m 对指标的影响。

    python src/p4_tune_detour.py --cases 20
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


def run(values, cases, seed, scenario):
    print(f"{'detour':>8}{'清除率':>9}{'全清':>7}{'平均定位清除':>13}"
          f"{'虚拟':>8}{'行程':>9}{'顺路清除次数':>13}{'墙钟':>7}")
    print("-" * 74)
    for v in values:
        cfg = P4Config(clear_detour_max_m=float(v))
        t0 = time.time()
        tot = cl = full = 0
        vt, tv, en = [], [], []
        for i in range(cases):
            arena, _ = directed_case(seed + 100 * i,
                                     directed_frac=1.0 if scenario == "only" else 0.5)
            rb = P4GridRobot(arena, cfg)
            rep = rb.run()
            tot += rep["n_sources"]
            cl += rep["cleared"]
            vt.append(rep["virtual_time_s"])
            tv.append(rep["travel_m"])
            en.append(sum(1 for e in rb.events if "顺路清除" in e["msg"]))
            if rep["cleared"] == rep["n_sources"]:
                full += 1
        print(f"{float(v):>8.0f}{cl / tot:>9.4f}{full:>4}/{cases:<3}"
              f"{S.mean(vt) / (cl / cases):>13.0f}{S.mean(vt):>8.0f}"
              f"{S.mean(tv):>9.0f}{S.mean(en):>13.1f}{time.time() - t0:>7.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="mixed", choices=["mixed", "only"])
    ap.add_argument("--values", default="0,150,300,450,650,900")
    a = ap.parse_args()
    vals = [float(x) for x in a.values.split(",") if x.strip()]
    run(vals, a.cases, a.seed, a.scenario)
