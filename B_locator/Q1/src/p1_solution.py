# -*- coding: utf-8 -*-
"""B 题问题一：交会定位区域、区域直径与直径圆覆盖判定。

本文件是论文 5.1 节的唯一计算依据，自包含、无第三方依赖（仅标准库 math/json）。

约定（与赛题附录 2 一致）
    - 坐标单位 m，x 轴正东、y 轴正北；
    - 示向度 theta 为自 x 轴正向逆时针旋转的方位角，单位度，范围 [0,360)；
    - 示向度误差界 eps = 1 度，同一检测点重复测量误差不变。

算法（正文 Algorithm 1）
    (1) 有界性判据：有向方位角区间 Theta_i = [theta_i-eps, theta_i+eps] 求交，
        交集非空 => 区域无界，该构型不可用于定位，停止；
    (2) 定位区域 = 全部角楔（半平面）之交，用半平面裁剪得到凸多边形；
    (3) 凸包（去共线内点）-> 直径 = 顶点集最远点对；
    (4) 覆盖判定：max_{P in V} |P-M| <= D/2，M 为直径中点。

运行：python p1_solution.py
输出：results/p1_summary.json，并在标准输出打印论文用三线表（LaTeX）。
"""
from __future__ import annotations

import json
import math
import os
import random

EPS_DEG = 1.0          # 示向度误差界，赛题给定
CLIP_BOX = 1.0e7       # 半平面裁剪初始包围盒（远大于任何可用的定位区域）

# ---------------------------------------------------------------------------
# 算例：取自已归档的 Q1/simulation/data/p1_case*.csv 与同名 .truth.json
# ---------------------------------------------------------------------------
CASES = {
    "A1": {
        "det": [(-432.855, -596.368, 91.86), (-290.614, -501.995, 121.82),
                (474.860, -160.806, 186.02), (461.755, 349.174, 212.80),
                (-444.749, -62.142, 269.79), (-958.142, 736.087, 298.12)],
        "truth": (-443.576, -252.667),
    },
    "A2": {
        "det": [(72.672, -1476.606, 73.96), (783.454, -636.506, 134.50),
                (746.674, -5.204, 217.55), (844.851, 787.911, 247.24),
                (34.166, 319.047, 304.05)],
        "truth": (420.750, -259.359),
    },
    "A3": {
        "det": [(709.118, -729.536, 179.57), (317.773, 449.572, 250.16),
                (-154.476, -336.439, 275.19), (-1410.795, -695.591, 359.41)],
        "truth": (-116.815, -716.576),
    },
    "A4": {
        "det": [(-108.557, -1370.888, 90.33), (41.556, -464.500, 166.16),
                (736.343, -249.188, 191.23), (53.780, 122.283, 253.02),
                (-713.233, -470.065, 4.50)],
        "truth": (-113.869, -427.931),
    },
    "A5": {
        "det": [(-1060.628, 138.331, 22.33), (-708.449, 92.735, 64.29),
                (-492.444, 15.307, 105.98), (-416.508, 177.626, 137.07),
                (-133.401, 454.320, 194.10), (-162.779, 801.637, 227.45)],
        "truth": (-588.010, 338.494),
    },
}

# 构造性反例：以下两组构型均给出"直径圆无法覆盖定位区域"的实例，
# 供论文 5.1.4 节直接引用（坐标单位 m，示向度单位度）。
COUNTER_EXAMPLES = {
    # 两个检测点：检测点均在目标区域内，定位区域是斜四边形
    "CE2": [(467.910, -177.778, 159.1962), (176.844, 467.174, 249.2663)],
    # 三个检测点在半径 1500 m 圆周上均匀分布（方位 0/120/240 度）
    "CE3": [(1500.0 * math.cos(math.radians(t)), 1500.0 * math.sin(math.radians(t)),
             (t + 180.0) % 360.0) for t in (0.0, 120.0, 240.0)],
}


# ---------------------------------------------------------------------------
# 基础向量 / 角度工具
# ---------------------------------------------------------------------------
def _rot(vec, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (vec[0] * c - vec[1] * s, vec[0] * s + vec[1] * c)


def ang_diff(a, b):
    """把 a-b 归一化到 (-180, 180]。"""
    return (a - b + 180.0) % 360.0 - 180.0


def bearing(p, q):
    """由 p 指向 q 的方位角（度）。"""
    return math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 360.0


def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


# ---------------------------------------------------------------------------
# 有界性判据：有向方位角区间求交（纯角度，O(m)，与坐标无关）
# ---------------------------------------------------------------------------
def _interval_parts(lo, hi):
    """把圆周区间 [lo,hi]（度，宽度 < 360）拆成至多两段普通区间。"""
    lo %= 360.0
    hi %= 360.0
    if lo <= hi:
        return [(lo, hi)]
    return [(lo, 360.0), (0.0, hi)]


def angle_interval_common(svds, eps=EPS_DEG):
    """返回全部 Theta_i = [theta_i-eps, theta_i+eps] 的公共交集（段列表）。"""
    segs = _interval_parts(svds[0] - eps, svds[0] + eps)
    for th in svds[1:]:
        cur = _interval_parts(th - eps, th + eps)
        new = []
        for a, b in segs:
            for c, d in cur:
                lo, hi = max(a, c), min(b, d)
                if lo <= hi + 1e-12:
                    new.append((lo, min(hi, 360.0)))
        segs = new
        if not segs:
            return []
    return segs


def boundedness(svds, eps=EPS_DEG):
    """bounded 当且仅当方位角区间公共交集为空。"""
    return "unbounded" if angle_interval_common(svds, eps) else "bounded"


# ---------------------------------------------------------------------------
# 定位区域：全部角楔（半平面）之交
# ---------------------------------------------------------------------------
def _clip(poly, n, b):
    """保留 {x : n . x + b >= 0}，Sutherland-Hodgman 裁剪。"""
    out = []
    k = len(poly)
    for i in range(k):
        p, q = poly[i], poly[(i + 1) % k]
        fp = n[0] * p[0] + n[1] * p[1] + b
        fq = n[0] * q[0] + n[1] * q[1] + b
        if fp >= 0.0:
            out.append(p)
        if (fp < 0.0 < fq) or (fp > 0.0 > fq):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    ded = []
    for v in out:
        if not ded or _dist(v, ded[-1]) > 1e-9:
            ded.append(v)
    if len(ded) > 1 and _dist(ded[0], ded[-1]) < 1e-9:
        ded.pop()
    return ded


def wedge_halfplanes(pi, thi, eps=EPS_DEG):
    """角楔 W_i 的两条边界半平面 (n, b)，满足 n.x + b >= 0 落在楔内。"""
    out = []
    for s in (-1.0, 1.0):
        a = math.radians(thi + s * eps)
        r = (math.cos(a), math.sin(a))     # 边界射线方向
        n = _rot(r, -90.0 * s)             # 指向楔内的法向量
        out.append((n, -(n[0] * pi[0] + n[1] * pi[1])))
    return out


def region_by_halfplane(dets, eps=EPS_DEG, box=CLIP_BOX):
    """主实现：半平面裁剪构造定位区域，返回顶点列表（无顶点则返回 []）。"""
    poly = [(-box, -box), (box, -box), (box, box), (-box, box)]
    for (x, y, th) in dets:
        for n, b in wedge_halfplanes((x, y), th, eps):
            poly = _clip(poly, n, b)
            if not poly:
                return []
    return poly


def region_by_intersection(dets, eps=EPS_DEG, tol=1e-7):
    """独立等价实现：枚举 2m 条边界线交点 + 角差可行性筛选。

    仅用于交叉校验主实现，不参与主流程。
    """
    lines = []
    for (x, y, th) in dets:
        for s in (-1.0, 1.0):
            a = math.radians((th + s * eps) % 360.0)
            lines.append(((x, y), (math.cos(a), math.sin(a))))
    cand = []
    for i in range(len(lines)):
        pi, di = lines[i]
        for j in range(i + 1, len(lines)):
            pj, dj = lines[j]
            det = di[0] * (-dj[1]) - (-dj[0]) * di[1]
            if abs(det) < 1e-14:                     # 近于平行，交点在无穷远
                continue
            rx, ry = pj[0] - pi[0], pj[1] - pi[1]
            t = (rx * (-dj[1]) - (-dj[0]) * ry) / det
            X = (pi[0] + t * di[0], pi[1] + t * di[1])
            if not (math.isfinite(X[0]) and math.isfinite(X[1])):
                continue
            ok = True
            for (x, y, th) in dets:                  # 该点必须落在全部角楔内
                if _dist((x, y), X) < 1e-9:
                    ok = False
                    break
                if abs(ang_diff(bearing((x, y), X), th)) > eps + tol:
                    ok = False
                    break
            if ok:
                cand.append(X)
    return cand


# ---------------------------------------------------------------------------
# 凸包 / 直径 / 最小包围圆
# ---------------------------------------------------------------------------
def convex_hull(pts):
    """Andrew 单调链，逆时针，弹出共线中间点。"""
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts

    def half(seq):
        st = []
        for p in seq:
            while len(st) >= 2 and _cross(st[-2], st[-1], p) <= 0:
                st.pop()
            st.append(p)
        return st

    lo = half(pts)
    hi = half(pts[::-1])
    return lo[:-1] + hi[:-1]


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def farthest_pair(pts):
    """最远点对（全枚举）。凸多边形直径由两个顶点达到，故 O(n^2) 已足够。"""
    best, pair = -1.0, (pts[0], pts[0])
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = _dist(pts[i], pts[j])
            if d > best:
                best, pair = d, (pts[i], pts[j])
    return best, pair


def diameter_calipers(pts):
    """反踵点旋转卡壳（仅作交叉校验）。要求 pts 逆时针且严格凸。"""
    n = len(pts)
    if n < 3:
        return farthest_pair(pts)
    best = 0.0
    j = 1
    for i in range(n):
        ni = (i + 1) % n
        while True:
            nj = (j + 1) % n
            if abs(_cross(pts[i], pts[ni], pts[nj])) > abs(_cross(pts[i], pts[ni], pts[j])):
                j = nj
            else:
                break
        best = max(best, _dist(pts[i], pts[j]), _dist(pts[ni], pts[j]))
    return best, None


def smallest_enclosing_circle(pts):
    """最小包围圆半径与圆心（2 点 / 3 点支配集枚举），用于检验 R_min 与 D/2 的关系。"""
    best = None
    n = len(pts)
    for i in range(n):
        for j in range(i + 1, n):
            c = ((pts[i][0] + pts[j][0]) / 2.0, (pts[i][1] + pts[j][1]) / 2.0)
            r = _dist(c, pts[i])
            if all(_dist(c, p) <= r + 1e-9 for p in pts):
                if best is None or r < best[0]:
                    best = (r, c)
    if best is not None and best[0] <= 1e-12:
        return best
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                (ax, ay), (bx, by), (cx, cy) = pts[i], pts[j], pts[k]
                d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
                if abs(d) < 1e-14:
                    continue
                ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay)
                      + (cx * cx + cy * cy) * (ay - by)) / d
                uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx)
                      + (cx * cx + cy * cy) * (bx - ax)) / d
                r = _dist((ux, uy), pts[i])
                if all(_dist((ux, uy), p) <= r + 1e-9 for p in pts):
                    if best is None or r < best[0]:
                        best = (r, (ux, uy))
    if best is None:
        # 全部共线：端点支配
        lo = min(pts)
        hi = max(pts)
        c = ((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0)
        best = (_dist(c, lo), c)
    return best


# ---------------------------------------------------------------------------
# 单算例主流程
# ---------------------------------------------------------------------------
def analyse_case(dets, eps=EPS_DEG, truth=None):
    """返回一个算例的全部特征量；无界 / 退化在此统一标注。"""
    svds = [th for (_, _, th) in dets]
    res = {
        "n_bearings": len(dets),
        "boundedness": boundedness(svds, eps),
        "status": None,
    }
    if res["boundedness"] == "unbounded":
        res["status"] = "unbounded"
        return res
    poly = region_by_halfplane(dets, eps)
    if len(poly) < 3:
        res["status"] = "degenerate" if poly else "empty"
        res["vertices"] = [[round(x, 6), round(y, 6)] for (x, y) in poly]
        return res

    hull = convex_hull(poly)
    if len(hull) < 3:                       # 交集退化为线段
        res["status"] = "degenerate"
        res["vertices"] = [[round(x, 6), round(y, 6)] for (x, y) in hull]
        if len(hull) == 2:
            res["diameter_m"] = _dist(hull[0], hull[1])
        return res

    D, (A, B) = farthest_pair(hull)
    M = ((A[0] + B[0]) / 2.0, (A[1] + B[1]) / 2.0)
    r = D / 2.0
    maxvtx = max(_dist(M, p) for p in hull)
    rmin, cmin = smallest_enclosing_circle(hull)
    # 坐标量级决定的绝对容差：用于区分"真超界"与浮点噪声（超界量 >= 1e-3 m 才是真失效）
    scale = max(1.0, max(max(abs(x), abs(y)) for (x, y, _) in dets))

    res.update({
        "status": "bounded",
        "vertices": [[round(x, 6), round(y, 6)] for (x, y) in hull],
        "diameter_m": D,
        "diameter_endpoints": [[round(A[0], 6), round(A[1], 6)],
                               [round(B[0], 6), round(B[1], 6)]],
        "circle_center": [round(M[0], 6), round(M[1], 6)],
        "circle_radius_m": r,
        "max_vertex_dist_m": maxvtx,
        "excess_m": maxvtx - r,
        "ratio": maxvtx / r,
        "coverage_tol_m": 1e-9 * scale,
        "coverage": bool(maxvtx <= r + 1e-9 * scale),
        "rmin_m": rmin,
        "rmin_over_halfD": rmin / r,
        "area_m2": abs(sum(hull[i][0] * hull[(i + 1) % len(hull)][1]
                           - hull[(i + 1) % len(hull)][0] * hull[i][1]
                           for i in range(len(hull)))) / 2.0,
    })
    if truth is not None:
        res["center_error_m"] = _dist(M, truth)
        res["truth_inside"] = all(
            abs(ang_diff(bearing((x, y), truth), th)) <= eps + 1e-6 for (x, y, th) in dets)
    # 交叉校验：独立实现必须给出同一顶点集（排序后逐点比较）
    alt = region_by_intersection(dets, eps)
    if alt:
        h_alt = convex_hull(alt)
        res["cross_check_vertices_match"] = (
            len(h_alt) == len(hull)
            and all(min(_dist(a, b) for b in hull) < 1e-6 for a in h_alt))
    Dc, _ = diameter_calipers(hull)
    res["cross_check_calipers_match"] = abs(Dc - D) < 1e-9 * max(1.0, D)
    return res


# ---------------------------------------------------------------------------
# 随机稳健性扫描（论文中"覆盖率"统计的来源）
# ---------------------------------------------------------------------------
def random_suite(n_trials=4000, seed=5, eps=EPS_DEG):
    """良态构型随机扫描：检测点方位间隔 > 3 deg，距离 300~1500 m。"""
    rng = random.Random(seed)
    n_bounded = 0
    ratios = []
    per_m = {3: [0, 0], 4: [0, 0], 5: [0, 0], 6: [0, 0]}      # m -> [有界数, 失败数]
    n_vertices_of_failures = {}
    for _ in range(n_trials):
        m = rng.choice([3, 4, 5, 6])
        angs = sorted(rng.uniform(0.0, 360.0) for _ in range(m))
        gaps = [min((angs[i] - angs[j]) % 360.0, (angs[j] - angs[i]) % 360.0)
                for i in range(m) for j in range(i + 1, m)]
        if min(gaps) <= 3.0:
            continue
        dets = []
        for t in angs:
            rr = rng.uniform(300.0, 1500.0)
            dets.append((rr * math.cos(math.radians(t)),
                         rr * math.sin(math.radians(t)),
                         (t + 180.0) % 360.0))
        res = analyse_case(dets, eps)
        if res["status"] != "bounded":
            continue
        n_bounded += 1
        per_m[m][0] += 1
        if not res["coverage"]:
            per_m[m][1] += 1
            ratios.append(res["ratio"])
            k = len(res["vertices"])
            n_vertices_of_failures[k] = n_vertices_of_failures.get(k, 0) + 1
    return {
        "seed": seed,
        "n_trials": n_trials,
        "n_bounded": n_bounded,
        "n_fail": len(ratios),
        "fail_pct": 100.0 * len(ratios) / max(n_bounded, 1),
        "worst_ratio": max(ratios) if ratios else None,
        "mean_ratio_over_failures": (sum(ratios) / len(ratios)) if ratios else None,
        "per_m": {str(m): {"bounded": v[0], "fail": v[1],
                           "fail_pct": 100.0 * v[1] / max(v[0], 1)}
                  for m, v in per_m.items()},
        "vertex_counts_of_failures": {str(k): v
                                      for k, v in sorted(n_vertices_of_failures.items())},
    }


def two_point_sweep(n_trials=20000, seed=17, eps=EPS_DEG, r_max=1800.0):
    """两测点随机扫描：方位差 > 2 eps 才可能有界；统计覆盖率与最坏比值。

    检测点采样保证落在半径 r_max 的目标区域内（方位角取 90 度~270 度一半平面）。
    """
    rng = random.Random(seed)
    n_bounded = 0
    ratios = []
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
        res = analyse_case([(A[0], A[1], th1), (B[0], B[1], th2)], eps)
        if res["status"] != "bounded":
            continue
        n_bounded += 1
        if not res["coverage"]:
            ratios.append(res["ratio"])
        if worst is None or res["ratio"] > worst[0]:
            worst = (res["ratio"], (A[0], A[1], th1), (B[0], B[1], th2), res)
    return {
        "seed": seed, "n_trials": n_trials, "n_bounded": n_bounded,
        "n_fail": len(ratios),
        "fail_pct": 100.0 * len(ratios) / max(n_bounded, 1),
        "worst_ratio": worst[0] if worst else None,
        "worst_config": {
            "S1": [round(worst[1][0], 3), round(worst[1][1], 3), round(worst[1][2], 4)],
            "S2": [round(worst[2][0], 3), round(worst[2][1], 3), round(worst[2][2], 4)],
            "D": round(worst[3]["diameter_m"], 4),
            "max_vertex_dist": round(worst[3]["max_vertex_dist_m"], 4),
            "ratio": round(worst[3]["ratio"], 6),
            "rmin_over_halfD": round(worst[3]["rmin_over_halfD"], 6),
        } if worst else None,
    }


def three_point_equilateral(radius=1500.0, eps=EPS_DEG):
    """构造性反例：三个检测点在半径 radius 的圆周上均匀分布（方位 0/120/240 度）。"""
    return [tuple(d) for d in COUNTER_EXAMPLES["CE3"]]


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def _fmt(x, nd=4):
    return ("{:." + str(nd) + "f}").format(x)


def latex_main_table(results):
    """论文表行：5 个算例 + 两组构造性反例。"""
    rows = []
    names = {"A1": r"A\textsubscript{1}", "A2": r"A\textsubscript{2}",
             "A3": r"A\textsubscript{3}", "A4": r"A\textsubscript{4}",
             "A5": r"A\textsubscript{5}", "CE2": r"C\textsubscript{2}",
             "CE3": r"C\textsubscript{3}"}
    for key in ("A1", "A2", "A3", "A4", "A5", "CE2", "CE3"):
        r = results[key]
        rows.append(
            "%s & %d & %d & %s & %s & %s & %s & %s \\\\" % (
                names[key], r["n_bearings"], len(r["vertices"]),
                _fmt(r["diameter_m"], 2), _fmt(r["circle_radius_m"], 2),
                _fmt(r["max_vertex_dist_m"], 2), _fmt(r["ratio"], 4),
                "是" if r["coverage"] else "否"))
    return "\n".join(rows)


def latex_counterexample_table(results):
    """构造性反例的两个检测点坐标与示向度（论文表行）。"""
    rows = []
    for key in ("CE2", "CE3"):
        for i, (x, y, th) in enumerate(COUNTER_EXAMPLES[key], start=1):
            rows.append("%s & $S_{%d}$ & %s & %s & %s \\\\" % (
                r"C\textsubscript{2}" if key == "CE2" else r"C\textsubscript{3}",
                i, _fmt(x, 2), _fmt(y, 2), _fmt(th, 2)))
    return "\n".join(rows)


def latex_robustness_table(stats, stats2):
    """随机扫描统计（论文表行）。"""
    rows = [
        r"两检测点构型 & 20000 & %d & %s & %s \\" % (
            stats2["n_bounded"], _fmt(stats2["fail_pct"], 2),
            _fmt(stats2["worst_ratio"], 4)),
        r"三至六检测点（合计） & 4000 & %d & %s & %s \\" % (
            stats["n_bounded"], _fmt(stats["fail_pct"], 2),
            _fmt(stats["worst_ratio"], 4)),
    ]
    for m in ("3", "4", "5", "6"):
        v = stats["per_m"][m]
        rows.append(r"其中 $m=%s$ & --- & %d & %s & --- \\" % (
            m, v["bounded"], _fmt(v["fail_pct"], 2)))
    return "\n".join(rows)


def main():
    results = {}
    for key, case in CASES.items():
        results[key] = analyse_case(case["det"], EPS_DEG, case["truth"])
    for key, dets in COUNTER_EXAMPLES.items():
        results[key] = analyse_case(dets, EPS_DEG)
    stats = random_suite()
    stats2 = two_point_sweep()

    print("== 单算例结果 ==")
    for key in ("A1", "A2", "A3", "A4", "A5", "CE2", "CE3"):
        r = results[key]
        if r["status"] != "bounded":
            print("%-4s %s" % (key, r["status"]))
            continue
        print("%-4s m=%d n=%2d D=%8.3f  D/2=%8.3f  max|V-M|=%8.3f  ratio=%.4f  "
              "cover=%-5s Rmin/(D/2)=%.5f  ctr_err=%s"
              % (key, r["n_bearings"], len(r["vertices"]), r["diameter_m"],
                 r["circle_radius_m"], r["max_vertex_dist_m"], r["ratio"],
                 r["coverage"], r["rmin_over_halfD"],
                 _fmt(r.get("center_error_m", float("nan")), 2)))
    print()
    print("== 随机稳健性（m = 3~6 良态构型） ==")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print()
    print("== 两测点随机扫描 ==")
    print(json.dumps(stats2, ensure_ascii=False, indent=2))
    print()
    print("== 论文表行（主结果） ==")
    print(latex_main_table(results))
    print()
    print("== 论文表行（构造性反例的输入） ==")
    print(latex_counterexample_table(results))
    print()
    print("== 论文表行（随机扫描统计） ==")
    print(latex_robustness_table(stats, stats2))

    here = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.join(here, "results")
    os.makedirs(outdir, exist_ok=True)
    payload = {"cases": results, "random_suite": stats,
               "two_point_sweep": stats2, "eps_deg": EPS_DEG}
    with open(os.path.join(outdir, "p1_summary.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("\n写出: %s" % os.path.join(outdir, "p1_summary.json"))


if __name__ == "__main__":
    main()
