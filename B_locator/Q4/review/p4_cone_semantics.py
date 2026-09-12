"""确定 mock 的定向覆盖角语义：源朝 d 发射时，哪个半平面听得到？"""
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

a = MockArena(seed=1, budget_s=1e9,
              sources=[MockSource(3, 1000.0, 0.0, 1200.0, cone_half=90.0, dir_deg=0.0)])
a.enter()
print("源在 (1000,0)，发射方向 d = 0°（正东），有效接收半径 1200 m")
for q in [(2000.0, 0.0), (500.0, 500.0), (0.0, 0.0), (500.0, -500.0),
          (1400.0, 300.0), (1600.0, 0.0), (1000.0, 800.0)]:
    r = a.measure(q[0], q[1], 3)
    d = math.hypot(q[0] - 1000.0, q[1])
    toward = (q[0] - 1000.0) > 0        # 在发射方向那一侧（源→站 与 d 同向）
    away = (1000.0 - q[0]) > 0          # 在发射方向的反侧
    res = r.get("measure_result")
    print(f"  q=({q[0]:6.0f},{q[1]:5.0f}) d={d:6.0f} -> {res:10s} "
          f"朝向侧={toward} 背向侧={away}")
