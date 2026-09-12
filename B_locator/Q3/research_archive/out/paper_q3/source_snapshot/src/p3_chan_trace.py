"""逐频道追踪：某个频道在整局里被"听到/定位/清除"的时间线，定位"该清没清"的时机。"""
from __future__ import annotations

import argparse
import math
import os
import sys

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


def make(scenario, cfg):
    if scenario.startswith("paths"):
        import p3_paths
        tag = {"pathsA": "A_默认种子", "pathsC": "C_live复刻",
               "pathsD": "D_外圈环带", "pathsE": "E_中心密集",
               "pathsF": "F_无信息陷阱"}[scenario]
        scen = {t: (no, ar, cf) for (t, no, ar, cf) in p3_paths.scenarios()}
        _no, a, _cfg = scen[tag]
        return a
    return MockArena(seed=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="pathsC")
    ap.add_argument("--ch", type=int, default=0)
    a = ap.parse_args()
    base = load_base()
    aren = make(a.scenario, TourConfig())
    rb = TourRobot(aren, TourConfig(), base=base, log=None)
    rep = rb.run()
    truth = {s["channel"]: s for s in aren.truth()["sources"]}
    print(f"{a.scenario}: 清除 {rep['cleared']}/{rep['n_sources']} T={rep['virtual_time_s']:.0f} "
          f"行程={rep['travel_m']:.0f}")
    chs = [a.ch] if a.ch else [s["channel"] for s in aren.truth()["sources"]]
    for ch in chs:
        s = truth[ch]
        rec = rb.recs[ch]
        print(f"\n频道{ch} 真源({s['x_m']:.0f},{s['y_m']:.0f}) r={math.hypot(s['x_m'],s['y_m']):.0f} "
              f"r_recv={s['r_recv_m']:.0f} 清除于 t={rec.cleared_at}")
        # 每一次"新方位"的时刻与当时算出的区域
        hist = rec.history
        for i, h in enumerate(hist):
            print(f"   第{i+1}条方位 t≈ 点({h['x']:.0f},{h['y']:.0f}) "
                  f"到源 {math.hypot(h['x']-s['x_m'], h['y']-s['y_m']):.0f} "
                  f"状态={h['status']} r*={h['r_star_m']}")
        # 找到"区域第一次变到可清除"的时刻
        for i, h in enumerate(hist):
            if h["status"] == "bounded" and (h["r_star_m"] or 1e9) <= 110:
                print(f"   -> 第{i+1}条方位时已经可以清除（r*={h['r_star_m']:.0f}）")


if __name__ == "__main__":
    main()
