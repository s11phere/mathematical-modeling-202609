"""覆盖 ↔ 用时 的实测 Pareto 前沿：逐步砍外环 / 加大格网，看清除率与指标怎么变。

    python src/p4_tradeoff.py --cases 60
    python src/p4_tradeoff.py --cases 60 --scenario only     # 全定向（最严苛）
    python src/p4_tradeoff.py --cases 60 --scenario omni     # 全向（只要覆盖半径达标就必被发现）
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

CASES = [
    ("全覆盖：a=1000 + 外环1850×12", dict(grid_a=1000.0, outer_rings=((1850.0, 12),))),
    ("a=1000 + 外环1900×6", dict(grid_a=1000.0, outer_rings=((1900.0, 6),))),
    ("a=1000 + 外环2100×6（更外）", dict(grid_a=1000.0, outer_rings=((2100.0, 6),))),
    ("a=1200 只铺域内", dict(grid_a=1200.0, outer_rings=())),
    ("a=1100 只铺域内", dict(grid_a=1100.0, outer_rings=())),
    ("a=1000 只铺域内", dict(grid_a=1000.0, outer_rings=())),
    ("a=1000 域内+外环1900×4", dict(grid_a=1000.0, outer_rings=((1900.0, 4),))),
    ("a=900 只铺域内", dict(grid_a=900.0, outer_rings=())),
]


def evaluate(label, over, cases, seed, frac, one_pass=False):
    cfg = P4Config(**over)
    if one_pass:
        cfg.two_pass = False
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
    return {"label": label, "ratio": cl / tot, "full": full, "cases": cases,
            "avg": S.mean(vt) / (cl / cases) if cl else 0.0,
            "vtime": S.mean(vt), "travel": S.mean(tv), "stn": S.mean(stn),
            "wall": time.time() - t0}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="mixed",
                    choices=["mixed", "only", "edge", "omni"])
    ap.add_argument("--one-pass", action="store_true", help="再加一列：关掉第二遍扫描")
    a = ap.parse_args()
    frac = {"mixed": 0.5, "only": 1.0, "edge": 0.5, "omni": 0.0}[a.scenario]

    print(f"场景 {a.scenario}（定向占比 {frac}），{a.cases} 局，seed {a.seed}+100i")
    hdr = (f"{'配置':<32}{'清除率':>8}{'全清':>9}{'平均定位清除':>12}"
           f"{'虚拟':>8}{'行程':>9}{'站次':>7}")
    if a.one_pass:
        hdr += f"{'单遍清除率':>11}{'单遍平均':>10}"
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for (lbl, over) in CASES:
        r = evaluate(lbl, over, a.cases, a.seed, frac)
        row = {"cfg": lbl, **r}
        line = (f"{lbl:<32}{r['ratio']:>8.4f}{f'{r[chr(102)+chr(117)+chr(108)+chr(108)]}/{r[chr(99)+chr(97)+chr(115)+chr(101)+chr(115)]}':>9}"
                f"{r['avg']:>12.0f}{r['vtime']:>8.0f}{r['travel']:>9.0f}{r['stn']:>7.1f}")
        if a.one_pass:
            r1 = evaluate(lbl, over, a.cases, a.seed, frac, one_pass=True)
            row["one_ratio"] = r1["ratio"]
            row["one_avg"] = r1["avg"]
            line += f"{r1['ratio']:>11.4f}{r1['avg']:>10.0f}"
        rows.append(row)
        print(line, flush=True)
