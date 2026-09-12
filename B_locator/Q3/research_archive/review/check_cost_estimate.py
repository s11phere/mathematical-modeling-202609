"""校验 estimate_clear_cost 的准度：估计值 vs 实际耗时。

如果估计系统性偏乐观（实际远大于估计），那么任何"按估计值判断可达性"的闸门
（扫描闸门 / 近点子集 / 剩余预算裁剪的 "reachable" 判定）都会误判 ——
这正好解释了为什么这些变体全部变差。

对每个 clean_target 记录：
  估计代价 estimate_clear_cost（含 probe_cap 乐观封顶）
  实际耗时（虚拟时间差）
  实际行程（arena.stats.travel_m 差）
  结果 success / miss / no_budget
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

from p3_arena import MockArena, V_ROBOT  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402


def run_case(seed, base):
    arena = MockArena(seed=seed)
    rb = P3Robot(arena, P3Config(), base=base, log=None)
    recs = []
    orig = rb.clear_target

    def spy(ch, rec):
        br = rb.bounded_region(rec)
        est = None
        if br is not None:
            est = rb.estimate_clear_cost(br, from_pos=rb.pos,
                                         probe_cap=rb.cfg.optimistic_probe_steps)
        t0 = float(arena.virtual_time_s)
        d0 = float(arena.stats.get("travel_m", 0.0))
        ok = orig(ch, rec)
        t1 = float(arena.virtual_time_s)
        d1 = float(arena.stats.get("travel_m", 0.0))
        recs.append({
            "ch": int(ch), "est_s": est, "actual_s": t1 - t0,
            "actual_m": d1 - d0,
            "r_star": (br["radius"] if br else None),
            "n_bearings": rec.n_bearings,
            "ok": bool(ok),
            "cleared": bool(rec.cleared),
        })
        return ok

    rb.clear_target = spy
    rep = rb.run()
    rep["_recs"] = recs
    rep["seed"] = seed
    return rep


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    seeds = [20260913 + 100 * i for i in range(n)]
    base = load_base()
    rows = [run_case(s, base) for s in seeds]
    all_r = [r for row in rows for r in row["_recs"]]
    good = [r for r in all_r if r["est_s"] is not None]

    print(f"{n} 局，clear_target 调用合计 {len(all_r)} 次"
          f"（其中 {len(good)} 次有定位区域可估代价）\n")

    ok = [r for r in good if r["ok"]]
    bad = [r for r in good if not r["ok"]]
    print(f"{'类别':<16}{'次数':>6}{'估计均(s)':>11}{'实际均(s)':>11}"
          f"{'实际/估计':>10}{'实际行程均(m)':>14}")
    for lbl, grp in (("全部", good), ("成功清除", ok), ("未清除", bad)):
        if not grp:
            continue
        e = st.mean(r["est_s"] for r in grp)
        a = st.mean(r["actual_s"] for r in grp)
        print(f"{lbl:<16}{len(grp):>6}{e:>11.0f}{a:>11.0f}"
              f"{(a/e if e else float('nan')):>10.2f}"
              f"{st.mean(r['actual_m'] for r in grp):>14.0f}")

    if ok:
        ratios = [r["actual_s"] / r["est_s"] for r in ok if r["est_s"] > 0]
        ratios.sort()
        print(f"\n成功清除的 '实际/估计' 比值：中位数 {st.median(ratios):.2f}，"
              f"P25 {ratios[len(ratios)//4]:.2f}，P75 {ratios[3*len(ratios)//4]:.2f}，"
              f"最大 {max(ratios):.2f}")
        over = sum(1 for x in ratios if x > 1.0)
        print(f"  实际超过估计的比例：{over}/{len(ratios)} = {over/len(ratios)*100:.0f}%")

    # 按区域半径分桶看低估程度
    print("\n按定位半径 r* 分桶（成功清除）：")
    print(f"{'r* (m)':>14}{'次数':>6}{'估计均':>9}{'实际均':>9}{'比值':>8}")
    buckets = [(0, 20), (20, 60), (60, 120), (120, 200), (200, 1e9)]
    for lo, hi in buckets:
        grp = [r for r in ok if r["r_star"] is not None and lo <= r["r_star"] < hi]
        if not grp:
            continue
        e = st.mean(r["est_s"] for r in grp)
        a = st.mean(r["actual_s"] for r in grp)
        lbl = f"[{lo:.0f},{hi:.0f})" if hi < 1e8 else f"[{lo:.0f},inf)"
        print(f"{lbl:>14}{len(grp):>6}{e:>9.0f}{a:>9.0f}{(a/e if e else float('nan')):>8.2f}")

    tot_est = sum(r["est_s"] for r in good)
    tot_act = sum(r["actual_s"] for r in good)
    print(f"\n合计：估计 {tot_est:.0f} s，实际 {tot_act:.0f} s，"
          f"总低估倍数 {tot_act/tot_est:.2f}×")


if __name__ == "__main__":
    sys.exit(main())
