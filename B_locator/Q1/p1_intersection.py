# -*- coding: utf-8 -*-
"""B 题问题一：示向度交会定位区域、区域直径与直径圆覆盖判定（纯求解库）。

约定：坐标单位 m，x 轴正东、y 轴正北；示向度 theta 为自 x 轴正向逆时针的方位角
（度，[0,360)）；示向度误差有界，|e| <= BEARING_ERR = 1 度。

定位区域 R = 各角楔 W_i 的交集，W_i 是以检测点 S_i 为顶点、张角 2*BEARING_ERR 的角楔
（两个半平面之交），故 R 是顶点数不超过 2m 的凸多边形；直径由顶点集上的最远点对给出，
覆盖判定比较 max|P-M| 与 D/2（M 为直径中点）。

入口：算例生成、逐例求解与两组随机扫描见 p1_experiments.py；自检见 p1_selftest.py。
"""
from __future__ import annotations
import csv
import json
import math
import os

import numpy as np

BEARING_ERR = 1.0        # 示向度误差界（度）
ANG_TOL = 1e-9           # 角度判据容差（度）
DIST_TOL = 1e-6          # 半平面判据容差（米）
CLIP = 1e7               # 裁剪参考实现的外框半边长（米）
DIAM_BRUTE_LIMIT = 128   # 顶点数不超过该值时直径用暴力枚举


# --------------------------------------------------------------------------
# 基本几何
# --------------------------------------------------------------------------
def bearing(p, q):
    """p 处指向 q 的方位角（度，[0,360)）"""
    return math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 360.0


def ang_diff(a, b):
    """a-b 归一化到 (-180,180]"""
    return (a - b + 180.0) % 360.0 - 180.0


def wedge_halfplanes(p, theta, err=BEARING_ERR):
    """角楔 W = {X : |ang(X-p) - theta| <= err} 的两个半平面 a·X + b <= 0"""
    p = np.asarray(p, float)
    tm = math.radians((theta - err) % 360.0)
    tp = math.radians((theta + err) % 360.0)
    dm = np.array([math.cos(tm), math.sin(tm)])
    dp = np.array([math.cos(tp), math.sin(tp)])
    # cross(dm, X-p) >= 0   <=>   a1·X + b1 <= 0
    a1 = np.array([dm[1], -dm[0]])
    b1 = float(-dm[1] * p[0] + dm[0] * p[1])
    # cross(dp, X-p) <= 0   <=>   a2·X + b2 <= 0
    a2 = np.array([-dp[1], dp[0]])
    b2 = float(dp[1] * p[0] - dp[0] * p[1])
    return [(a1, b1), (a2, b2)]


def region_is_unbounded(svds, err=BEARING_ERR):
    """区域无界时返回一个逃逸方向（度），有界时返回 None；仅在区域非空时有意义。"""
    for th in svds:
        for cand in ((th - err) % 360.0, (th + err) % 360.0):
            if all(abs(ang_diff(cand, t)) <= err + ANG_TOL for t in svds):
                return cand
    return None


def _line_intersection(P, u, Q, v):
    """直线 P + t·u 与 Q + s·v 的交点，平行时返回 None"""
    det = u[0] * (-v[1]) - (-v[0]) * u[1]
    if abs(det) < 1e-14:
        return None
    r = Q - P
    t = (r[0] * (-v[1]) - (-v[0]) * r[1]) / det
    return P + t * u


def convex_hull(P):
    """Andrew monotone chain，逆时针，去掉共线点"""
    def half(pts):
        st = []
        for p in pts:
            while len(st) >= 2 and _cross2(st[-1] - st[-2], p - st[-2]) <= 0:
                st.pop()
            st.append(p)
        return st
    P = P[np.lexsort((P[:, 1], P[:, 0]))]
    lo = half(P)
    hi = half(P[::-1])
    return np.array(lo[:-1] + hi[:-1])


def _cross2(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


def _dedup_hull(cand):
    """候选顶点去重 + 凸包，返回 (P, "empty"|"degenerate"|"polygon")"""
    if len(cand) == 0:
        return np.zeros((0, 2)), "empty"
    P = np.array(cand, float)
    P = P[np.lexsort((P[:, 1], P[:, 0]))]
    ded = [P[0]]
    for v in P[1:]:
        if np.linalg.norm(v - ded[-1]) > 1e-7:
            ded.append(v)
    P = np.array(ded)
    if len(P) < 3:
        return P, "degenerate"
    H = convex_hull(P)
    if len(H) < 3:
        return H, "degenerate"
    return H, "polygon"


# --------------------------------------------------------------------------
# 区域算法 1：顶点枚举 + 凸包（主算法，精确）
# --------------------------------------------------------------------------
def region_by_vertices(pts, svds, err=BEARING_ERR, tol=DIST_TOL):
    """主算法：枚举 2m 条边界直线的两两交点，用全部半平面判据筛选后求凸包。

    R 是凸集，其任一极点必是两条起作用约束边界直线的交点，故枚举 + 筛选是精确的；
    半平面判据在处理"边界直线过检测点"的情形时仍良定义，检测点本身也可作顶点保留。
    """
    if len(pts) == 0:
        return np.zeros((0, 2)), "empty"
    H, lines = [], []
    for p, th in zip(pts, svds):
        H += wedge_halfplanes(p, th, err)
        for s in (-1.0, 1.0):
            a = math.radians((th + s * err) % 360.0)
            lines.append((np.asarray(p, float), np.array([math.cos(a), math.sin(a)])))
    cand = []
    n = len(lines)
    for i in range(n):
        for j in range(i + 1, n):
            X = _line_intersection(lines[i][0], lines[i][1], lines[j][0], lines[j][1])
            if X is None or not np.all(np.isfinite(X)):
                continue
            if all(float(a @ X + b) <= tol for (a, b) in H):
                cand.append(X)
    return _dedup_hull(cand)


# --------------------------------------------------------------------------
# 区域算法 2：半平面裁剪（独立参考实现，可直接判无界）
# --------------------------------------------------------------------------
def clip_halfplane(poly, a, b, tol=DIST_TOL):
    """Sutherland–Hodgman：保留 {X : a·X + b <= 0} 的部分"""
    if not poly:
        return []
    out = []
    n = len(poly)
    for i in range(n):
        P = poly[i]
        Q = poly[(i + 1) % n]
        fp = float(a @ P + b)
        fq = float(a @ Q + b)
        if fp <= tol:
            out.append(P)
        if (fp < -tol and fq > tol) or (fp > tol and fq < -tol):
            t = fp / (fp - fq)
            out.append(P + t * (Q - P))
    ded = []
    for v in out:
        if not ded or np.linalg.norm(v - ded[-1]) > 1e-9:
            ded.append(v)
    if len(ded) > 1 and np.linalg.norm(ded[0] - ded[-1]) < 1e-9:
        ded.pop()
    return ded


def region_by_clipping(pts, svds, err=BEARING_ERR, box=CLIP, tol=DIST_TOL):
    """参考实现：从大框出发逐个半平面裁剪；多边形触到外框即判区域无界。"""
    poly = [np.array([-box, -box], float), np.array([box, -box], float),
            np.array([box, box], float), np.array([-box, box], float)]
    for p, th in zip(pts, svds):
        for (a, b) in wedge_halfplanes(p, th, err):
            poly = clip_halfplane(poly, a, b, tol)
            if not poly:
                return np.zeros((0, 2)), "empty"
    P = np.array(poly, float)
    if len(P) < 3:
        return P, "degenerate"
    if float(np.max(np.abs(P))) > box * 0.5:
        return P, "unbounded"
    H = convex_hull(P)
    return (H if len(H) >= 3 else P), "polygon"


def region_from_bearings(pts, svds, err=BEARING_ERR):
    """主入口：返回 (顶点数组, status)，status 取 empty / unbounded / degenerate / bounded。"""
    P, st = region_by_vertices(pts, svds, err)
    if st == "empty":
        return P, "empty"
    rec = region_is_unbounded(list(svds), err) if len(svds) else None
    if rec is not None:
        return P, "unbounded"
    if st == "degenerate":
        return P, "degenerate"
    return P, "bounded"


# --------------------------------------------------------------------------
# 直径与最小包围圆
# --------------------------------------------------------------------------
def _diameter_brute(P):
    n = len(P)
    best, pair = -1.0, (P[0], P[1])
    for i in range(n - 1):
        d = np.linalg.norm(P[i + 1:] - P[i], axis=1)
        k = int(np.argmax(d))
        if float(d[k]) > best:
            best, pair = float(d[k]), (P[i], P[i + 1 + k])
    return best, pair


def rotating_calipers(P):
    """凸多边形直径（旋转卡壳，O(n)）。P 需为逆时针凸序（允许共线点）。"""
    n = len(P)
    if n < 3:
        return diameter(P, brute_limit=2)
    k = 1
    best, pair = -1.0, (P[0], P[1])
    for i in range(n):
        i2 = (i + 1) % n
        e = P[i2] - P[i]
        while True:
            k2 = (k + 1) % n
            if abs(_cross2(e, P[k2] - P[i])) > abs(_cross2(e, P[k] - P[i])):
                k = k2
            else:
                break
        for j in (k, (k + 1) % n):
            d = float(np.linalg.norm(P[i] - P[j]))
            if d > best:
                best, pair = d, (P[i], P[j])
            d = float(np.linalg.norm(P[i2] - P[j]))
            if d > best:
                best, pair = d, (P[i2], P[j])
    return best, pair


def diameter(P, brute_limit=DIAM_BRUTE_LIMIT):
    """凸多边形直径，返回 (D, (A, B))"""
    n = len(P)
    if n == 0:
        return 0.0, None
    if n == 1:
        return 0.0, (P[0], P[0])
    if n == 2:
        return float(np.linalg.norm(P[0] - P[1])), (P[0], P[1])
    if n <= brute_limit:
        return _diameter_brute(P)
    return rotating_calipers(P)


def min_enclosing_circle(P):
    """最小包围圆 (center, radius)；顶点数很少，直接枚举 1/2/3 点候选圆。"""
    P = np.asarray(P, float)
    n = len(P)
    if n == 0:
        return None, 0.0
    if n == 1:
        return P[0].copy(), 0.0
    cands = [(P[i].copy(), 0.0) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = 0.5 * (P[i] + P[j])
            cands.append((c, float(np.linalg.norm(P[i] - c))))
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                A, B, C = P[i], P[j], P[k]
                d = 2.0 * (A[0] * (B[1] - C[1]) + B[0] * (C[1] - A[1])
                           + C[0] * (A[1] - B[1]))
                if abs(d) < 1e-12:
                    continue
                aa, bb, cc = float(A @ A), float(B @ B), float(C @ C)
                ux = (aa * (B[1] - C[1]) + bb * (C[1] - A[1]) + cc * (A[1] - B[1])) / d
                uy = (aa * (C[0] - B[0]) + bb * (A[0] - C[0]) + cc * (B[0] - A[0])) / d
                c = np.array([ux, uy])
                cands.append((c, float(np.linalg.norm(A - c))))
    best = None
    for c, r in cands:
        if all(float(np.linalg.norm(P[i] - c)) <= r + 1e-9 for i in range(n)):
            if best is None or r < best[1]:
                best = (c, r)
    return best


def region_area(P):
    n = len(P)
    if n < 3:
        return 0.0
    return abs(0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1)
                                   - np.roll(P[:, 0], -1) * P[:, 1])))


# --------------------------------------------------------------------------
# 汇总
# --------------------------------------------------------------------------
def analyse(pts, svds, err=BEARING_ERR):
    """给定检测点与示向度，输出定位区域的全套几何量（长度量按 4 位小数落盘）。"""
    P, status = region_from_bearings(pts, svds, err)
    base = {"n_bearings": len(pts), "status": status}
    if status == "empty":
        base["reason"] = ("所有示向度锥无公共交集（数据不一致：两两夹角可以 > 2°，"
                          "但错开的两个楔也可能不相交）")
        return base
    if status == "unbounded":
        rec = region_is_unbounded(list(svds), err)
        base["reason"] = ("示向度锥近似平行（两两夹角 <= 2°），定位区域无界，"
                          "直径 = +inf；必须换检测点重测")
        base["recession_direction_deg"] = None if rec is None else round(float(rec), 4)
        base["n_vertices"] = int(len(P))
        base["vertices"] = [[round(float(v[0]), 4), round(float(v[1]), 4)] for v in P]
        return base
    if status == "degenerate" or len(P) < 3:
        base["status"] = "degenerate"
        base["reason"] = "公共交集退化为线段或点"
        base["vertices"] = [[round(float(v[0]), 4), round(float(v[1]), 4)] for v in P]
        return base

    D, (A, B) = diameter(P)
    c = 0.5 * (A + B)
    maxr = float(max(np.linalg.norm(v - c) for v in P))
    mc, mr = min_enclosing_circle(P)
    base.update({
        "n_vertices": int(len(P)),
        "vertices": [[round(float(v[0]), 4), round(float(v[1]), 4)] for v in P],
        "diameter_m": round(D, 4),
        "diameter_endpoints": [[round(float(A[0]), 4), round(float(A[1]), 4)],
                               [round(float(B[0]), 4), round(float(B[1]), 4)]],
        "circle_center": [round(float(c[0]), 4), round(float(c[1]), 4)],
        "circle_radius_m": round(D / 2.0, 4),
        "max_vertex_dist_m": round(maxr, 4),
        "diameter_circle_covers": bool(maxr <= D / 2.0 + 1e-9),
        "min_enclosing_center": [round(float(mc[0]), 4), round(float(mc[1]), 4)],
        "min_enclosing_radius_m": round(float(mr), 4),
        "min_circle_over_half_diameter": round(float(mr) / (D / 2.0), 6),
        "area_m2": round(region_area(P), 4),
    })
    return base


def run_case_csv(path, truth_path=None, err=BEARING_ERR):
    """读单个算例 CSV（列含 x_m,y_m,svd_deg）与可选真值 JSON，返回 analyse 结果。"""
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    pts = [(float(r["x_m"]), float(r["y_m"])) for r in rows]
    svds = [float(r["svd_deg"]) for r in rows]
    res = analyse(pts, svds, err)
    res["n_bearings"] = len(rows)
    if truth_path and os.path.exists(truth_path):
        with open(truth_path, encoding="utf-8") as f:
            truth = json.load(f)
        G = truth["source_xy"]
        res["truth_xy"] = G
        if "circle_center" in res:
            res["center_error_vs_truth_m"] = round(math.dist(res["circle_center"], G), 3)
        if "min_enclosing_center" in res:
            res["mincircle_error_vs_truth_m"] = round(
                math.dist(res["min_enclosing_center"], G), 3)
        # 真值是否满足全部约束（等价于在半平面内）
        H = []
        for p, th in zip(pts, svds):
            H += wedge_halfplanes(p, th, err)
        res["truth_inside_region"] = bool(all(a @ np.asarray(G, float) + b <= 1e-6
                                             for (a, b) in H))
    return res
