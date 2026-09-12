"""把一局的动作序列打成可读轨迹，用于人工检查"哪里在折返、哪里在绕远"。"""
from __future__ import annotations
import argparse
import math
import os
import sys
import json

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena, V_ROBOT  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402
from p3_sweep import SweepConfig, SweepRobot  # noqa: E402
from p3_bench import LIVE1, LIVE2, arena_from, outer_annulus, center_cluster  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--policy", default="sweep")
    ap.add_argument("--cfg", default="")
    ap.add_argument("--scenario", default="random")
    ap.add_argument("--events", action="store_true", help="同时打印策略日志")
    a = ap.parse_args()
    base = load_base()
    over = json.loads(a.cfg) if a.cfg else {}
    if a.scenario == "random":
        aren = MockArena(seed=a.seed)
    elif a.scenario == "annulus":
        aren = outer_annulus(seed=a.seed)
    elif a.scenario == "center":
        aren = center_cluster(seed=a.seed)
    elif a.scenario == "live1":
        aren = arena_from(LIVE1, seed=a.seed)
    else:
        aren = arena_from(LIVE2, seed=a.seed)
    cls, cfgcls = (SweepRobot, SweepConfig) if a.policy == "sweep" else (P3Robot, P3Config)
    cfg = cfgcls(**{**cfgcls().__dict__, **over})
    rb = cls(aren, cfg, base=base, log=(print if a.events else None))
    rep = rb.run()
    print(f"\n=== seed {a.seed} 清除 {rep['cleared']}/{rep['n_sources']} "
          f"T={rep['virtual_time_s']:.0f}s 行程={rep['travel_m']:.0f}m "
          f"检测={rep['n_measure']} ===")
    for s in aren.truth()["sources"]:
        print(f"  真源 ch{s['channel']:>2} ({s['x_m']:>8.0f},{s['y_m']:>8.0f}) "
              f"r={math.hypot(s['x_m'], s['y_m']):>6.0f} r_recv={s['r_recv_m']:.0f} "
              f"{'已清除' if s['cleared'] else '未清除'}")
    print(f"\n{'t/s':>8}{'kind':>8}{'ch':>4}{'res':>18}{'x':>9}{'y':>9}{'r':>7}"
          f"{'seg/m':>8}{'turn':>6}")
    prev = np.array([0.0, 0.0])
    pprev_dir = None
    for ac in aren.actions:
        if "x" not in ac:
            continue
        p = np.array([ac["x"], ac["y"]])
        seg = float(np.linalg.norm(p - prev))
        d = p - prev
        turn = ""
        if seg > 30:
            if pprev_dir is not None:
                cos = float((d / seg) @ pprev_dir)
                turn = f"{math.degrees(math.acos(max(-1, min(1, cos)))):>6.0f}"
            pprev_dir = d / seg
        print(f"{ac['virtual_time_s']:>8.1f}{ac['kind']:>8}{ac.get('channel', ''):>4}"
              f"{str(ac.get('measure_result') or ac.get('clear_result') or ''):>18}"
              f"{ac['x']:>9.0f}{ac['y']:>9.0f}{float(np.linalg.norm(p)):>7.0f}"
              f"{seg:>8.0f}{turn:>6}")
        prev = p


if __name__ == "__main__":
    main()
