"""在指定情景下找出未清除的频道及其原因。"""
from __future__ import annotations

import argparse
import math
import os
import sys
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--scenario", default="random")
    a = ap.parse_args()
    base = load_base()

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

    for i in range(a.cases):
        s = a.seed + 100 * i
        aren = mk(s)
        rb = TourRobot(aren, TourConfig(), base=base, log=None)
        rep = rb.run()
        if rep["cleared"] == rep["n_sources"]:
            continue
        print(f"\nseed {s}: 清除 {rep['cleared']}/{rep['n_sources']} T={rep['virtual_time_s']:.0f} "
              f"行程={rep['travel_m']:.0f}")
        for src in aren.truth()["sources"]:
            if src["cleared"]:
                continue
            ch = src["channel"]
            rec = rb.recs[ch]
            reg = rb.region(rec)
            print(f"  未清 ch{ch} 真源({src['x_m']:.0f},{src['y_m']:.0f}) "
                  f"r={math.hypot(src['x_m'], src['y_m']):.0f} r_recv={src['r_recv_m']:.0f} "
                  f"方位{rec.n_bearings}条 状态={reg.get('status')} "
                  f"r*={reg.get('min_enclosing_radius_m')} 检测{len(rec.meas_pts)}次 "
                  f"hold={rb.on_hold(ch)}")
            for h in rec.history:
                print(f"     方位{h['n']} 点({h['x']:.0f},{h['y']:.0f}) "
                      f"状态={h['status']} r*={h['r_star_m']}")


if __name__ == "__main__":
    main()
