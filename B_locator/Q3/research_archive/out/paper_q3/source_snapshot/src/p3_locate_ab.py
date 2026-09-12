"""定位路点参数的逐项 A/B（默认为"收紧后"的配置，逐项回退一项看影响）。"""
from __future__ import annotations

import argparse
import os
import statistics as st
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
from p3_bench import LIVE1, LIVE2, arena_from, outer_annulus, center_cluster  # noqa: E402

OLD = dict(locate_travel_cap_m=1100.0,
           locate_bearing_cap_m=700.0,
           locate_radii=(150.0, 300.0, 500.0, 750.0, 1000.0),
           locate_stale_stops=2,
           locate_max_detour_m=600.0,
           field_min_pending=1)

VARIANTS = {
    "收紧（当前默认）": {},
    "全部回退到旧值": dict(OLD, risk_locate=False, sector_clear_m=0.0,
                          clear_max_detour_m=1500.0),
    "旧定位+新机制": dict(OLD),
    "只回退 travel_cap/radii": dict(locate_travel_cap_m=1100.0,
                                    locate_radii=(150.0, 300.0, 500.0, 750.0, 1000.0)),
    "只回退 stale_stops": dict(locate_stale_stops=2),
    "只回退 max_detour": dict(locate_max_detour_m=600.0),
    "只回退 field_min_pending": dict(field_min_pending=1),
    "关掉 risk/sector": dict(risk_locate=False, sector_clear_m=0.0),
    "关掉 risk/sector+旧clear上限": dict(risk_locate=False, sector_clear_m=0.0,
                                        clear_max_detour_m=1500.0),
}


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

    seeds = [a.seed + 100 * i for i in range(a.cases)]
    hdr = (f"{'配置':<28}{'清除率':>8}{'全清':>7}{'T/N':>8}{'虚拟/s':>9}"
           f"{'检测':>7}{'行程/m':>9}")
    print(f"场景 {a.scenario}，{a.cases} 局")
    print(hdr)
    print("-" * len(hdr))
    for name, ov in VARIANTS.items():
        cfg = replace(TourConfig(), **ov)
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
        print(f"{name:<28}{cl/ns:>8.4f}{full:>4}/{a.cases:<3}{T/cl:>8.1f}"
              f"{T/a.cases:>9.0f}{mm/a.cases:>7.0f}{tr/a.cases:>9.0f}", flush=True)


if __name__ == "__main__":
    main()
