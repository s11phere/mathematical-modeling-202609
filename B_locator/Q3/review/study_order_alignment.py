"""诊断：排序决策时刻的"区域中心" vs 执行时刻的实际中心 —— 滚动结构到底吃掉了多少。

对每一次 plan_clear_tour：
  * 记录当时各目标的中心（排序依据）与所选的第一步
对每一次 clear_target 执行：
  * 记录执行开始时的中心、是否与决策时一致、实际耗时/行程、结果
  * 记录清除成功时机器狗的位置，与"决策时预计的中心"差多少
    （= 走到中心这一手有多准；差值大说明中心漂移或误差在拖着走）

另外记录：每个目标在**成为可清目标之后**，到**真正被尝试清除**之间隔了多久、
期间有没有新方位导致中心变化（= 排序决策被"过期信息"影响的程度）。
"""
from __future__ import annotations

import math
import os
import statistics as st
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _SRC)

import numpy as np  # noqa: E402

from p3_arena import MockArena, V_ROBOT  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402


def run_case(seed, base):
    arena = MockArena(seed=seed)
    rb = P3Robot(arena, P3Config(), base=base, log=None)

    plan_log = []      # 每次排序时的快照
    exec_log = []      # 每次真实执行的记录

    orig_plan = rb.plan_clear_tour
    orig_clear = rb.clear_target

    def plan_spy(targets, remaining_s=None):
        snap = {t[0]: (tuple(t[2]["center"]), float(t[2]["radius"]))
                for t in (targets or [])}
        out = orig_plan(targets, remaining_s=remaining_s)
        plan_log.append({
            "t": float(arena.virtual_time_s),
            "pos": (float(rb.pos[0]), float(rb.pos[1])),
            "snap": snap,
            "first": (out[0][0] if out else None),
            "order": [t[0] for t in out],
            "n": len(targets or []),
        })
        return out

    def clear_spy(ch, rec):
        br0 = rb.bounded_region(rec)
        c0 = tuple(br0["center"]) if br0 else None
        r0 = float(br0["radius"]) if br0 else None
        # 决策时（上一次 plan）看到的中心
        prev = None
        for p in reversed(plan_log):
            if ch in p["snap"]:
                prev = p["snap"][ch][0]
                break
        t0 = float(arena.virtual_time_s)
        d0 = float(arena.stats.get("travel_m", 0.0))
        pos0 = (float(rb.pos[0]), float(rb.pos[1]))
        ok = orig_clear(ch, rec)
        t1 = float(arena.virtual_time_s)
        d1 = float(arena.stats.get("travel_m", 0.0))
        br1 = rb.bounded_region(rec)
        c1 = tuple(br1["center"]) if br1 else None
        exec_log.append({
            "ch": int(ch),
            "pos0": pos0,
            "planned_center": prev,
            "center_at_exec": c0,
            "center_after": c1,
            "r0": r0,
            "drift_center": (math.dist(prev, c0) if (prev and c0) else None),
            "hop_planned": (math.dist(pos0, prev) if prev else None),
            "hop_actual": (math.dist(pos0, c0) if c0 else None),
            "actual_s": t1 - t0,
            "actual_m": d1 - d0,
            "ok": bool(ok),
            "cleared": bool(rec.cleared),
            "final_pos": (float(rb.pos[0]), float(rb.pos[1])),
        })
        return ok

    rb.plan_clear_tour = plan_spy
    rb.clear_target = clear_spy
    rep = rb.run()
    rep["seed"] = seed
    rep["_plan_log"] = plan_log
    rep["_exec_log"] = exec_log
    return rep


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    seeds = [20260913 + 100 * i for i in range(n)]
    base = load_base()
    rows = [run_case(s, base) for s in seeds]

    plans = [p for r in rows for p in r["_plan_log"]]
    execs = [e for r in rows for e in r["_exec_log"]]

    print(f"{n} 局：排序决策 {len(plans)} 次，目标执行 {len(execs)} 次\n")

    # ---------- A. 决策时的中心 vs 执行时的中心 ----------
    print("A. 排序决策时刻的中心 vs 执行时刻的中心")
    d = [e["drift_center"] for e in execs if e["drift_center"] is not None]
    if d:
        print(f"   不一致的样本 {len(d)}/{len(execs)}"
              f"（其余 {len(execs)-len(d)} 个在执行时已无有界区域）")
        print(f"   中心漂移：均值 {st.mean(d):.1f} m，中位数 {st.median(d):.1f} m，"
              f"P90 {sorted(d)[int(0.9*len(d))]:.1f} m，最大 {max(d):.1f} m")
        nz = sum(1 for x in d if x > 1e-9)
        print(f"   发生漂移（>0）的比例：{nz}/{len(d)} = {nz/len(d)*100:.1f}%")

    # 计划步长 vs 实际步长
    hp = [e["hop_planned"] for e in execs if e["hop_planned"] is not None]
    ha = [e["hop_actual"] for e in execs if e["hop_actual"] is not None]
    if hp and ha:
        m = min(len(hp), len(ha))
        diff = [abs(ha[i] - hp[i]) for i in range(m)]
        print(f"   '走到中心'的距离：决策时预计均值 {st.mean(hp):.0f} m，"
              f"实际 {st.mean(ha):.0f} m，差均值 {st.mean(diff):.0f} m")

    # ---------- B. 清除成功时，实际清除位置离"区域中心"多远 ----------
    print("\nB. 清除成功的位置 vs 逼近目标（说明'走到中心'这一手有多准）")
    ok = [e for e in execs if e["ok"]]
    pk = [math.dist(e["final_pos"], e["center_at_exec"]) for e in ok
          if e["center_at_exec"]]
    if pk:
        print(f"   成功清除 {len(ok)} 次；清除点到执行时中心："
              f"均值 {st.mean(pk):.1f} m，中位数 {st.median(pk):.1f} m，"
              f"P90 {sorted(pk)[int(0.9*len(pk))]:.1f} m")
    # 清除点离**真源**多远（用 truth 算，衡量整体定位精度）
    truth = {int(s["channel"]): (float(s["x_m"]), float(s["y_m"]))
             for s in (MockArena(seed=seeds[0]).truth() or {}).get("sources", [])}
    print("   （下面按局算清除点到真源的距离）")
    pj = []
    for r in rows:
        tmap = {int(s["channel"]): (float(s["x_m"]), float(s["y_m"]))
                for s in (r.get("truth") or {}).get("sources", [])}
        for e in r["_exec_log"]:
            if e["ok"] and e["ch"] in tmap:
                pj.append(math.dist(e["final_pos"], tmap[e["ch"]]))
    if pj:
        print(f"   清除点到真源：均值 {st.mean(pj):.1f} m，中位数 {st.median(pj):.1f} m，"
              f"P90 {sorted(pj)[int(0.9*len(pj))]:.1f} m（清除半径 20 m）")

    # ---------- C. 排序的第一步是否就是最近的 ----------
    print("\nC. 排序结果的第一步，是否等于'离当前位置最近'的目标")
    bad = 0
    tot = 0
    for p in plans:
        if not p["order"] or len(p["snap"]) < 2:
            continue
        tot += 1
        pos = np.asarray(p["pos"], float)
        nearest = min(p["snap"], key=lambda ch: math.dist(pos, p["snap"][ch][0]))
        if nearest != p["first"]:
            bad += 1
    print(f"   非最近邻开头的比例：{bad}/{tot} = {bad/max(tot,1)*100:.1f}%"
          f"（2-opt 与最近邻不一致的次数）")

    # ---------- D. 目标从'可清'到'被尝试'隔了多久 ----------
    print("\nD. 每个目标被尝试清除时的各项代价分解（按结果分组）")
    for lbl, grp in (("成功", [e for e in execs if e["ok"]]),
                     ("失败/放弃", [e for e in execs if not e["ok"]])):
        if not grp:
            continue
        print(f"   {lbl:<10} {len(grp):>4} 次：实际耗时均值 {st.mean(e['actual_s'] for e in grp):>6.0f} s，"
              f"实际行程均值 {st.mean(e['actual_m'] for e in grp):>6.0f} m"
              f"（= {st.mean(e['actual_m'] for e in grp)/V_ROBOT:>5.0f} s 行程）")

    print(f"\n   总实际耗时：成功 {sum(e['actual_s'] for e in execs if e['ok']):.0f} s，"
          f"失败 {sum(e['actual_s'] for e in execs if not e['ok']):.0f} s")
    tot_s = sum(e["actual_s"] for e in execs)
    print(f"   目标执行占用合计 {tot_s:.0f} s / {n} 局 = {tot_s/n:.0f} s/局"
          f"（预算 1200 s/局）")


if __name__ == "__main__":
    sys.exit(main())
