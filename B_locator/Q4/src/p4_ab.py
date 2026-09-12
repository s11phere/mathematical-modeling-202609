"""A/B 对照台：统一航路（边扫边清） vs 阶段式（先扫后清）。

    python src/p4_ab.py --cases 20                    # 混合定向场景
    python src/p4_ab.py --cases 20 --scenario only    # 全定向
    python src/p4_ab.py --cases 20 --grid-a 1200
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


def evaluate(label, cfg, cases, seed, frac):
    t0 = time.time()
    tot = cl = full = 0
    vt, tv, st, ac = [], [], [], []
    for i in range(cases):
        arena, _ = directed_case(seed + 100 * i, directed_frac=frac)
        rb = P4GridRobot(arena, cfg)
        rep = rb.run()
        tot += rep["n_sources"]
        cl += rep["cleared"]
        vt.append(rep["virtual_time_s"])
        tv.append(rep["travel_m"])
        st.append(len(rb.visited_stations))
        ac.append(rep["n_measure"] + rep["n_clear"])
        if rep["cleared"] == rep["n_sources"]:
            full += 1
    return {
        "label": label, "ratio": cl / tot, "full": f"{full}/{cases}",
        "cleared": cl, "total": tot,
        "avg_clear": S.mean(vt) / (cl / cases),
        "vtime": S.mean(vt), "travel": S.mean(tv),
        "stations": S.mean(st), "actions": S.mean(ac),
        "wall": time.time() - t0,
    }


HDR = (f"{'配置':<34}{'清除率':>8}{'全清':>7}{'平均定位清除':>13}"
       f"{'虚拟':>8}{'行程':>9}{'站位':>7}{'动作':>7}{'墙钟':>7}")


def fmt(r):
    return (f"{r['label']:<34}{r['ratio']:>8.4f}{r['full']:>7}"
            f"{r['avg_clear']:>13.0f}{r['vtime']:>8.0f}{r['travel']:>9.0f}"
            f"{r['stations']:>7.1f}{r['actions']:>7.0f}{r['wall']:>7.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="mixed", choices=["mixed", "only", "edge", "omni"])
    ap.add_argument("--grid-a", type=float, default=1000.0)
    ap.add_argument("--grid-step", type=float, default=25.0)
    a = ap.parse_args()
    frac = {"mixed": 0.5, "only": 1.0, "edge": 0.5, "omni": 0.0}[a.scenario]

    base = dict(grid_a=a.grid_a, cover_grid_step_m=a.grid_step)
    rows = [
        evaluate("统一航路（边扫边清，默认）", P4Config(unified=True, **base),
                 a.cases, a.seed, frac),
        evaluate("阶段式（先扫两遍再清）", P4Config(unified=False, **base),
                 a.cases, a.seed, frac),
        evaluate("统一 + 只扫一遍", P4Config(unified=True, two_pass=False, **base),
                 a.cases, a.seed, frac),
        evaluate("统一 + 规划航路", P4Config(unified=True, plan_tour=True, **base),
                 a.cases, a.seed, frac),
    ]
    print(f"场景 {a.scenario}，{a.cases} 局（seed {a.seed}+100i），"
          f"grid_a={a.grid_a:.0f}，覆盖网格 {a.grid_step:.0f} m")
    print(HDR)
    print("-" * len(HDR))
    for r in rows:
        print(fmt(r), flush=True)


if __name__ == "__main__":
    main()
