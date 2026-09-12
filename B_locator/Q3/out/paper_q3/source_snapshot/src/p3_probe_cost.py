"""覆盖式试探的开销统计：每个目标试探了几次、走了多少米。"""
from __future__ import annotations

import argparse
import math
import os
import statistics as st
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
    ap.add_argument("--cases", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260913)
    a = ap.parse_args()
    base = load_base()
    rows = []
    for i in range(a.cases):
        s = a.seed + 100 * i
        aren = MockArena(seed=s)
        rb = TourRobot(aren, TourConfig(), base=base, log=None)
        per = []
        orig = rb.sweep_clear

        def patched(ch, rec, c, r, poly=None, _orig=orig, _rb=rb, _per=per):
            n0 = _rb.stats.get("n_probe", 0)
            m0 = _rb.stats.get("probe_m", 0.0)
            res = _orig(ch, rec, c, r, poly=poly)
            _per.append((int(ch), round(float(r)), _rb.stats.get("n_probe", 0) - n0,
                         _rb.stats.get("probe_m", 0.0) - m0, bool(res)))
            return res
        rb.sweep_clear = patched
        rep = rb.run()
        rows.append((s, rep, per, rb))
    print(f"{a.cases} 局：总行程 {st.mean(r[1]['travel_m'] for r in rows):.0f} m；"
          f"试探 {st.mean(r[3].stats.get('n_probe',0) for r in rows):.1f} 次 / "
          f"{st.mean(r[3].stats.get('probe_m',0.0) for r in rows):.0f} m")
    allp = [p for r in rows for p in r[2]]
    print(f"每次 sweep_clear：平均 {len(allp)/a.cases:.1f} 次调用；"
          f"每次试探点数 {st.mean(p[2] for p in allp):.1f}；"
          f"每次移动 {st.mean(p[3] for p in allp):.0f} m")
    print("最费钱的 12 次 sweep_clear：")
    for p in sorted(allp, key=lambda x: -x[3])[:12]:
        print(f"   ch{p[0]:>3} r*={p[1]:>4} 试探 {p[2]:>3} 点  移动 {p[3]:>6.0f} m  "
              f"{'成功' if p[4] else '失败'}")
    # 每局统计
    for s, rep, per, rb in rows:
        big = [p for p in per if p[3] > 400]
        print(f"  seed {s}: sweep 调用 {len(per)}；>400 m 的 {len(big)} 次，"
              f"合计 {sum(p[3] for p in big):.0f} m")


if __name__ == "__main__":
    main()
