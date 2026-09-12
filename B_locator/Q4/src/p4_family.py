"""大范围参数矩阵：找"用时大幅减少、清除率仍高"的档位。

扫描维度（都在绕圈航路上）：
* 格网边长 a（决定域内站数）
* 外环（半径 × 点数；() = 不铺）
* station_min_gain（整站跳过的门槛）
* 第二遍扫描开关

用 25 局快筛，挑出候选后再用 100 局复核。结果写入 JSON 便于论文引用。

    python src/p4_family.py --cases 25
"""
from __future__ import annotations

import argparse
import itertools
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

GRID_A = [900.0, 1000.0, 1100.0, 1200.0]
OUTER = [((), "无外环"),
         (((1900.0, 3),), "外环1900×3"),
         (((1900.0, 4),), "外环1900×4"),
         (((1900.0, 6),), "外环1900×6"),
         (((1850.0, 9),), "外环1850×9"),
         (((1850.0, 12),), "外环1850×12")]
GAINS = [90.0, 400.0]


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
    return {"ratio": cl / tot, "full": full, "cases": cases, "miss": tot - cl,
            "avg": S.mean(vt) / (cl / cases) if cl else 0.0,
            "vtime": S.mean(vt), "travel": S.mean(tv), "stn": S.mean(stn),
            "meas": S.mean(ms)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=25)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="mixed",
                    choices=["mixed", "only", "edge", "omni"])
    ap.add_argument("--json-out", default="B_locator/Q4/out/p4_family.json")
    a = ap.parse_args()
    frac = {"mixed": 0.5, "only": 1.0, "edge": 0.5, "omni": 0.0}[a.scenario]

    print(f"场景 {a.scenario}（定向占比 {frac}），{a.cases} 局快筛")
    hdr = (f"{'a':>6}{'外环':>12}{'gain':>6}{'清除率':>8}{'全清':>8}{'漏源':>5}"
           f"{'平均定位清除':>12}{'虚拟':>8}{'行程':>9}{'站次':>7}{'检测':>7}")
    print(hdr)
    print("-" * len(hdr))
    recs = []
    for (a_, (outer, olabel), g) in itertools.product(GRID_A, OUTER, GAINS):
        over = dict(grid_a=a_, outer_rings=outer, station_min_gain=g)
        t0 = time.time()
        r = run(over, a.cases, a.seed, frac)
        r.update({"grid_a": a_, "outer": olabel, "gain": g,
                  "wall": time.time() - t0, "cases_n": a.cases})
        recs.append(r)
        print(f"{a_:>6.0f}{olabel:>12}{g:>6.0f}{r['ratio']:>8.4f}"
              f"{f'{r[chr(102)+chr(117)+chr(108)+chr(108)]}/{a.cases}':>8}"
              f"{r['miss']:>5}{r['avg']:>12.0f}{r['vtime']:>8.0f}"
              f"{r['travel']:>9.0f}{r['stn']:>7.1f}{r['meas']:>7.0f}", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.json_out)), exist_ok=True)
    with open(a.json_out, "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=2)
    print(f"\n-> {a.json_out}（{len(recs)} 个配置）")
    print("\n=== 按'清除率 ≥ 0.97 且 用时最短'排序的前 8 名 ===")
    ok = [r for r in recs if r["ratio"] >= 0.97]
    ok.sort(key=lambda r: r["avg"])
    for r in ok[:8]:
        print(f"  a={r['grid_a']:.0f} {r['outer']:<12} gain={r['gain']:.0f} "
              f"-> 清除率 {r['ratio']:.4f}（漏 {r['miss']}）平均 {r['avg']:.0f} s "
              f"虚拟 {r['vtime']:.0f} s 行程 {r['travel']:.0f} m 站次 {r['stn']:.1f}")
    print("\n=== 按'清除率 ≥ 0.99 且 用时最短'排序的前 5 名 ===")
    ok = [r for r in recs if r["ratio"] >= 0.99]
    ok.sort(key=lambda r: r["avg"])
    for r in ok[:5]:
        print(f"  a={r['grid_a']:.0f} {r['outer']:<12} gain={r['gain']:.0f} "
              f"-> 清除率 {r['ratio']:.4f}（漏 {r['miss']}）平均 {r['avg']:.0f} s "
              f"虚拟 {r['vtime']:.0f} s 行程 {r['travel']:.0f} m 站次 {r['stn']:.1f}")
