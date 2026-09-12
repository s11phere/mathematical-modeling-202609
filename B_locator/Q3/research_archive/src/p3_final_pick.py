"""最终配置选定：把候选配置一次性在四类情景（各 30 局）上跑完并汇总打分。

指标口径与题目表 1 一致：
* **平均定位清除时间** = 逐局 (最后一个源被清除的时刻 / 该局清除个数) 的平均
  （等价于"定位清除总时间 ÷ 被清除个数"的逐局平均）
* T/N(全程) = Σ虚拟时间 / Σ清除个数（把收工后的空转也算进去，用来核对）
* 行程 / 检测 = 逐局平均
"""
from __future__ import annotations

import argparse
import os
import statistics as st
import sys
from dataclasses import replace

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena  # noqa: E402
from p3_robot import load_base  # noqa: E402
from p3_tour import TourConfig, TourRobot  # noqa: E402
from p3_bench import LIVE1, arena_from, outer_annulus, center_cluster  # noqa: E402

CANDIDATES = {
    "A 基线(入口优选+就地清, dist=450)": {},
    "B dist=700": dict(offroute_max_dist_m=700.0),
    "C 关就地清": dict(offroute_clear=False),
    "D 关入口优选": dict(entry_select=False),
    "E 两个都关": dict(offroute_clear=False, entry_select=False),
    "F 入口优选+就地清, dist=900": dict(offroute_max_dist_m=900.0),
    "G 就地清 dist=700 + 关入口优选": dict(offroute_max_dist_m=700.0,
                                          entry_select=False),
}


def mk(scen, seed):
    if scen == "random":
        return MockArena(seed=seed)
    if scen == "annulus":
        return outer_annulus(seed=seed)
    if scen == "center":
        return center_cluster(seed=seed)
    return arena_from(LIVE1, seed=seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--scenarios", default="random,annulus,center,live1")
    a = ap.parse_args()
    base = load_base()
    scens = [s.strip() for s in a.scenarios.split(",") if s.strip()]
    seeds = [a.seed + 100 * i for i in range(a.cases)]

    # 汇总打分：四类情景的平均定位清除时间的平均（等权）
    summary = {}
    hdr = (f"{'配置':<34}" + "".join(f"{s+' 判定/行程':>22}" for s in scens)
           + f"{'均判定':>8}")
    print(hdr)
    print("-" * len(hdr))
    for name, ov in CANDIDATES.items():
        cfg = replace(TourConfig(), **ov)
        cells, scores = [], []
        for scen in scens:
            tt = []
            cl = ns = tr = mm = 0
            full = 0
            for s in seeds:
                rb = TourRobot(mk(scen, s), cfg, base=base, log=None)
                rep = rb.run()
                tt.append(rep["avg_clear_time_s"] or 0.0)
                cl += rep["cleared"]
                ns += rep["n_sources"]
                tr += rep["travel_m"]
                mm += rep["n_measure"]
                full += int(rep["cleared"] == rep["n_sources"])
            act = st.mean(tt)
            scores.append(act)
            cells.append(f"{act:>8.1f} {tr/a.cases:>7.0f} {full:>2}/{a.cases}")
        summary[name] = (st.mean(scores), cells, scores)
        print(f"{name:<34}" + "".join(f"{c:>22}" for c in cells)
              + f"{st.mean(scores):>8.1f}", flush=True)
    best = min(summary.items(), key=lambda kv: kv[1][0])
    print(f"\n=== 最优配置（四情景平均定位清除时间最小）：{best[0]}  "
          f"{best[1][0]:.1f} s ===")
    for scen, sc in zip(scens, best[1][2]):
        print(f"    {scen:<9}{sc:.1f} s")


if __name__ == "__main__":
    main()
