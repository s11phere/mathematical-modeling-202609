"""降覆盖档的**正式记录**（100 局 × 两场景），供论文引用。

档位取自 `src/p4_family.py` 的大矩阵筛选结果，按"用时 ↔ 清除率"排列。

    python src/p4_record.py --cases 100
"""
from __future__ import annotations

import argparse
import json
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

# (档名, 覆盖口径, 配置)
LEVELS = [
    ("L0 全覆盖", "盲区 0.00%", dict()),
    ("L2 稀疏外环", "盲区 2.99%", dict(outer_rings=((1850.0, 9),))),
    ("L3 中格外环4", "盲区 ~3%", dict(grid_a=1100.0, outer_rings=((1900.0, 4),))),
    ("L4 只铺域内", "盲区 38.7%", dict(outer_rings=())),
    ("L6 稀疏格网", "盲区 ~60%", dict(grid_a=1100.0, outer_rings=())),
]


def run(over, cases, seed, frac):
    cfg = P4Config(**over)
    tot = cl = full = 0
    vt, tv, stn, ms = [], [], [], []
    for i in range(cases):
        arena, _ = directed_case(seed + 100 * i, directed_frac=frac)
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
    return {"ratio": cl / tot, "full": full, "miss": tot - cl, "cases": cases,
            "avg": S.mean(vt) / (cl / cases) if cl else 0.0,
            "vtime": S.mean(vt), "travel": S.mean(tv),
            "stn": S.mean(stn), "meas": S.mean(ms)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--json-out", default="B_locator/Q4/out/p4_levels.json")
    a = ap.parse_args()

    store = []
    for scen, frac in (("mixed", 0.5), ("only", 1.0), ("omni", 0.0)):
        print(f"\n===== 场景 {scen}（定向占比 {frac}），{a.cases} 局 =====")
        hdr = (f"{'档':<14}{'覆盖口径':>12}{'清除率':>8}{'全清':>10}{'漏源':>5}"
               f"{'平均定位清除':>12}{'虚拟':>8}{'行程':>9}{'站次':>7}{'检测':>7}")
        print(hdr)
        print("-" * len(hdr))
        for (lbl, cov, over) in LEVELS:
            t0 = time.time()
            r = run(over, a.cases, a.seed, frac)
            r.update({"level": lbl, "coverage": cov, "scenario": scen,
                      "cfg": {k: str(v) for k, v in over.items()},
                      "wall": time.time() - t0})
            store.append(r)
            print(f"{lbl:<14}{cov:>12}{r['ratio']:>8.4f}"
                  f"{f'{r[chr(102)+chr(117)+chr(108)+chr(108)]}/{a.cases}':>10}"
                  f"{r['miss']:>5}{r['avg']:>12.0f}{r['vtime']:>8.0f}"
                  f"{r['travel']:>9.0f}{r['stn']:>7.1f}{r['meas']:>7.0f}",
                  flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.json_out)), exist_ok=True)
    with open(a.json_out, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\n-> {a.json_out}")
