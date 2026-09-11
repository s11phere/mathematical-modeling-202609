# -*- coding: utf-8 -*-
"""B 题问题一：算例生成、逐例求解与两组随机扫描（论文数值的唯一来源）。

运行（在扁平的 Q1/ 目录下）：
    python p1_experiments.py                  # 生成算例 + 求解 + 两组扫描
    python p1_experiments.py --skip-sweep     # 只跑 5 组算例

产出（默认写到本文件所在目录）：
    p1_case01.csv ~ p1_case05.csv   5 组自造良态算例（后三列为真值，仅自检用）
    p1_case01.truth.json ~ ...      每组算例的真值与方位统计
    p1_results.jsonl                逐例求解结果（全字段）
    p1_summary.json                 算例汇总 + 两组随机扫描统计 + 元信息

算例生成使用固定种子（默认 20260901），同种子下逐字节可复现；两组随机扫描分别使用
固定种子 17（两测点构型，20000 次）与 5（3~6 个检测点的良态构型，4000 次）。
覆盖判据一律按全精度几何计算（analyse() 落盘的顶点/直径为 4 位小数，直接反算会引入
约 1e-4 m 的舍入噪声，不能用于统计）。
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p1_intersection as P                                      # noqa: E402

R_ARENA = 1800.0                          # 目标区域半径（m）
R_RECV_MIN, R_RECV_MAX = 1000.0, 1500.0   # 有效接收距离范围（m）
NEAR_R = 5.0                              # 近场阈值（m）
DEFAULT_SEED = 20260901
SWEEP_TWO_POINT = {"n_trials": 20000, "seed": 17, "r_max": 1800.0}
SWEEP_WELL_COND = {"n_trials": 4000, "seed": 5, "min_gap": 3.0,
                   "dist": (300.0, 1500.0), "m_choices": (3, 4, 5, 6)}
CASE_FIELDS = ["det_id", "x_m", "y_m", "svd_deg", "true_svd_deg",
               "true_az_err_deg", "dist_m"]
CASE_LABELS = ["A1", "A2", "A3", "A4", "A5"]


def wrap360(a):
    return a % 360.0


def bearing(p, q):
    """p 处指向 q 的方位角（度）"""
    return wrap360(math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])))


def in_cone(src, p, half_deg):
    """点 p 是否落在以 src 为顶点、沿定向方向的 ±half_deg 锥内（全向 half=180）"""
    if half_deg >= 180.0:
        return True
    return abs(P.ang_diff(bearing(src["xy"], p), src["dir_deg"])) <= half_deg + 1e-12


def measure(src, p):
    """按题目附录规则返回一次检测结果（不含示向度误差）"""
    d = math.dist(p, src["xy"])
    if d > src["r_recv"]:
        return "no_signal", None
    if not in_cone(src, p, src["cone_half"]):
        return "no_signal", None
    if d <= NEAR_R:
        return "near", None
    return "direction", bearing(p, src["xy"])


# --------------------------------------------------------------------------
# 算例生成（随机数调用序列固定，同种子逐字节可复现）
# --------------------------------------------------------------------------
def make_case_p1(rng, n_pts=3, min_az_gap=25.0, min_dist=150.0,
                 max_dist=1300.0, spread=140.0):
    """生成一组"良态"算例：检测点分布在干扰源四周一定方位张角内，且有最小间隔与距离。"""
    ang = rng.uniform(0, 2 * math.pi)
    rad = rng.uniform(50, 0.75 * R_ARENA)
    G = (rad * math.cos(ang), rad * math.sin(ang))
    src = {"xy": G, "r_recv": rng.uniform(R_RECV_MIN, R_RECV_MAX),
           "cone_half": 180.0, "dir_deg": None}

    n = max(2, n_pts)
    base = rng.uniform(0, 360)
    span = 2 * spread
    while n * min_az_gap > span:
        min_az_gap *= 0.85
    offs = np.sort(rng.uniform(-spread, spread, size=n))
    for _ in range(200):
        gaps = np.diff(offs)
        if len(gaps) == 0 or gaps.min() >= min_az_gap:
            break
        offs = np.sort(rng.uniform(-spread, spread, size=n))

    pts, azs = [], []
    for o in offs:
        a = math.radians((base + o) % 360.0)
        for _try in range(80):
            d = rng.uniform(min_dist, min(max_dist, src["r_recv"]))
            p = (G[0] + d * math.cos(a), G[1] + d * math.sin(a))
            if math.hypot(*p) <= R_ARENA:
                pts.append(p)
                azs.append(bearing(p, G))
                break
    if len(pts) < 2:
        return [], {"error": "failed to build well-conditioned case"}

    errs = rng.uniform(-P.BEARING_ERR, P.BEARING_ERR, size=len(pts))
    rows = []
    for i, (p, e) in enumerate(zip(pts, errs), start=1):
        res, svd = measure(src, p)
        if res != "direction":
            continue
        rows.append({
            "det_id": i,
            "x_m": round(p[0], 3),
            "y_m": round(p[1], 3),
            "svd_deg": round(wrap360(svd + e), 2),
            "true_svd_deg": round(svd, 4),
            "true_az_err_deg": round(e, 4),
            "dist_m": round(math.dist(p, G), 3),
        })
    truth = {"source_xy": [round(G[0], 3), round(G[1], 3)],
             "r_recv_m": round(src["r_recv"], 3),
             "type": "omnidirectional", "dir_deg": None,
             "bearing_error_bound_deg": P.BEARING_ERR,
             "azimuth_span_deg": round(float(max(azs) - min(azs)), 2),
             "min_azimuth_gap_deg": round(float(np.min(np.diff(np.sort(azs)))), 2)
             if len(azs) > 1 else None,
             "n_detection_points": len(rows)}
    return rows, truth


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def gen_cases(out_dir, seed=DEFAULT_SEED, n_cases=5):
    """生成 n_cases 组算例，返回 (文件路径, 真值) 列表。"""
    rng = np.random.default_rng(seed)
    out = []
    for k in range(n_cases):
        rows, truth = make_case_p1(rng, n_pts=int(rng.integers(3, 7)))
        name = "p1_case%02d" % (k + 1)
        csv_path = os.path.join(out_dir, name + ".csv")
        truth_path = os.path.join(out_dir, name + ".truth.json")
        write_csv(csv_path, rows, CASE_FIELDS)
        with open(truth_path, "w", encoding="utf-8") as f:
            json.dump(truth, f, ensure_ascii=False, indent=2)
        out.append((csv_path, truth_path))
    return out


# --------------------------------------------------------------------------
# 全精度求解（统计用）
# --------------------------------------------------------------------------
def solve_full(pts, svds):
    """返回 dict：status / D / half / max_vertex_dist / ratio / excess / covers。"""
    V, st = P.region_by_vertices(pts, svds)
    if st == "empty":
        return {"status": "empty"}
    if P.region_is_unbounded(list(svds)) is not None:
        return {"status": "unbounded"}
    if st != "polygon":
        return {"status": "degenerate"}
    D, (A, B) = P.diameter(V)
    M = 0.5 * (A + B)
    dists = np.linalg.norm(V - M, axis=1)
    k = int(np.argmax(dists))
    maxr = float(dists[k])
    half = D / 2.0
    ua, ub = A - V[k], B - V[k]
    na, nb = float(np.linalg.norm(ua)), float(np.linalg.norm(ub))
    # 覆盖成立时最远顶点就是直径端点（ua 或 ub 为零向量），该处的张角无定义
    angle = None
    if na > 1e-12 and nb > 1e-12:
        cosang = float(ua @ ub / (na * nb))
        angle = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
    return {"status": "bounded", "D": float(D), "half": float(half),
            "max_vertex_dist": maxr, "ratio": maxr / half,
            "excess": maxr - half, "covers": bool(maxr <= half + 1e-9),
            "worst_vertex_angle_deg": angle}


def run_cases(case_paths):
    """逐例求解（analyse 落盘 4 位小数 + 全精度比值与张角）。"""
    results = []
    for i, (csv_path, truth_path) in enumerate(case_paths):
        res = P.run_case_csv(csv_path, truth_path)
        res["case"] = os.path.basename(csv_path)
        res["label"] = CASE_LABELS[i] if i < len(CASE_LABELS) else "C%d" % (i + 1)
        if res["status"] == "bounded":
            rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
            pts = [(float(r["x_m"]), float(r["y_m"])) for r in rows]
            svds = [float(r["svd_deg"]) for r in rows]
            full = solve_full(pts, svds)
            res["ratio"] = round(full["ratio"], 6)
            res["excess_m"] = round(full["excess"], 4)
            res["excess_pct"] = round(100.0 * full["excess"] / full["half"], 4)
            ang = full["worst_vertex_angle_deg"]
            res["worst_vertex_angle_deg"] = None if ang is None else round(ang, 2)
        results.append(res)
    return results


# --------------------------------------------------------------------------
# 两组随机扫描：统计"直径圆覆盖定位区域"的失败率与最坏比值
# --------------------------------------------------------------------------
def sweep_two_point(n_trials=SWEEP_TWO_POINT["n_trials"], seed=SWEEP_TWO_POINT["seed"],
                    r_max=SWEEP_TWO_POINT["r_max"]):
    """两测点构型：检测点落在半径 r_max 的目标区域内，方位差 3°~179°，只统计有界者。"""
    rng = random.Random(seed)
    n_bounded = n_fail = 0
    worst = None
    for _ in range(n_trials):
        dth = rng.uniform(3.0, 179.0)
        th1 = rng.uniform(90.0, 270.0)
        th2 = (th1 + dth) % 360.0
        r1, r2 = rng.uniform(150.0, r_max), rng.uniform(150.0, r_max)
        A = (r1 * math.cos(math.radians(th1 + 180.0)),
             r1 * math.sin(math.radians(th1 + 180.0)))
        B = (r2 * math.cos(math.radians(th2 + 180.0)),
             r2 * math.sin(math.radians(th2 + 180.0)))
        if math.hypot(*A) > r_max or math.hypot(*B) > r_max:
            continue
        st = solve_full([A, B], [th1, th2])
        if st["status"] != "bounded":
            continue
        n_bounded += 1
        if worst is None or st["ratio"] > worst["ratio"]:
            worst = {"S1": [round(A[0], 3), round(A[1], 3), round(th1, 4)],
                     "S2": [round(B[0], 3), round(B[1], 3), round(th2, 4)],
                     "D_m": round(st["D"], 4), "max_vertex_dist_m": round(st["max_vertex_dist"], 4),
                     "ratio": round(st["ratio"], 6), "covers": st["covers"]}
        if not st["covers"]:
            n_fail += 1
    return {"n_trials": n_trials, "seed": seed, "r_max_m": r_max,
            "n_bounded": n_bounded, "n_fail": n_fail,
            "fail_pct": 100.0 * n_fail / max(n_bounded, 1),
            "worst_ratio": None if worst is None else worst["ratio"],
            "worst_config": worst}


def sweep_well_conditioned(n_trials=SWEEP_WELL_COND["n_trials"],
                           seed=SWEEP_WELL_COND["seed"],
                           min_gap=SWEEP_WELL_COND["min_gap"],
                           dist=SWEEP_WELL_COND["dist"],
                           m_choices=SWEEP_WELL_COND["m_choices"]):
    """3~6 个检测点的良态构型：方位角最小间隔 > min_gap，检测点到原点距离在 dist 内。"""
    rng = random.Random(seed)
    n_bounded = n_fail = 0
    per_m = {str(m): {"bounded": 0, "fail": 0} for m in m_choices}
    worst = None
    for _ in range(n_trials):
        m = rng.choice(list(m_choices))
        angs = sorted(rng.uniform(0.0, 360.0) for _ in range(m))
        gaps = [min((angs[i] - angs[j]) % 360.0, (angs[j] - angs[i]) % 360.0)
                for i in range(m) for j in range(i + 1, m)]
        if min(gaps) <= min_gap:
            continue
        pts, svds = [], []
        for t in angs:
            rr = rng.uniform(dist[0], dist[1])
            pts.append((rr * math.cos(math.radians(t)), rr * math.sin(math.radians(t))))
            svds.append((t + 180.0) % 360.0)
        st = solve_full(pts, svds)
        if st["status"] != "bounded":
            continue
        n_bounded += 1
        per_m[str(m)]["bounded"] += 1
        if worst is None or st["ratio"] > worst["ratio"]:
            worst = {"m": m, "pts": [[round(p[0], 3), round(p[1], 3)] for p in pts],
                     "svds_deg": [round(s, 4) for s in svds],
                     "D_m": round(st["D"], 4), "max_vertex_dist_m": round(st["max_vertex_dist"], 4),
                     "ratio": round(st["ratio"], 6), "covers": st["covers"]}
        if not st["covers"]:
            n_fail += 1
            per_m[str(m)]["fail"] += 1
    for v in per_m.values():
        v["fail_pct"] = round(100.0 * v["fail"] / max(v["bounded"], 1), 4)
    return {"n_trials": n_trials, "seed": seed, "min_gap_deg": min_gap,
            "dist_range_m": list(dist), "m_choices": list(m_choices),
            "n_bounded": n_bounded, "n_fail": n_fail,
            "fail_pct": 100.0 * n_fail / max(n_bounded, 1),
            "worst_ratio": None if worst is None else worst["ratio"],
            "worst_config": worst, "per_m": per_m}


# --------------------------------------------------------------------------
# 汇总与主程序
# --------------------------------------------------------------------------
def build_summary(case_paths, results, sweep1, sweep2, seed):
    ok = [r for r in results if r["status"] == "bounded"]
    cases_summary = {
        "n_cases": len(results),
        "n_bounded": len(ok),
        "n_unbounded": sum(1 for r in results if r["status"] == "unbounded"),
        "n_degenerate": sum(1 for r in results if r["status"] == "degenerate"),
        "n_empty": sum(1 for r in results if r["status"] == "empty"),
        "diameter_m_range": [min(r["diameter_m"] for r in ok),
                             max(r["diameter_m"] for r in ok)] if ok else None,
        "n_diameter_circle_misses": sum(1 for r in ok if not r["diameter_circle_covers"]),
        "min_circle_over_half_diameter_max": max(
            r["min_circle_over_half_diameter"] for r in ok) if ok else None,
        "n_truth_inside_region": sum(1 for r in ok if r.get("truth_inside_region")),
    }
    per_case = [{"case": r["case"], "label": r["label"], "n_bearings": r["n_bearings"],
                 "n_vertices": r.get("n_vertices"), "diameter_m": r.get("diameter_m"),
                 "circle_radius_m": r.get("circle_radius_m"),
                 "max_vertex_dist_m": r.get("max_vertex_dist_m"),
                 "ratio": r.get("ratio"), "excess_m": r.get("excess_m"),
                 "excess_pct": r.get("excess_pct"),
                 "coverage": r.get("diameter_circle_covers"),
                 "min_circle_over_half_diameter": r.get("min_circle_over_half_diameter"),
                 "worst_vertex_angle_deg": r.get("worst_vertex_angle_deg"),
                 "center_error_vs_truth_m": r.get("center_error_vs_truth_m"),
                 "truth_inside_region": r.get("truth_inside_region")} for r in results]
    meta = {"seed": seed, "n_cases": len(results),
            "arena_radius_m": R_ARENA,
            "bearing_error_bound_deg": P.BEARING_ERR,
            "r_recv_range_m": [R_RECV_MIN, R_RECV_MAX],
            "case_files": [os.path.basename(c) for c, _ in case_paths],
            "sweeps": {"two_point": {k: sweep1[k] for k in ("n_trials", "seed", "r_max_m")},
                       "well_conditioned": {k: sweep2[k] for k in
                                            ("n_trials", "seed", "min_gap_deg",
                                             "dist_range_m", "m_choices")}}}
    return {"meta": meta, "cases_summary": cases_summary, "per_case": per_case,
            "sweeps": {"two_point": sweep1, "well_conditioned": sweep2}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="问题一：算例生成 + 逐例求解 + 两组随机扫描")
    ap.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)),
                    help="算例与结果的输出目录（默认为本文件所在目录）")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED, help="算例生成种子")
    ap.add_argument("--cases", type=int, default=5, help="算例组数")
    ap.add_argument("--skip-sweep", action="store_true", help="跳过两组随机扫描")
    args = ap.parse_args(argv)

    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    case_paths = gen_cases(out, args.seed, args.cases)
    results = run_cases(case_paths)

    jl = os.path.join(out, "p1_results.jsonl")
    with open(jl, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    sweep1 = {"n_trials": 0, "seed": SWEEP_TWO_POINT["seed"], "n_bounded": 0,
              "n_fail": 0, "fail_pct": None, "worst_ratio": None, "worst_config": None}
    sweep2 = {"n_trials": 0, "seed": SWEEP_WELL_COND["seed"], "n_bounded": 0,
              "n_fail": 0, "fail_pct": None, "worst_ratio": None,
              "worst_config": None, "per_m": {}}
    if not args.skip_sweep:
        sweep1 = sweep_two_point()
        sweep2 = sweep_well_conditioned()

    summary = build_summary(case_paths, results, sweep1, sweep2, args.seed)
    with open(os.path.join(out, "p1_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("== 逐例结果（%s） ==" % out)
    for r in results:
        print("%-4s %-16s %-10s D=%-9s D/2=%-9s max|P-M|=%-9s ratio=%-9s cover=%-5s r*/D*2=%-8s" % (
            r["label"], r["case"], r["status"], r.get("diameter_m", "-"),
            r.get("circle_radius_m", "-"), r.get("max_vertex_dist_m", "-"),
            r.get("ratio", "-"), r.get("diameter_circle_covers", "-"),
            r.get("min_circle_over_half_diameter", "-")))
    if not args.skip_sweep:
        print("\n== 随机扫描 ==")
        print("两测点      : trials=%d bounded=%d fail=%d (%.4f%%) worst_ratio=%.6f" % (
            sweep1["n_trials"], sweep1["n_bounded"], sweep1["n_fail"],
            sweep1["fail_pct"], sweep1["worst_ratio"]))
        print("3~6 测点良态: trials=%d bounded=%d fail=%d (%.4f%%) worst_ratio=%.6f" % (
            sweep2["n_trials"], sweep2["n_bounded"], sweep2["n_fail"],
            sweep2["fail_pct"], sweep2["worst_ratio"]))
    print("\n== 论文表 2 行 ==")
    for r in results:
        lab = r"A\textsubscript{%s}" % r["label"].lstrip("AC")
        print("        %s & %d & %d & %.2f & %.2f & %.2f & %.4f & %s \\\\" % (
            lab, r["n_bearings"], r["n_vertices"], r["diameter_m"],
            r["circle_radius_m"], r["max_vertex_dist_m"], r["ratio"],
            "是" if r["diameter_circle_covers"] else "否"))
    print("\n写出: %s, %s, p1_case*.csv, p1_case*.truth.json"
          % (os.path.join(out, "p1_summary.json"), jl))
    return 0


if __name__ == "__main__":
    sys.exit(main())
