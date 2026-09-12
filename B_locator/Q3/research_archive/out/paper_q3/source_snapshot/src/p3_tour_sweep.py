"""统一航路策略的参数/开关扫描（12–30 局同一批种子）。

    python src/p3_tour_sweep.py --cases 12 --grid cover_duty_frac=0.95,1.1,1.4,8
    python src/p3_tour_sweep.py --cases 12 --grid route_mode=insert,polish,tsp
    python src/p3_tour_sweep.py --cases 12 --grid locate_mode=never,stale,always
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys
import time
from dataclasses import replace

import numpy as np

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
from p3_bench import LIVE1, LIVE2, arena_from, outer_annulus, center_cluster  # noqa: E402


def coerce(v):
    if v in ("True", "true"):
        return True
    if v in ("False", "false"):
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--scenario", default="random")
    ap.add_argument("--grid", action="append", default=None,
                    metavar="NAME=v1,v2")
    ap.add_argument("--base", default="", help="基础覆盖配置（JSON）")
    ap.add_argument("--rings", default="",
                    help='骨架配置列表，形如 "950:9,1050:7,1200:6"（半径:点数）')
    a = ap.parse_args()
    base = load_base()
    if a.base:
        base_cfg = replace(TourConfig(), **json.loads(a.base))
    else:
        base_cfg = TourConfig()

    def mk(seed):
        if a.scenario == "random":
            return MockArena(seed=seed)
        if a.scenario == "annulus":
            return outer_annulus(seed=seed)
        if a.scenario == "center":
            return center_cluster(seed=seed)
        if a.scenario == "live1":
            return arena_from(LIVE1, seed=seed)
        return arena_from(LIVE2, seed=seed)

    combos = [{}]
    for spec in (a.grid or []):
        k, v = spec.split("=", 1)
        vals = [coerce(x) for x in v.split(",") if x.strip() != ""]
        combos = [dict(c, **{k.strip(): val}) for c in combos for val in vals]
    if a.rings:
        rl = []
        for tok in a.rings.split(","):
            r, n = tok.split(":")
            rl.append(((float(r), int(n)),))
        combos = [dict(c, cover_rings=rr) for c in combos for rr in rl]
    seeds = [a.seed + 100 * i for i in range(a.cases)]
    hdr = (f"{'配置':<44}{'清除率':>8}{'全清':>7}{'T/N':>8}{'虚拟/s':>9}"
           f"{'检测':>7}{'行程/m':>9}{'实跑/s':>8}")
    print(f"场景 {a.scenario}，{a.cases} 局")
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for ov in combos:
        cfg = replace(base_cfg, **ov)
        t0 = time.time()
        T = cl = ns = mm = tr = 0
        full = 0
        for s in seeds:
            rb = TourRobot(mk(s), cfg, base=base, log=None)
            rep = rb.run()
            T += rep["virtual_time_s"]
            cl += rep["cleared"]
            ns += rep["n_sources"]
            mm += rep["n_measure"]
            tr += rep["travel_m"]
            full += int(rep["cleared"] == rep["n_sources"])
        tag = json.dumps(ov, ensure_ascii=False) if ov else "（默认）"
        print(f"{tag:<44}{cl/ns:>8.3f}{full:>4}/{a.cases:<3}{T/cl:>8.1f}"
              f"{T/a.cases:>9.0f}{mm/a.cases:>7.0f}{tr/a.cases:>9.0f}"
              f"{time.time()-t0:>8.1f}", flush=True)
        rows.append((tag, T / cl))
    rows.sort(key=lambda kv: kv[1])
    print(f"\n最优：{rows[0][0]}  T/N={rows[0][1]:.1f}")


if __name__ == "__main__":
    main()
