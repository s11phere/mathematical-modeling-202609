"""**降覆盖档**扫描：主动放弃一部分区域，换大幅省时。

`cover_reduce = r` 表示"故意留 r 比例的可听格点不测"（见 `P4GridRobot.measure_set`）。
这一档是"覆盖 → 用时"最直接的旋钮：站数、测量次数、行程会同步下降。

    python src/p4_cover_reduce.py --cases 60
    python src/p4_cover_reduce.py --cases 60 --scenario only
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

ROWS = [
    ("R0 全覆盖（默认）", 0.0, dict()),
    ("R1 放弃 25% 面积", 0.25, dict(cover_reduce=0.25)),
    ("R2 放弃 40% 面积", 0.40, dict(cover_reduce=0.40)),
    ("R3 放弃 55% 面积", 0.55, dict(cover_reduce=0.55)),
    ("R4 放弃 70% 面积", 0.70, dict(cover_reduce=0.70)),
    ("R5 放弃 80% 面积", 0.80, dict(cover_reduce=0.80)),
]


def run(over, cases, seed, frac):
    cfg = P4Config(**over)
    tot = cl = full = 0
    vt, tv, stn, ms, ab = [], [], [], [], []
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
        ab.append(rb.stats.get("cover_abandoned", 0.0))
        if rep["cleared"] == rep["n_sources"]:
            full += 1
    return {"ratio": cl / tot, "full": full, "cases": cases, "miss": tot - cl,
            "avg": S.mean(vt) / (cl / cases) if cl else 0.0,
            "vtime": S.mean(vt), "travel": S.mean(tv), "stn": S.mean(stn),
            "meas": S.mean(ms), "abandon": S.mean(ab)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="mixed",
                    choices=["mixed", "only", "edge", "omni"])
    ap.add_argument("--json-out", default="")
    a = ap.parse_args()
    frac = {"mixed": 0.5, "only": 1.0, "edge": 0.5, "omni": 0.0}[a.scenario]
    print(f"场景 {a.scenario}（定向占比 {frac}），{a.cases} 局，seed {a.seed}+100i")
    hdr = (f"{'档':<22}{'实弃面积':>9}{'清除率':>8}{'全清':>9}{'漏源':>5}"
           f"{'平均定位清除':>12}{'虚拟':>8}{'行程':>9}{'站次':>7}{'检测':>7}{'墙钟':>7}")
    print(hdr)
    print("-" * len(hdr))
    store = []
    for (lbl, r, over) in ROWS:
        t0 = time.time()
        res = run(over, a.cases, a.seed, frac)
        res["label"] = lbl
        res["reduce"] = r
        res["wall"] = time.time() - t0
        store.append(res)
        full = f"{res['full']}/{res['cases']}"
        print(f"{lbl:<22}{res['abandon']:>9.1%}{res['ratio']:>8.4f}{full:>9}"
              f"{res['miss']:>5}{res['avg']:>12.0f}{res['vtime']:>8.0f}"
              f"{res['travel']:>9.0f}{res['stn']:>7.1f}{res['meas']:>7.0f}"
              f"{res['wall']:>7.1f}", flush=True)
    print("\n注：'实弃面积' = 贪心选取后主动放弃的可听格点占比（目标值 r 的实现值）。")
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
        print(f"-> {a.json_out}")
