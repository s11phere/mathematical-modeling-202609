"""live 局的对照实验：把 live 反算出的真源搬到 mock 上复现（默认配置）。

live（2026-09-11 15:14）实测真源（由 ±1° 交会区域反算）：
    ch2 (937,-782) ch5 (363,418) ch6 (-939,-1491) ch9 (1652,-112) ch10 (1606,-590)
    ch11 (-591,-82) ch13 (18,-197) ch14 (470,-1292) ch18 (1024,1242) ch20 (-316,241)

用法：
    python src/p3_exp_outer.py [--cases 30]
"""
from __future__ import annotations

import argparse
import math
import os
import statistics as st
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from p3_arena import MockArena, MockSource  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402

LIVE_SOURCES = [(2, 937.0, -782.0), (5, 363.0, 418.0), (6, -939.0, -1491.0),
                (9, 1652.0, -112.0), (10, 1606.0, -590.0), (11, -591.0, -82.0),
                (13, 18.0, -197.0), (14, 470.0, -1292.0), (18, 1024.0, 1242.0),
                (20, -316.0, 241.0)]


def live_like_arena(seed=0, r_recv=1400.0, budget=360000.0):
    return MockArena(seed=seed,
                     sources=[MockSource(c, x, y, r_recv) for (c, x, y) in LIVE_SOURCES],
                     budget_s=budget)


def outer_annulus_arena(seed=0, n=12, r_lo=1300.0, r_hi=1800.0,
                        r_recv_lo=1000.0, r_recv_hi=1500.0, budget=360000.0):
    """把源按面积均匀放在外圈环带里（对"发现"最不利的几何）。"""
    rng = np.random.default_rng(seed)
    chans = rng.choice(np.arange(1, 21), size=n, replace=False)
    out = []
    for ch in chans:
        r = math.sqrt(rng.uniform(r_lo ** 2, r_hi ** 2))
        a = rng.uniform(0, 2 * math.pi)
        out.append(MockSource(int(ch), r * math.cos(a), r * math.sin(a),
                              float(rng.uniform(r_recv_lo, r_recv_hi))))
    return MockArena(seed=seed, sources=out, budget_s=budget)


def report(tag, reps):
    cl = [r["cleared"] for r in reps]
    tot = [r["n_sources"] for r in reps]
    tm = [r["avg_clear_time_s"] for r in reps if r["avg_clear_time_s"]]
    print(f"{tag:<28} 清除 {sum(cl):>4}/{sum(tot):<4} 比例 {sum(cl)/sum(tot):.3f}  "
          f"虚拟时间 {st.mean(r['virtual_time_s'] for r in reps):8.0f}s  "
          f"平均定位清除时间 {st.mean(tm):7.1f}s  "
          f"检测 {st.mean(r['n_measure'] for r in reps):6.1f}  "
          f"行程 {st.mean(r['mock_stats']['travel_m'] for r in reps):7.0f}m  "
          f"拒动 {sum(r['n_rejected'] for r in reps)}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    args = ap.parse_args()
    base = load_base()

    print("--- 场景 A：完全复刻 live 那一局的 10 个源（r 145~1758 m）---")
    report("live 复刻（1 局）", [P3Robot(live_like_arena(), P3Config(), base=base,
                                         log=None).run()])
    print("      （live 实测：虚拟 6914 s、平均 642.9 s、检测 384、行程 22152 m）")

    print(f"\n--- 场景 B：12 个源全在外圈环带 r∈[1300,1800]（最坏几何，3 局）---")
    report("外圈环带", [P3Robot(outer_annulus_arena(seed=100 + s), P3Config(),
                                base=base, log=None).run() for s in range(3)])

    print(f"\n--- 场景 C：常规随机 {args.cases} 局（seed 20260913+100i）---")
    report("随机（默认口径）",
           [P3Robot(MockArena(seed=20260913 + 100 * i), P3Config(), base=base,
                    log=None).run() for i in range(args.cases)])


if __name__ == "__main__":
    main()
