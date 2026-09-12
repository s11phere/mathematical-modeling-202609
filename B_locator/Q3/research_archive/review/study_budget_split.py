"""诊断：每局的时间到底花在哪（扫描 / 清理 / 行程），以及"清完最后一个目标时还剩多少"。

直接驱动 P3Robot 并给 scan_at / sweep_clear / measure / do_clear 打点，
按"扫描阶段"与"清理阶段"分别累计虚拟时间。
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

from p3_arena import MockArena, T_CLEAR_FAIL, T_CLEAR_OK, T_MEASURE, T_SWITCH, V_ROBOT  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402


def run_case(seed, base, cfg=None):
    arena = MockArena(seed=seed)
    rb = P3Robot(arena, cfg or P3Config(), base=base, log=None)

    acc = {"scan": 0.0, "clear": 0.0, "other": 0.0}
    last_t = [0.0]
    phase = ["init"]

    orig_scan_at = rb.scan_at
    orig_clear_target = rb.clear_target
    orig_measure = rb.measure
    orig_do_clear = rb.do_clear
    orig_clear_phase = rb.clear_phase

    def mark(new_phase):
        t = float(arena.virtual_time_s)
        acc[phase[0]] = acc.get(phase[0], 0.0)
        phase[0] = new_phase
        last_t[0] = t

    def scan_at_spy(x, y, chans):
        phase[0] = "scan"
        return orig_scan_at(x, y, chans)

    def clear_phase_spy():
        phase[0] = "clear"
        return orig_clear_phase()

    def measure_spy(x, y, ch):
        t0 = float(arena.virtual_time_s)
        r = orig_measure(x, y, ch)
        dt = float(arena.virtual_time_s) - t0
        acc[phase[0]] = acc.get(phase[0], 0.0) + dt
        return r

    def do_clear_spy(x, y, ch):
        t0 = float(arena.virtual_time_s)
        r = orig_do_clear(x, y, ch)
        dt = float(arena.virtual_time_s) - t0
        acc[phase[0]] = acc.get(phase[0], 0.0) + dt
        return r

    rb.scan_at = scan_at_spy
    rb.clear_phase = clear_phase_spy
    rb.measure = measure_spy
    rb.do_clear = do_clear_spy

    rep = rb.run()
    rep["seed"] = seed
    st_ = arena.stats
    rep["_t_scan"] = acc.get("scan", 0.0)
    rep["_t_clear"] = acc.get("clear", 0.0)
    rep["_travel"] = float(st_.get("travel_m", 0.0))
    # 还剩几个"已定位但没清掉"的目标（清理阶段的尾巴）
    rep["_leftover_located"] = sum(
        1 for r in rb.recs.values()
        if not r.cleared and r.n_bearings >= 2)
    return rep


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    seeds = [20260913 + 100 * i for i in range(n)]
    base = load_base()
    rows = [run_case(s, base) for s in seeds]

    print(f"{n} 局，基准={'图族' if hasattr(base, 'select') else '单张'}\n")
    print(f"{'seed':>9} {'清/源':>7} {'vtime':>7} {'行程s':>7} {'扫描s':>7} "
          f"{'清理s':>7} {'清完时剩余':>9} {'已定位未清':>9}")
    print("-" * 80)
    for r in rows:
        tv = r["travel_m"] / V_ROBOT
        print(f"{r['seed']:>9} {r['cleared']:>3}/{r['n_sources']:<3} "
              f"{r['virtual_time_s']:>7.0f} {tv:>7.0f} {r['_t_scan']:>7.0f} "
              f"{r['_t_clear']:>7.0f} {r['remaining_budget_s']:>9.0f} "
              f"{r['_leftover_located']:>9}")

    print("-" * 80)
    print(f"{'均值':>9} "
          f"{st.mean(r['clear_ratio'] for r in rows):>7.3f} "
          f"{st.mean(r['virtual_time_s'] for r in rows):>7.0f} "
          f"{st.mean(r['travel_m'] for r in rows)/V_ROBOT:>7.0f} "
          f"{st.mean(r['_t_scan'] for r in rows):>7.0f} "
          f"{st.mean(r['_t_clear'] for r in rows):>7.0f} "
          f"{st.mean(r['remaining_budget_s'] for r in rows):>9.0f} "
          f"{st.mean(r['_leftover_located'] for r in rows):>9.2f}")

    tot = sum(r["n_sources"] for r in rows)
    cl = sum(r["cleared"] for r in rows)
    print(f"\n合计清除 {cl}/{tot} = {cl/tot:.4f}")
    print(f"末尾仍'已定位但未清除'的目标合计 {sum(r['_leftover_located'] for r in rows)} 个"
          f"（占未清除总数的 {sum(r['_leftover_located'] for r in rows)/(tot-cl)*100:.1f}%）")

    with open(os.path.join(_HERE, "out_time_budget.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    sys.exit(main())
