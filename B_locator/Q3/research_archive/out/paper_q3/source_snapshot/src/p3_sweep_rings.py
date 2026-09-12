"""环带骨架参数扫描：在同一批种子上比较 ``cover_rings`` 的几种配置。

    python src/p3_sweep_rings.py --cases 20
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
from p3_bench import LIVE1, LIVE2, arena_from, outer_annulus, center_cluster, summarize  # noqa: E402

CONFIGS = {
    "7@1050": ((1050.0, 7),),
    "8@1000": ((1000.0, 8),),
    "9@950": ((950.0, 9),),
    "10@920": ((920.0, 10),),
    "11@900": ((900.0, 11),),
    "13@880": ((880.0, 13),),
    "7@1050+7@1300": ((1050.0, 7), (1300.0, 7)),
    "9@950+9@1250": ((950.0, 9), (1250.0, 9)),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--scenario", default="random",
                    choices=["random", "annulus", "live1", "live2", "center"])
    ap.add_argument("--keys", default="")
    args = ap.parse_args()
    base = load_base()
    seeds = [args.seed + 100 * i for i in range(args.cases)]

    def mk(seed):
        if args.scenario == "random":
            return MockArena(seed=seed)
        if args.scenario == "annulus":
            return outer_annulus(seed=seed)
        if args.scenario == "center":
            return center_cluster(seed=seed)
        if args.scenario == "live1":
            return arena_from(LIVE1, seed=seed)
        return arena_from(LIVE2, seed=seed)

    keys = [k.strip() for k in args.keys.split(",") if k.strip()] or list(CONFIGS)
    hdr = (f"{'骨架':<16}{'清除率':>8}{'全清':>7}{'T/N':>8}{'虚拟/s':>9}"
           f"{'检测':>7}{'行程/m':>9}{'折返':>7}{'折返/m':>8}{'实跑':>7}")
    print(f"场景 {args.scenario}，{args.cases} 局")
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for k in keys:
        cfg = replace(TourConfig(), cover_rings=CONFIGS[k])
        reps = []
        t0 = time.time()
        for s in seeds:
            rb = TourRobot(mk(s), cfg, base=base, log=None)
            rep = rb.run()
            st_ = getattr(rb.arena, "stats", {}) or {}
            rep["travel_m"] = float(st_.get("travel_m", 0.0))
            acts = rb.arena.actions
            pts = [(0.0, 0.0)] + [(a["x"], a["y"]) for a in acts if "x" in a]
            P = []
            for p in pts:
                if not P or math.dist(P[-1], p) > 1.0:
                    P.append(p)
            un = 0
            um = 0.0
            for i in range(1, len(P) - 1):
                v1 = np.asarray(P[i], float) - np.asarray(P[i - 1], float)
                v2 = np.asarray(P[i + 1], float) - np.asarray(P[i], float)
                n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
                if n1 < 30 or n2 < 30:
                    continue
                ang = math.degrees(math.acos(max(-1, min(1, float((v1 / n1) @ (v2 / n2))))))
                if ang > 120.0:
                    un += 1
                    um += n2
            rep["u_turns"] = un
            rep["u_m"] = um
            rep["_wall"] = 0.0
            reps.append(rep)
        s_ = summarize(reps)
        s_["wall_s"] = time.time() - t0
        s_["Tn"] = st.mean(r["virtual_time_s"] / max(r["cleared"], 1) for r in reps)
        rows.append((k, s_))
        print(f"{k:<16}{s_['clear_ratio']:>8.3f}{s_['full_clear_cases']:>4}/{s_['cases']:<3}"
              f"{s_['Tn']:>8.1f}{s_['vtime_s']:>9.0f}{s_['n_measure']:>7.0f}"
              f"{s_['travel_m']:>9.0f}{s_['u_turns']:>7.1f}{s_['u_m']:>8.0f}"
              f"{s_['wall_s']:>7.1f}", flush=True)
    rows.sort(key=lambda kv: kv[1]["Tn"])
    print(f"\n按 T/N 排序最优：{rows[0][0]}  T/N={rows[0][1]['Tn']:.1f}")


if __name__ == "__main__":
    main()
