"""挑出"表现差"的案例并画出路径对照（默认 vs 边绕边清）。

用法：
    python src/p3_pick_worst.py                 # 找最差的 4 局并画图
    python src/p3_pick_worst.py --metric gap    # 按"与默认的差距"排序
    python src/p3_pick_worst.py --seeds 20260913,20261013
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from p3_arena import MockArena  # noqa: E402
from p3_robot import load_base  # noqa: E402
from p3_sweep import SweepConfig, SweepRobot  # noqa: E402

sys.path.insert(0, _HERE)
from p3_paths import draw_path, legend_handles, OUT  # noqa: E402

ROOT = os.path.normpath(os.path.join(_HERE, ".."))
OUTDIR = os.path.join(ROOT, "out", "p3_worst")


def run_one(seed, **kw):
    arena = MockArena(seed=seed)
    rb = SweepRobot(arena, SweepConfig(**kw), base=load_base(), log=None)
    rep = rb.run()
    rep["truth"] = arena.truth()
    rep["mock_stats"] = arena.stats
    return arena, rb, rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="")
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--metric", choices=["worst", "gap"], default="worst",
                    help="worst=按清除率/时间最差；gap=按'边绕边清比默认差得最多'")
    ap.add_argument("--top", type=int, default=4)
    args = ap.parse_args()

    if args.seeds:
        seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    else:
        seeds = [20260913 + 100 * i for i in range(args.cases)]

    rows = []
    for s in seeds:
        _a, _r, base_rep = run_one(s, onlap_clear=False)
        _a, _r, onl_rep = run_one(s, onlap_clear=True)
        rows.append({
            "seed": s,
            "base_cleared": base_rep["cleared"], "base_n": base_rep["n_sources"],
            "base_ratio": base_rep["clear_ratio"], "base_vt": base_rep["virtual_time_s"],
            "base_avg": base_rep["avg_clear_time_s"], "base_travel": base_rep["mock_stats"]["travel_m"],
            "onl_cleared": onl_rep["cleared"], "onl_n": onl_rep["n_sources"],
            "onl_ratio": onl_rep["clear_ratio"], "onl_vt": onl_rep["virtual_time_s"],
            "onl_avg": onl_rep["avg_clear_time_s"], "onl_travel": onl_rep["mock_stats"]["travel_m"],
        })
        print(f"seed={s} 默认 {base_rep['cleared']}/{base_rep['n_sources']} "
              f"vt={base_rep['virtual_time_s']:.0f} tr={base_rep['mock_stats']['travel_m']:.0f} | "
              f"边绕边清 {onl_rep['cleared']}/{onl_rep['n_sources']} "
              f"vt={onl_rep['virtual_time_s']:.0f} tr={onl_rep['mock_stats']['travel_m']:.0f}",
              flush=True)

    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "per_seed.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    if args.metric == "gap":
        key = lambda r: ((r["base_ratio"] - r["onl_ratio"]) * 1000
                         + (r["onl_travel"] - r["base_travel"]) / 1000.0)
    else:
        key = lambda r: ((1 - r["base_ratio"]) * 1000
                         + (1 - r["onl_ratio"]) * 1000
                         + r["base_avg"] / 100.0 + r["onl_avg"] / 100.0)
    picked = sorted(rows, key=key, reverse=True)[:args.top]
    print("\n选出的差案例：")
    for r in picked:
        print(f"  seed={r['seed']} 源数={r['base_n']} 默认 {r['base_cleared']} "
              f"vt={r['base_vt']:.0f} | 边绕 {r['onl_cleared']} vt={r['onl_vt']:.0f}")

    for r in picked:
        s = r["seed"]
        fig, axes = plt.subplots(1, 2, figsize=(17.6, 9.0))
        for ax, kw, lab in ((axes[0], dict(onlap_clear=False), "默认：圈后统一清除"),
                            (axes[1], dict(onlap_clear=True), "边绕边清（小步定位）")):
            arena, rb, rep = run_one(s, **kw)
            draw_path(ax, arena, rb, rep,
                      f"seed={s}｜{lab}",
                      f"清除 {rep['cleared']}/{rep['n_sources']}｜虚拟 {rep['virtual_time_s']:.0f}s"
                      f"｜平均 {rep['avg_clear_time_s'] or 0:.0f}s"
                      f"｜检测 {rep['n_measure']}｜行程 {rep['mock_stats']['travel_m']:.0f}m")
            ax.legend(handles=legend_handles(), loc="lower right", fontsize=7.5,
                      framealpha=0.9)
        fig.tight_layout()
        p = os.path.join(OUTDIR, f"worst_{s}.png")
        fig.savefig(p, dpi=130)
        plt.close(fig)
        print(f"  -> {p}")


if __name__ == "__main__":
    main()
