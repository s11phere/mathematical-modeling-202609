"""打印某局里"最费钱的 sweep_clear"的逐点距离，定位试探为什么走了那么远。"""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261013)
    ap.add_argument("--thresh", type=float, default=800.0)
    a = ap.parse_args()
    base = load_base()
    aren = MockArena(seed=a.seed)
    rb = TourRobot(aren, TourConfig(), base=base, log=None)
    orig = rb.sweep_clear
    events = []

    def patched(ch, rec, c, r, poly=None):
        pos0 = rb.pos
        trail = []
        orig_clear = rb.do_clear

        def clr(x, y, ch2):
            trail.append((round(math.dist(rb.pos, (x, y))), round(x), round(y)))
            return orig_clear(x, y, ch2)
        rb.do_clear = clr
        try:
            res = orig(ch, rec, c, r, poly=poly)
        finally:
            rb.do_clear = orig_clear
        tot = sum(t[0] for t in trail)
        if tot >= a.thresh:
            events.append((int(ch), round(float(r)), poly is not None, pos0, c, trail, res))
        return res
    rb.sweep_clear = patched
    rep = rb.run()
    print(f"seed {a.seed}: 行程 {rep['travel_m']:.0f} m，清除 {rep['cleared']}/{rep['n_sources']}；"
          f"共 {len(events)} 次昂贵的 sweep_clear")
    for (ch, r, haspoly, pos0, c, trail, res) in events:
        print(f"\nch{ch} r*={r} poly={haspoly} 起点 ({pos0[0]:.0f},{pos0[1]:.0f}) "
              f"中心 ({c[0]:.0f},{c[1]:.0f}) 距中心 {math.dist(pos0, tuple(c)):.0f} m "
              f"-> {'成功' if res else '失败'}")
        print("   逐点距离：" + ", ".join(str(t[0]) for t in trail))
        print("   试探点：" + ", ".join(f"({t[1]},{t[2]})" for t in trail))


if __name__ == "__main__":
    main()
