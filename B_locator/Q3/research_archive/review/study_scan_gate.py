"""策略对照实验（最终版）：关于"剩余时间不够时是否该放弃扫描、直奔最优清除路线"。

诊断事实（30 局，见 review/out_leftover_reach.txt、out_scan_competition.txt）：
  * 进入清理队列的 200 个频道，**100% 的第二条方位都来自扫描阶段**（原点只给出 1 条）；
    所以"完全不扫描"会让清除数变成 0（对照 M）。
  * 但扫描阶段吃掉约 1016 s / 1200 s，而末尾 49 个"已定位未清除"的目标里
    有 26 个（53%）在变成可清目标时**剩余时间完全够走去清**（如 seed 20260913
    频道14：剩余 981 s、只需 91 s、区域中心 351 m），却始终没被排在航路第一位。
  * 清理轮因"预算不足"收敛的比例高达 54.8%。

于是本实验比较三类策略：
  ① 扫描闸门（扫完必须还够清最近目标）与扫描时间上限（cap_frac）
  ② 清理航路：可达近点子集 / 收益排序 / 距离排序 / 剩余预算裁剪
  ③ 上界：只对**本局实际已定位**的目标，在 1200 s 内最优航路能清几个
     （⇒ 把"发现能力"与"排序决策"的贡献分开）

用法：
  python review/study_scan_gate.py --cases 60
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _SRC)

from p3_arena import MockArena, V_ROBOT  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402

T_CLEAR_OK, T_MEASURE, T_SWITCH, T_CLEAR_FAIL = 5.0, 5.0, 1.0, 3.0

VARIANTS = [
    ("A  baseline（现行默认）", {}),
    ("B  scan_gate", dict(scan_budget_gate=True, scan_gate_factor=1.2,
                          scan_gate_margin=80.0)),
    ("C  scan_cap_frac50", dict(scan_budget_gate=True, scan_budget_frac=0.50)),
    ("D  shortlist（近点子集）", dict(clear_shortlist=True)),
    ("E  tour_greedy_cost", dict(clear_policy="tour_greedy_cost")),
    ("F  tour_nearest", dict(tour="nn")),
    ("G  truncation（剩余预算裁剪）", dict(clear_budget_truncation=True)),
    ("H  gate + greedy_cost", dict(scan_budget_gate=True, scan_gate_factor=1.2,
                                   scan_gate_margin=80.0,
                                   clear_policy="tour_greedy_cost")),
]


def evaluate(label, kw, seeds, base):
    cfg = P3Config(**{**P3Config().__dict__, **kw})
    rows = []
    t0 = time.time()
    for s in seeds:
        arena = MockArena(seed=s)
        rb = P3Robot(arena, cfg, base=base, log=None)
        rep = rb.run()
        rep["seed"] = s
        rows.append(rep)
    n_src = sum(r["n_sources"] for r in rows)
    n_cl = sum(r["cleared"] for r in rows)
    tms = [r["avg_clear_time_s"] for r in rows if r["avg_clear_time_s"]]
    return {
        "label": label, "cases": len(rows),
        "clear_ratio": n_cl / n_src,
        "cleared_mean": st.mean(r["cleared"] for r in rows),
        "cleared_per_case": [r["cleared"] for r in rows],
        "avg_clear_time_s": st.mean(tms) if tms else None,
        "travel_m": st.mean(r["travel_m"] for r in rows),
        "t_scan_s": st.mean(r.get("t_scan_s", 0.0) for r in rows),
        "t_clear_s": st.mean(r.get("t_clear_s", 0.0) for r in rows),
        "n_scan_gated": st.mean(r.get("n_scan_gated", 0) for r in rows),
        "n_leftover_located": st.mean(r.get("n_leftover_located", 0) for r in rows),
        "n_rejected": sum(r["n_rejected"] for r in rows),
        "wall_s": round(time.time() - t0, 1),
    }


def oracle_on_located(cfg, seeds, base, budget_s=1200.0):
    """上界：只对本局**实际曾经定位**（≥2 方位且有界区域）的目标，在预算内最优航路能清几个。

    注意必须统计**所有**曾定位的目标（含已清除的），否则会把已经花掉的预算
    重复计算。这是"排序决策"的理论天花板：它不改变发现能力，
    只假设航路排序完美、且走到区域中心即可清除。
    """
    out = []
    for s in seeds:
        arena = MockArena(seed=s)
        rb = P3Robot(arena, cfg, base=base, log=None)
        rb.run()
        centers = []
        for ch, rec in rb.recs.items():
            if rec.n_bearings < 2:
                continue
            br = rb.bounded_region(rec)
            if br is not None:
                centers.append(tuple(br["center"]))
        # 从原点出发：对可达点集做最近邻 + 2-opt，再按预算取前缀长度
        if not centers:
            out.append(0)
            continue
        pos = np.asarray([0.0, 0.0])
        left = list(centers)
        seq = []
        while left:
            j = min(range(len(left)),
                    key=lambda i: math.dist(pos, left[i]))
            seq.append(left.pop(j))
            pos = np.asarray(seq[-1])
        # 2-opt（开放路径）
        def plen(pts):
            d = math.dist((0.0, 0.0), pts[0])
            for a, b in zip(pts, pts[1:]):
                d += math.dist(a, b)
            return d
        improved = True
        best = plen(seq)
        while improved:
            improved = False
            for i in range(len(seq) - 1):
                for j in range(i + 1, len(seq)):
                    cand = seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]
                    d = plen(cand)
                    if d < best - 1e-9:
                        seq, best, improved = cand, d, True
        # 逐个累计"走到中心 + 检测 + 清除"，超预算即停
        used, n, pos = 0.0, 0, (0.0, 0.0)
        for c in seq:
            cost = (math.dist(pos, c) / V_ROBOT + T_MEASURE + T_SWITCH + T_CLEAR_OK)
            if used + cost > budget_s:
                break
            used += cost
            pos = c
            n += 1
        out.append(n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--out", default=os.path.join(_HERE, "out_scan_gate.json"))
    ap.add_argument("--oracle", action="store_true", help="附带计算'已定位目标'的上界")
    args = ap.parse_args()

    seeds = [args.seed + 100 * i for i in range(args.cases)]
    base = load_base()
    print(f"{args.cases} 局，基准={'图族' if hasattr(base, 'select') else '单张'}\n")

    res = [evaluate(lbl, kw, seeds, base) for lbl, kw in VARIANTS]

    hdr = (f"{'变体':<28}{'清除率':>8}{'清除数':>7}{'定位清除时间':>12}"
           f"{'行程(m)':>9}{'扫描s':>7}{'清理s':>7}{'已定位未清':>10}")
    print(hdr)
    print("-" * len(hdr))
    base_ratio = res[0]["clear_ratio"]
    for r in res:
        act = r["avg_clear_time_s"] if r["avg_clear_time_s"] is not None else float("nan")
        d = (r["clear_ratio"] - base_ratio) * 100
        mark = "" if r["label"].startswith("A") else f"  {d:+.1f}pt"
        print(f"{r['label']:<28}{r['clear_ratio']:>8.4f}{r['cleared_mean']:>7.3f}"
              f"{act:>12.1f}{r['travel_m']:>9.0f}{r['t_scan_s']:>7.0f}"
              f"{r['t_clear_s']:>7.0f}{r['n_leftover_located']:>10.2f}{mark}")

    print("\n与 baseline 的**配对**差异（同种子逐局清除数）：")
    print(f"{'变体':<28}{'均值差':>9}{'标准误':>9}{'胜/平/负':>12}{'95%CI':>18}")
    b = res[0]["cleared_per_case"]
    for r in res[1:]:
        dd = [x - y for x, y in zip(r["cleared_per_case"], b)]
        m = st.mean(dd)
        sd = st.stdev(dd) if len(dd) > 1 else 0.0
        se = sd / math.sqrt(len(dd)) if dd else 0.0
        w = sum(1 for x in dd if x > 0)
        l = sum(1 for x in dd if x < 0)
        t = sum(1 for x in dd if x == 0)
        stars = " **" if se > 0 and abs(m) / se >= 2.0 else ""
        print(f"{r['label']:<28}{m:>+9.3f}{se:>9.3f}{f'{w}/{t}/{l}':>12}"
              f"{f'[{m-1.96*se:+.2f},{m+1.96*se:+.2f}]':>18}{stars}")

    if args.oracle:
        print("\n【上界】只对本局实际曾定位的目标、1200 s 内最优航路可清除数：")
        ob = oracle_on_located(P3Config(), seeds, base)
        print(f"  上界均值 {st.mean(ob):.3f} 个/局"
              f"（baseline 实际 {res[0]['cleared_mean']:.3f} 个/局）")
        print(f"  上界总清除 {sum(ob)} 个；baseline 总清除 "
              f"{sum(res[0]['cleared_per_case'])} 个")
        with open(args.out.replace(".json", "_oracle.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"seeds": seeds, "oracle_on_located": ob}, f)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"cases": args.cases, "seeds": seeds, "results": res},
                  f, ensure_ascii=False, indent=2)
    print(f"\n已写入 {args.out}")


if __name__ == "__main__":
    sys.exit(main())
