"""诊断"去掉外环"漏掉的源：位置/朝向有什么共同点？

如果漏的都是"贴靶区边界 + 朝外发射"的定向源（这是外环唯一能救的那类），
就可以只在那条环带上补少量站位，把清除率买回来、同时保住大部分时间收益。
"""
from __future__ import annotations

import math
import os
import statistics as S
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from p3_arena import R_ARENA  # noqa: E402
from p4_arena_ext import directed_case  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402

CASES = [
    ("无外环 a=1000", dict(grid_a=1000.0, outer_rings=())),
    ("a=1200 无外环", dict(grid_a=1200.0, outer_rings=())),
]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60

for (lbl, over) in CASES:
    cfg = P4Config(**over)
    miss = []
    for i in range(N):
        arena, srcs = directed_case(20260914 + 100 * i, directed_frac=0.5)
        rb = P4GridRobot(arena, cfg)
        rep = rb.run()
        if rep["cleared"] == rep["n_sources"]:
            continue
        by_ch = {s.channel: s for s in srcs}
        for c, r in rb.recs.items():
            if r.cleared or c not in by_ch:
                continue
            s = by_ch[c]
            rho = math.hypot(s.x, s.y)
            # "背向"程度：朝向与径向的夹角（180° = 正对圆心，0° = 正对外）
            radial = math.degrees(math.atan2(s.y, s.x)) % 360.0
            diff = abs((float(s.dir_deg) - radial + 180.0) % 360.0 - 180.0)
            miss.append((round(rho), round(diff), s.cone_half < 180,
                         int(s.channel), round(s.r_recv)))
    print(f"\n=== {lbl}：{N} 局漏 {len(miss)} 个源 ===")
    for m in sorted(miss, key=lambda t: -t[0]):
        print(f"  半径 {m[0]:4d} m  与径向夹角 {m[1]:3d}°  "
              f"{'定向' if m[2] else '全向'}  ch{m[3]}  r_recv={m[4]}")
    if miss:
        rhos = [m[0] for m in miss]
        dirs = [m[1] for m in miss]
        print(f"  半径分布：min {min(rhos)} / 中位 {S.median(rhos):.0f} / max {max(rhos)}")
        print(f"  朝向与径向夹角：min {min(dirs)}° / 中位 {S.median(dirs):.0f}° / max {max(dirs)}°")
        print(f"  全向 {sum(1 for m in miss if not m[2])} 个，定向 {sum(1 for m in miss if m[2])} 个")
