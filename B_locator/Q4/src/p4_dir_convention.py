"""把 mock 的定向源语义反转（模拟"协议约定相反"），检验策略是否仍然全清。

背景：`MockArena` 的 cone 判据是
    a = 站→源 的方位角;  in_cone = |a - dir_deg| <= cone_half
它等价于"**站落在 dir_deg 所指的那半平面里**"（源→站 的方向与 dir_deg 夹角 ≤ 90°）。
但题目原文"定向方向两侧各 90°"更像是"**源朝 dir_deg 辐射**"，
即"站必须落在 **-dir_deg** 那一侧"。两种约定互为反面。

本模块用子类把 mock 的语义**反转**，然后把同一套策略跑一遍：
如果两种约定下清除率都一样，说明策略对协议约定不敏感。

    python src/p4_dir_convention.py --cases 20
"""
from __future__ import annotations

import argparse
import math
import os
import statistics as S
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena  # noqa: E402
from p4_arena_ext import directed_case  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402


class FlippedArena(MockArena):
    """把定向覆盖角判据反向（站必须落在 dir_deg 的**反面**半平面里）。"""

    def measure(self, x, y, channel):
        src = self._src_of(channel)
        if src is not None and not src.cleared and src.cone_half < 180.0:
            # 临时把方向转 180°，让 mock 的判据等价于"反约定"
            d0 = src.dir_deg
            src.dir_deg = (float(d0) + 180.0) % 360.0
            try:
                return super().measure(x, y, channel)
            finally:
                src.dir_deg = d0
        return super().measure(x, y, channel)


def run(arena_cls, cases, seed, frac, cfg=None):
    tot = cl = full = 0
    vt, tv = [], []
    for i in range(cases):
        arena, srcs = directed_case(seed + 100 * i, directed_frac=frac)
        if arena_cls is not MockArena:
            arena = arena_cls(seed=arena.seed, budget_s=arena.budget,
                              sources=arena.sources)
        rb = P4GridRobot(arena, cfg or P4Config())
        rep = rb.run()
        tot += rep["n_sources"]
        cl += rep["cleared"]
        vt.append(rep["virtual_time_s"])
        tv.append(rep["travel_m"])
        if rep["cleared"] == rep["n_sources"]:
            full += 1
    return {"ratio": cl / tot, "full": full, "n": cases,
            "avg": S.mean(vt) / (cl / cases), "vtime": S.mean(vt),
            "travel": S.mean(tv)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="only", choices=["only", "mixed"])
    a = ap.parse_args()
    frac = {"only": 1.0, "mixed": 0.5}[a.scenario]

    print(f"场景 {a.scenario}（定向比例 {frac}），{a.cases} 局")
    print(f"{'约定':<34}{'清除率':>8}{'全清':>7}{'平均定位清除':>13}"
          f"{'虚拟':>8}{'行程':>9}")
    print("-" * 72)
    t0 = time.time()
    for label, cls in (("mock 原约定（站落在 dir_deg 一侧）", MockArena),
                       ("反向约定（站落在 -dir_deg 一侧）", FlippedArena)):
        r = run(cls, a.cases, a.seed, frac)
        print(f"{label:<34}{r['ratio']:>8.4f}{r['full']:>4}/{r['n']:<3}"
              f"{r['avg']:>13.0f}{r['vtime']:>8.0f}{r['travel']:>9.0f}", flush=True)
    print(f"\n用时 {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
