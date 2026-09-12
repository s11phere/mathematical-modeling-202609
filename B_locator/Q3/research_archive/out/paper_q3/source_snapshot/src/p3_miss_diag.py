"""针对单个未清除频道：打印它被检测过的所有位置/结果，以及到真源的距离。"""
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
from p3_sweep import SweepConfig, SweepRobot, lattice_candidates  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261613)
    ap.add_argument("--ch", type=int, default=0)
    ap.add_argument("--policy", default="sweep")
    ap.add_argument("--rings", default="")
    a = ap.parse_args()
    base = load_base()
    if a.policy == "tour":
        from p3_tour import TourConfig, TourRobot
        cfg = TourConfig()
        cls = TourRobot
    else:
        cfg = SweepConfig()
        cls = SweepRobot
    if a.rings:
        cfg.sweep_rings = eval(a.rings)
    aren = MockArena(seed=a.seed)
    rb = cls(aren, cfg, base=base, log=None)
    rep = rb.run()
    truth = {s["channel"]: s for s in aren.truth()["sources"]}
    chs = [a.ch] if a.ch else [s["channel"] for s in aren.truth()["sources"]
                               if not s["cleared"]]
    print(f"seed {a.seed}: 清除 {rep['cleared']}/{rep['n_sources']} "
          f"T={rep['virtual_time_s']:.0f} 行程={rep['travel_m']:.0f}")
    print(f"环格点：{[(round(x), round(y)) for x, y in lattice_candidates(cfg.sweep_rings)]}")
    print(f"实际停点：{[tuple(round(v) for v in p) for p in rep['scan_points']]}")
    for ch in chs:
        s = truth.get(ch)
        print(f"\n--- 频道 {ch} 真源 ({s['x_m']:.0f},{s['y_m']:.0f}) "
              f"r={math.hypot(s['x_m'], s['y_m']):.0f} r_recv={s['r_recv_m']:.0f} "
              f"{'已清除' if s['cleared'] else '未清除'} ---")
        rec = rb.recs[ch]
        for (x, y, t, res) in rec.meas_log:
            d = math.hypot(x - s["x_m"], y - s["y_m"])
            flag = "  <== 在接收半径内!" if (d <= s["r_recv_m"] and res != "direction") else ""
            print(f"   t={t:7.1f}  点({x:7.0f},{y:7.0f})  r={math.hypot(x,y):6.0f}  "
                  f"到源 {d:7.0f}  {res}{flag}")
        reg = rb.region(rec)
        print(f"   区域状态 {reg.get('status')} "
              f"r*={reg.get('min_enclosing_radius_m')} "
              f"顶点数={len(reg.get('vertices') or [])}")


if __name__ == "__main__":
    main()
