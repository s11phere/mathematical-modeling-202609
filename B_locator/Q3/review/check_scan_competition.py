"""核查一个关键假设：现行主循环里，"扫描"是不是**本来就已经只在没有可清目标时**才发生？

如果是，那么"预算不够就别扫、直接去清除"这类闸门在结构上就是空的（永远不改变行为）。
这里统计每局：
  * 扫描阶段开始时，场上可清目标数（应为 0，否则说明确实存在竞争）
  * 每轮清理阶段为什么结束（无目标 / 预算不足 / 闸门）
  * 每轮扫描后新产生了几个"可清目标"
  * 以及"扫描阶段净收益"：扫描后新增的可清目标里，最终有几个真被清掉
"""
from __future__ import annotations

import math
import os
import statistics as st
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _SRC)

from p3_arena import MockArena  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402


def run_case(seed, base):
    arena = MockArena(seed=seed)
    rb = P3Robot(arena, P3Config(), base=base, log=None)

    log = []
    orig_plan_scan = rb.plan_scan
    orig_execute_scan = rb.execute_scan
    orig_clear_phase = rb.clear_phase

    state = {}

    def plan_scan_spy(*a, **k):
        state["n_clearable_at_scan_decision"] = len(rb.clear_targets())
        p = orig_plan_scan(*a, **k)
        state["scan_cost"] = (p or {}).get("cost_s")
        return p

    def execute_scan_spy(plan):
        before = {c for c, r in rb.recs.items()
                  if not r.cleared and r.n_bearings >= 2}
        n = orig_execute_scan(plan)
        after = {c for c, r in rb.recs.items()
                 if not r.cleared and r.n_bearings >= 2}
        log.append({"kind": "scan", "t": float(arena.virtual_time_s),
                    "clearable_before": len(before),
                    "new_targets": sorted(after - before),
                    "cost_s": plan.get("cost_s")})
        return n

    def clear_phase_spy():
        before = sum(1 for r in rb.recs.values() if r.cleared)
        n = orig_clear_phase()
        after = sum(1 for r in rb.recs.values() if r.cleared)
        log.append({"kind": "clear", "t0": None, "t": float(arena.virtual_time_s),
                    "cleared": after - before,
                    "remaining": rb.remaining(),
                    "clearable_left": len(rb.clear_targets()),
                    "aborted": bool(rb.abort_clear_phase)})
        return n

    rb.plan_scan = plan_scan_spy
    rb.execute_scan = execute_scan_spy
    rb.clear_phase = clear_phase_spy

    rep = rb.run()
    rep["seed"] = seed
    rep["_log"] = log
    rep["_n_clearable_at_scan"] = state.get("n_clearable_at_scan_decision")
    return rep


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    seeds = [20260913 + 100 * i for i in range(n)]
    base = load_base()
    rows = [run_case(s, base) for s in seeds]

    print(f"{n} 局\n")
    print("【假设核查】扫描决策时场上的可清目标数（若恒为 0，则扫描与清除本来就不竞争）")
    vals = [r["_n_clearable_at_scan"] for r in rows if r["_n_clearable_at_scan"] is not None]
    print(f"  样本 {len(vals)} 次扫描决策：非零次数 = {sum(1 for v in vals if v)}，"
          f"最大 = {max(vals) if vals else '-'}")

    print("\n【每局流程】扫描轮 / 清理轮 / 清理轮结束时剩余预算")
    print(f"{'seed':>9} {'清/源':>7} {'扫描轮':>7} {'清理轮':>7} "
          f"{'清理轮末剩余':>12} {'扫描新目标':>10} {'新目标被清':>10}")
    print("-" * 78)
    tot_new = tot_new_cleared = 0
    for r in rows:
        scans = [e for e in r["_log"] if e["kind"] == "scan"]
        clears = [e for e in r["_log"] if e["kind"] == "clear"]
        new = [c for e in scans for c in e["new_targets"]]
        # 这些新目标里最终被清掉的
        nc = 0
        for ch in new:
            if ch in r["channels"] and r["channels"][ch]["cleared"]:
                nc += 1
        tot_new += len(new)
        tot_new_cleared += nc
        last_rem = clears[-1]["remaining"] if clears else float("nan")
        print(f"{r['seed']:>9} {r['cleared']:>3}/{r['n_sources']:<3} "
              f"{len(scans):>7} {len(clears):>7} {last_rem:>12.0f} "
              f"{len(new):>10} {nc:>10}")

    print("-" * 78)
    print(f"扫描阶段新发现的可清目标合计 {tot_new} 个，其中最终被清除 {tot_new_cleared} 个"
          f"（{tot_new_cleared/max(tot_new,1)*100:.1f}%）")

    ab = sum(1 for r in rows for e in r["_log"]
             if e["kind"] == "clear" and e["aborted"])
    nclear = sum(1 for r in rows for e in r["_log"] if e["kind"] == "clear")
    print(f"清理轮合计 {nclear} 次，其中因'预算不足'收敛 {ab} 次"
          f"（{ab/max(nclear,1)*100:.1f}%）")
    left = sum(r["n_leftover_located"] for r in rows)
    uncl = sum(r["n_sources"] - r["cleared"] for r in rows)
    print(f"末尾'已定位但未清除'合计 {left} 个，占未清除总数 {uncl} 的 "
          f"{left/max(uncl,1)*100:.1f}%")


if __name__ == "__main__":
    sys.exit(main())
