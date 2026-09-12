"""问题 4 诊断：逐源统计"定位估计误差 / 清除尝试次数"，找出清除阶段的浪费点。

    python src/p4_diag.py --cases 5 --scenario directed
"""
from __future__ import annotations

import argparse
import math
import os
import statistics as st
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
from p4_robot import P4Config, P4GridRobot  # noqa: E402
from p4_run import make_arena  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="directed")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    rows = []
    for i in range(a.cases):
        seed = a.seed + 100 * i
        arena = make_arena(a.scenario, seed)
        rb = P4GridRobot(arena, P4Config())
        rep = rb.run()
        truth = {s.channel: (s.x, s.y, s.cone_half, s.r_recv) for s in arena.sources}
        n_fail_before = 0
        n_clear_acts = 0
        for act in arena.actions:
            if act.get("kind") == "clear":
                n_clear_acts += 1
                if act.get("clear_result") != "success":
                    n_fail_before += 1
        # 逐源：最后一次成功清除前的 clear 次数
        per_clear = {}
        for act in arena.actions:
            if act.get("kind") != "clear":
                continue
            ch = act.get("channel")
            per_clear.setdefault(ch, []).append(act.get("clear_result"))
        for ch, (x, y, half, rr) in sorted(truth.items()):
            rec = rb.recs[ch]
            br = rb.bounded_region(rec)
            est = rb.cross_estimate(rec) if rec.n_bearings >= 2 else rb.ray_estimate(rec)
            err = None if est is None else float(np.hypot(est[0] - x, est[1] - y))
            res = per_clear.get(ch, [])
            rows.append({
                "seed": seed, "ch": ch, "dir": half < 180.0,
                "r_src": math.hypot(x, y), "r_recv": rr,
                "n_bear": rec.n_bearings, "cleared": rec.cleared,
                "est_err": err,
                "region_r": None if br is None else float(br["radius"]),
                "n_clear_acts": len(res),
                "n_clear_fail": sum(1 for r in res if r != "success"),
                "dist_to_src_from_last": (
                    None if not rec.meas_pts else
                    float(np.hypot(rec.meas_pts[-1][0] - x, rec.meas_pts[-1][1] - y))),
            })
        print(f"seed {seed}: 清除 {rep['cleared']}/{rep['n_sources']}  "
              f"虚拟 {rep['virtual_time_s']:.0f}s  平均 {rep['avg_clear_time_s'] or 0:.0f}s  "
              f"清零动作 {n_clear_acts}（失败 {n_fail_before}）", flush=True)

    print()
    errs = [r["est_err"] for r in rows if r["est_err"] is not None]
    regs = [r["region_r"] for r in rows if r["region_r"] is not None]
    cf = [r["n_clear_fail"] for r in rows]
    print(f"源数 {len(rows)}：定位估计误差 中位 {st.median(errs):.0f} m  "
          f"均值 {st.mean(errs):.0f} m  最大 {max(errs):.0f} m")
    print(f"         有界区域半径 中位 {st.median(regs):.0f} m  最大 {max(regs):.0f} m")
    print(f"         每源 clear 失败次数 中位 {st.median(cf):.0f}  均值 {st.mean(cf):.1f}  "
          f"最大 {max(cf)}")
    print(f"         未清除 {sum(1 for r in rows if not r['cleared'])} 个")
    if not a.quiet:
        print("\n逐源明细（est_err=定位估计误差, region_r=有界区域半径）：")
        print(f"{'seed':>10}{'ch':>4}{'定向':>5}{'r_src':>7}{'方位':>5}"
              f"{'est_err':>9}{'reg_r':>8}{'clear次':>8}{'失败':>6}  清")
        for r in rows:
            print(f"{r['seed']:>10}{r['ch']:>4}{'Y' if r['dir'] else 'n':>5}"
                  f"{r['r_src']:>7.0f}{r['n_bear']:>5}"
                  f"{(r['est_err'] if r['est_err'] is not None else float('nan')):>9.0f}"
                  f"{(r['region_r'] if r['region_r'] is not None else float('nan')):>8.0f}"
                  f"{r['n_clear_acts']:>8}{r['n_clear_fail']:>6}"
                  f"  {'OK' if r['cleared'] else '--'}")


if __name__ == "__main__":
    main()
