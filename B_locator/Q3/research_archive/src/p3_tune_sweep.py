"""扫圈策略的参数扫描：找一组"可证明完备 + 指标最好"的配置。

用法：
    python src/p3_tune_sweep.py [--cases 12]
"""
from __future__ import annotations

import argparse
import itertools
import os
import statistics as st
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from p3_arena import MockArena  # noqa: E402
from p3_robot import load_base  # noqa: E402
from p3_sweep import SweepConfig, SweepRobot  # noqa: E402

SEEDS = [20260913 + 100 * i for i in range(12)]


def run(cfg, seeds, base):
    rows = []
    for s in seeds:
        a = MockArena(seed=s)
        rb = SweepRobot(a, cfg, base=base, log=None)
        t0 = time.time()
        rep = rb.run()
        rep["_wall"] = time.time() - t0
        rows.append(rep)
    cl = sum(r["cleared"] for r in rows)
    tot = sum(r["n_sources"] for r in rows)
    tm = [r["avg_clear_time_s"] for r in rows if r["avg_clear_time_s"]]
    return {
        "ratio": cl / tot, "cleared": st.mean(r["cleared"] for r in rows),
        "avg": st.mean(tm) if tm else 0.0,
        "vt": st.mean(r["virtual_time_s"] for r in rows),
        "meas": st.mean(r["n_measure"] for r in rows),
        "cov": st.mean(r["coverage"] for r in rows),
        "unc": st.mean(r["max_uncovered_dist_m"] for r in rows),
        "rounds": st.mean(r["n_scan_rounds"] for r in rows),
        "wall": st.mean(r["_wall"] for r in rows),
        "complete": sum(1 for r in rows if r["max_uncovered_dist_m"] <= 1000.0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=12)
    args = ap.parse_args()
    seeds = SEEDS[:args.cases]
    base = load_base()
    print(f"共 {len(seeds)} 局；基线（现行策略）见 review/P3-design.md §5\n")

    grid = {
        "sweep_rings": [((1400.0, 8),), ((1400.0, 8), (1250.0, 12)),
                        ((1250.0, 8),), ((1550.0, 8),)],
        "clear_detour_max_m": [0.0, 350.0, 700.0],
        "measured_revisit_gap_m": [200.0, 400.0, 700.0],
    }
    keys = list(grid)
    hdr = (f"{'rings':<14}{'detour':>8}{'gap':>6}{'清除率':>8}{'平均清除':>9}"
           f"{'虚拟时间':>10}{'检测':>7}{'覆盖':>7}{'未覆盖/m':>10}{'轮':>5}{'完备局':>7}{'实跑/s':>8}")
    print(hdr)
    print("-" * len(hdr))
    best = None
    for combo in itertools.product(*(grid[k] for k in keys)):
        kw = dict(zip(keys, combo))
        cfg = SweepConfig(**kw)
        r = run(cfg, seeds, base)
        rings_tag = "+".join(str(int(x[0])) for x in kw["sweep_rings"])
        print(f"{rings_tag:<14}{kw['clear_detour_max_m']:>8.0f}"
              f"{kw['measured_revisit_gap_m']:>6.0f}{r['ratio']:>8.3f}{r['avg']:>9.1f}"
              f"{r['vt']:>10.0f}{r['meas']:>7.0f}{r['cov']:>7.3f}{r['unc']:>10.0f}"
              f"{r['rounds']:>5.1f}{r['complete']:>4d}/{len(seeds):<2}{r['wall']:>8.2f}",
              flush=True)
        # 只在"全部完备"的配置里，按平均定位清除时间挑最好
        score = (r["complete"] == len(seeds), -r["avg"])
        if best is None or score > best[0]:
            best = (score, kw, r)
    print("\n最优（要求全部完备，再看平均定位清除时间）：")
    print("  ", best[1], {k: round(v, 3) if isinstance(v, float) else v
                          for k, v in best[2].items()})


if __name__ == "__main__":
    main()
