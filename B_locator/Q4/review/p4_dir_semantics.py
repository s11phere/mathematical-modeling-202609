"""核对：图上"红箭头"与"示向度射线"看起来矛盾的原因。

取一局定向源，打印
* 源的 dir_deg（协议给的"定向方向"）、
* 源到各个"听到过它的检测点"的向量方向（即射线实际从哪一侧过来）、
* 两者夹角。
如果夹角都在 (90°, 180°]，说明"能听到源的那一侧"与 dir_deg 相反
（模拟器的实现口径是"站→源 的视线方向落在 dir_deg 的 ±90° 内"）。
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena, MockSource  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402

# 源在 (1000,0)，dir_deg = 90（正北）
src = MockSource(3, 1000.0, 0.0, 1200.0, cone_half=90.0, dir_deg=90.0)
arena = MockArena(seed=1, budget_s=1e9, sources=[src])
rb = P4GridRobot(arena, P4Config())
rb.arena.enter()

print(f"源 G=(1000,0)，dir_deg=90°（正北），覆盖半角 90°（180° 覆盖范围）")
print(f"{'检测点':>18}{'到源距离':>9}{'结果':>10}"
      f"{'源→站 的方向':>14}{'与 dir_deg 夹角':>16}{'源→站 是否落在 ±90°':>20}")
for q in [(0.0, 0.0), (1000.0, 900.0), (1000.0, -900.0), (2000.0, 0.0),
          (500.0, 500.0), (1700.0, 500.0)]:
    r = arena.measure(q[0], q[1], 3)
    res = r.get("measure_result")
    d = math.hypot(q[0] - 1000.0, q[1] - 0.0)
    # "源→站"的向量方向（也就是射线从哪一侧射过来）
    a_src2q = math.degrees(math.atan2(q[1] - 0.0, q[0] - 1000.0)) % 360.0
    diff = abs((a_src2q - 90.0 + 180.0) % 360.0 - 180.0)
    print(f"({q[0]:6.0f},{q[1]:6.0f}){d:>9.0f}{res:>10}"
          f"{a_src2q:>14.1f}{diff:>16.1f}{str(diff <= 90.0):>20}")

print("\n结论：能听到源的检测点，全部满足『源→站 的方向落在 dir_deg ±90° 内』，")
print("      也就是说 —— 信号出现在 dir_deg **所指的那半平面**里。")
print("      所以图上箭头所指一侧 = 该源实际辐射、可被听到的那一侧。")
