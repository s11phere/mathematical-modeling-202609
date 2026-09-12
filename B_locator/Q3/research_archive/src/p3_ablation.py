"""B 题问题 3：参数灵敏度与消融实验（论文用表）。

    python src/p3_ablation.py --cases 30 --out out/p3

对同一批随机案例（固定种子）比较：
* 距离项系数 λ（问题里"距离项前加入一个系数，可以调节"）
* "无信号"频道的重测间隔
* 消融：不做 2-opt 航路 / 不做顺路补测 / 叠加探索项 / 新频道立刻补第二条方位 / 不做覆盖式试探（改直接清中心）

输出 ``out/p3/ablation.json`` + ``out/p3/ablation.csv``，并打印表格。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics as st
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np  # noqa: E402

from p3_arena import MockArena  # noqa: E402
from p3_expect_field import DEFAULT_BASE_CSV, DEFAULT_FAMILY_DIR  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402
from p3_run import oracle_bound  # noqa: E402


def evaluate(label, seeds, cfg, base, group=""):
    rows = []
    t0 = time.time()
    for s in seeds:
        arena = MockArena(seed=s)
        rb = P3Robot(arena, cfg, base=base)
        rep = rb.run()
        rows.append(rep)
    n_src = sum(r["n_sources"] for r in rows)
    n_cl = sum(r["cleared"] for r in rows)
    tms = [r["avg_clear_time_s"] for r in rows if r["avg_clear_time_s"]]
    return {
        "group": group, "label": label,
        "cases": len(rows),
        "sources": n_src,
        "cleared": n_cl,
        "clear_ratio": n_cl / n_src,
        "cleared_mean": st.mean(r["cleared"] for r in rows),
        "avg_clear_time_s": st.mean(tms) if tms else None,
        "virtual_time_s": st.mean(r["virtual_time_s"] for r in rows),
        "travel_m": st.mean(r["travel_m"] for r in rows),
        "n_measure": st.mean(r["n_measure"] for r in rows),
        "n_scan_rounds": st.mean(r["n_scan_rounds"] for r in rows),
        "n_clear_fail": st.mean(r["n_clear_fail"] for r in rows),
        "n_sweep_aborted": st.mean(r.get("n_sweep_aborted", 0) for r in rows),
        "n_sweep_miss": st.mean(r.get("n_sweep_miss", 0) for r in rows),
        "n_probe_issued": st.mean(r.get("n_probe_issued", 0) for r in rows),
        "n_rejected": sum(r["n_rejected"] for r in rows),
        "wall_s": round(time.time() - t0, 2),
    }


def main():
    ap = argparse.ArgumentParser(description="问题3 参数灵敏度与消融")
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--out", default=os.path.normpath(
        os.path.join(_HERE, "..", "out", "p3")))
    ap.add_argument("--family-dir", default=DEFAULT_FAMILY_DIR)
    ap.add_argument("--base-map", default=DEFAULT_BASE_CSV)
    args = ap.parse_args()

    base = load_base(args.family_dir, args.base_map)
    seeds = [args.seed + 100 * i for i in range(args.cases)]
    D = P3Config().__dict__          # 调参后的默认配置
    trials = []

    def add(group, label, **kw):
        cfg = P3Config(**{**D, **kw})
        trials.append((group, label, cfg))

    # ---- 1) 距离项系数 λ ----
    for w in (0.0, 0.35, 0.75, 1.5, 3.0, 6.0):
        add("距离项系数 λ", f"λ={w}", dist_weight=w)
    # ---- 2) 无信号频道重测间隔 ----
    for g in (250.0, 450.0, 700.0, 1000.0):
        add("无信号重测间隔 (m)", f"gap={g:g}", nosignal_gap_m=g)
    # ---- 3) 消融 ----
    add("消融（默认配置）", "baseline")
    add("消融（默认配置）", "静态航路（阶段内不重规划）", dynamic_replan=False)
    add("消融（默认配置）", "动态+按预算裁剪航路", clear_budget_truncation=True)
    add("消融（默认配置）", "动态 rollout（一步前瞻）", clear_policy="rollout")
    add("消融（默认配置）", "无 2-opt（仅最近邻）", tour="nn")
    add("消融（默认配置）", "2-opt 保第一步为最近邻", tour="nn2opt_keepfirst")
    add("消融（默认配置）", "不顺路补测", enroute_scan=False)
    add("消融（默认配置）", "不顺路补测+多扫描轮", enroute_scan=False,
        min_scan_rounds_before_clear=1, max_rounds=30)
    add("消融（默认配置）", "叠加探索项", field_discovery=True)
    add("消融（默认配置）", "新频道立刻补第二方位",
        second_bearing_refine=True, refine_travel_cap_m=300.0)
    add("消融（默认配置）", "不做覆盖式试探（只清中心，封顶 1 点）",
        probe_unlimited=False, probe_max_points=1)
    add("消融（默认配置）", "覆盖式试探按点数封顶 60（破坏覆盖保证）",
        probe_unlimited=False, probe_max_points=60)
    # ---- 4) 预算分配：扫描 vs 清除（详见 review/P3-design.md §5.3）----
    # 结论：全部不优于 baseline。扫描时间上限、近点子集、剩余预算裁剪都属于
    # "对可达性做事前判定"，而 estimate_clear_cost 是**准确到略悲观**的
    # （中位数实际/估计 = 0.87），所以预判并不能筛掉真正的浪费；
    # 反而因为提前放弃远处目标而减少了收益。
    add("预算分配（扫描 vs 清除）", "扫描闸门（扫完须够清最近目标）",
        scan_budget_gate=True, scan_gate_factor=1.2, scan_gate_margin=80.0)
    add("预算分配（扫描 vs 清除）", "扫描时间上限 50% 预算",
        scan_budget_gate=True, scan_budget_frac=0.50)
    add("预算分配（扫描 vs 清除）", "清理近点子集（可达性预筛）", clear_shortlist=True)
    add("预算分配（扫描 vs 清除）", "贪心+剩余预算可达（greedy_cost）",
        clear_policy="tour_greedy_cost")
    add("消融（默认配置）", "网格步长 200 m", grid_step=200.0)
    add("消融（默认配置）", "网格步长 50 m", grid_step=50.0)

    results = [evaluate(label, seeds, cfg, base, group)
               for (group, label, cfg) in trials]
    ob = oracle_bound(seeds)
    oracle = {"cleared_mean": st.mean(o[0] for o in ob),
              "clear_ratio": sum(o[0] for o in ob) / sum(o[1] for o in ob),
              "note": "上界：预知全部源位置 + 最优航路 + 到点即清除（无需发现与二次定位）"}

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "ablation.json"), "w", encoding="utf-8") as f:
        json.dump({"seeds": seeds, "cases": args.cases, "defaults": D,
                   "oracle": oracle, "results": results}, f,
                  ensure_ascii=False, indent=2)
    cols = ["group", "label", "clear_ratio", "cleared_mean", "avg_clear_time_s",
            "virtual_time_s", "travel_m", "n_measure", "n_scan_rounds",
            "n_clear_fail", "n_sweep_aborted", "n_sweep_miss", "n_probe_issued",
            "n_rejected"]
    with open(os.path.join(args.out, "ablation.csv"), "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k) for k in cols})

    # ---- 打印 ----
    print(f"案例 {args.cases} 局（种子 {seeds[0]}..{seeds[-1]}），"
          f"干扰源合计 {sum(o[1] for o in ob)} 个")
    print(f"{'组':<18}{'配置':<28}{'清除率':>8}{'清除数':>8}"
          f"{'平均时间':>10}{'行程(m)':>9}{'检测数':>8}")
    print("-" * 92)
    for r in results:
        print(f"{r['group']:<18}{r['label']:<28}{r['clear_ratio']:>8.3f}"
              f"{r['cleared_mean']:>8.2f}{r['avg_clear_time_s']:>10.1f}"
              f"{r['travel_m']:>9.0f}{r['n_measure']:>8.1f}")
    print("-" * 92)
    print(f"{'理论上界（预知位置）':<44}{oracle['clear_ratio']:>8.3f}"
          f"{oracle['cleared_mean']:>8.2f}")
    print(f"\n已写入 {os.path.join(args.out, 'ablation.json')} 与 ablation.csv")


if __name__ == "__main__":
    main()
