"""逐局对比两套配置，找出差异最大的几局（用于定位回归来源）。"""
from __future__ import annotations

import argparse
import os
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

OLD = dict(locate_travel_cap_m=1100.0,
           locate_bearing_cap_m=700.0,
           locate_radii=(150.0, 300.0, 500.0, 750.0, 1000.0),
           locate_stale_stops=2,
           locate_max_detour_m=600.0,
           field_min_pending=1,
           risk_locate=False,
           sector_clear_m=0.0,
           clear_max_detour_m=1500.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260913)
    a = ap.parse_args()
    base = load_base()
    rows = []
    for i in range(a.cases):
        s = a.seed + 100 * i
        out = {}
        for tag, ov in (("new", {}), ("old", OLD)):
            rb = TourRobot(MockArena(seed=s), replace(TourConfig(), **ov),
                           base=base, log=None)
            rep = rb.run()
            out[tag] = (rep["virtual_time_s"], rep["travel_m"], rep["n_measure"],
                        rep["n_sources"], rep["cleared"], len(rb.tour_log))
        rows.append((s, out["new"], out["old"]))
    print(f"{'seed':>10}{'new T':>8}{'old T':>8}{'ΔT':>8}{'new行程':>9}{'old行程':>9}"
          f"{'Δ行程':>8}{'new检测':>8}{'old检测':>8}{'new站':>7}{'old站':>7}")
    dT = []
    for s, n, o in rows:
        dT.append(n[0] - o[0])
        print(f"{s:>10}{n[0]:>8.0f}{o[0]:>8.0f}{n[0]-o[0]:>8.0f}"
              f"{n[1]:>9.0f}{o[1]:>9.0f}{n[1]-o[1]:>8.0f}"
              f"{n[2]:>8.0f}{o[2]:>8.0f}{n[5]:>7}{o[5]:>7}")
    print(f"\nΔT 均值 {sum(dT)/len(dT):+.0f}s")


if __name__ == "__main__":
    main()
