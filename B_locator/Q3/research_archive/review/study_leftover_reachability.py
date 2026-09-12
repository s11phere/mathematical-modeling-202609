"""关键量化：末尾"已定位但未清除"的目标，在哪个时刻曾经"可达"？

对每个这样的目标 ch，回放它的台账，找出它**第一次变成可清目标**的虚拟时刻 t0、
此时机器狗的位置、以及"从这里走过去清掉"的乐观耗时。
再和"从 t0 到结束还剩多少时间"比较，判断属于哪一类：

  R1 可达却错过 —— t0 时剩余时间 >= 耗时，但最终没清（**策略缺陷，可修**）
  R2 从未可达   —— t0 时剩余时间 < 耗时（结构性，预算不够）
  R3 清过失败   —— 去过但没打中/预算耗尽（clear_fail > 0）

另外统计：扫描轮新发现的频道集合，与"origin 第 0 轮给出的频道集合"的重叠，
以判断扫描的信息增量到底是"新频道"还是"给已知频道补第二方位"。
"""
from __future__ import annotations

import json
import math
import os
import statistics as st
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _SRC)

import numpy as np  # noqa: E402

from p3_arena import MockArena, T_CLEAR_FAIL, T_CLEAR_OK, T_MEASURE, T_SWITCH, V_ROBOT  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402


def run_case(seed, base):
    arena = MockArena(seed=seed)
    rb = P3Robot(arena, P3Config(), base=base, log=None)

    snapshots = []
    orig_measure = rb.measure
    orig_estimate = rb.estimate_clear_cost

    def measure_spy(x, y, ch):
        r = orig_measure(x, y, ch)
        t = float(arena.virtual_time_s)
        rec = rb.recs[int(ch)]
        br = rb.bounded_region(rec)
        cost = None
        if br is not None and rec.n_bearings >= 2:
            cost = orig_estimate(br, from_pos=rb.pos,
                                 probe_cap=rb.cfg.optimistic_probe_steps)
        snapshots.append({
            "t": t, "x": float(rb.pos[0]), "y": float(rb.pos[1]),
            "ch": int(ch),
            "n_bearings": rec.n_bearings,
            "remaining": rb.remaining(),
            # 用**策略自己估计的区域中心**算代价（这才是它决策时看到的东西）
            "real_cost": cost,
            "center": (tuple(br["center"]) if br else None),
            "radius": (float(br["radius"]) if br else None),
        })
        return r

    rb.measure = measure_spy
    rep = rb.run()
    rep["seed"] = seed
    rep["_snapshots"] = snapshots
    # 每个频道第一次达到 2 条方位的时刻与当时位置
    first2 = {}
    for s in snapshots:
        if s["n_bearings"] >= 2 and s["ch"] not in first2:
            first2[s["ch"]] = s
    rep["_first2"] = first2
    return rep


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    seeds = [20260913 + 100 * i for i in range(n)]
    base = load_base()
    rows = [run_case(s, base) for s in seeds]

    cls = {"R1": [], "R2": [], "R3": []}
    for r in rows:
        for ch_s, info in r["channels"].items():
            ch = int(ch_s)
            if info["cleared"]:
                continue
            if info["n_bearings"] < 2:
                continue
            f2 = r["_first2"].get(ch)
            if f2 is None or f2.get("real_cost") is None:
                cls["R3"].append((r["seed"], ch))
                continue
            need = float(f2["real_cost"])
            cx, cy = f2["center"]
            d = math.hypot(cx - f2["x"], cy - f2["y"])
            row = (r["seed"], ch, round(f2["remaining"]), round(need), round(d),
                   round(f2["radius"]))
            if f2["remaining"] >= need:
                cls["R1"].append(row)
            else:
                cls["R2"].append(row)

    tot = len(cls["R1"]) + len(cls["R2"]) + len(cls["R3"])
    print(f"{n} 局；末尾'已定位但未清除'的目标共 {tot} 个\n")
    print(f"  R1 可达却错过（t0 时剩余 >= 耗时）: {len(cls['R1']):>4} 个"
          f"  {len(cls['R1'])/max(tot,1)*100:5.1f}%")
    print(f"  R2 从未可达（t0 时剩余 <  耗时）: {len(cls['R2']):>4} 个"
          f"  {len(cls['R2'])/max(tot,1)*100:5.1f}%")
    print(f"  R3 去过但失败/记账异常          : {len(cls['R3']):>4} 个")

    if cls["R1"]:
        print("\n  R1 明细（seed, ch, 当时剩余s, 需要s, 到区域中心m, 区域半径m）：")
        for x in cls["R1"][:25]:
            print(f"    {x}")

    print("\n  R2 的'缺口'分布（需要 − 剩余）:")
    gaps = [x[3] - x[2] for x in cls["R2"]]
    if gaps:
        gaps_sorted = sorted(gaps)
        print(f"    中位数 {st.median(gaps):.0f} s，"
              f"P25 {gaps_sorted[len(gaps_sorted)//4]:.0f} s，"
              f"P75 {gaps_sorted[3*len(gaps_sorted)//4]:.0f} s，"
              f"最大 {max(gaps):.0f} s")

    # ---- 扫描是否"只在确实缺第二个方位时才做" ----
    print("\n【扫描的用途】进入清理队列（≥2 条方位）的频道，其第二方位来自哪里")
    from_scan, at_origin = 0, 0
    for r in rows:
        for ch, f2 in r["_first2"].items():
            if abs(f2["x"]) < 1e-6 and abs(f2["y"]) < 1e-6:
                at_origin += 1
            else:
                from_scan += 1
    print(f"  在原点就拿到 2 条方位的：{at_origin} 个")
    print(f"  需要移动到别处才拿到第二方位的：{from_scan} 个"
          f"（{(from_scan)/max(at_origin+from_scan,1)*100:.1f}%）"
          f" <- 这部分是扫描阶段换来的")


if __name__ == "__main__":
    sys.exit(main())
