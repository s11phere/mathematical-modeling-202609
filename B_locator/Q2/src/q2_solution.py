# =====================================================================
# 问题二：第二个检测点的选择模型 —— 求解与汇总
#
# 模型（与 Q2modeling.md 一致）：
#   P1 置于原点、其示向度方向取为 x 轴正方向；P2 置于 (a, b)。
#   源点 S 位于 (x_S, 0)，后验分布 P_S(x_S|P1) = 2 x_S / x_max^2。
#   D(x_S, a, b) = 两探测束交会四边形 ABCD 的对角线长度最大值
#                = max_{A,B,C,D} 两两距离
#   其中 ABCD 由 P1 的两条边界射线（与 x 轴夹角 ±alpha）
#   与 P2 的两条边界射线（绕“P2 -> S”方向 ±alpha）两两相交得到。
#   价值函数 Dbar(a,b) = ∫ P_S(x_S|P1) D(x_S,a,b) dx_S（重心法数值积分）。
#
# 运行（仓库根目录）：
#   MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q2/src/q2_solution.py
# 产出：
#   B_locator/Q2/src/results/q2_summary.json
# =====================================================================
"""问题二求解：期望定位区域直径 Dbar(a,b) 的计算、最优化与汇总。"""

from __future__ import annotations

import json
import math
import os

import numpy as np

# ---------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------
X_MAX = 1500.0                # 有效接收半径上限，单位 m
ALPHA_DEG = 1.0               # 示向度误差界（度）= 探测束半张角
ALPHA = math.radians(ALPHA_DEG)

# 数值积分：求期望时 x_S 的分点个数（论文正文用 800）
NX_EXPECT = 800
# 求最优点时用的较粗分点数（仅用于扫描与细化）
NX_SCAN = 200
NX_REFINE = 800


# ---------------------------------------------------------------------
# 1. 单点计算：交会四边形与它的直径
# ---------------------------------------------------------------------
def quad_vertices(x_s, a, b, alpha=ALPHA):
    """返回两探测束交会四边形的四个顶点（4x2 数组）。

    四个顶点 = P1 的两条边界射线 × P2 的两条边界射线 的两两交点。
    P2 的边界射线绕 "P2 -> S" 方向 (psi) 张开 ±alpha，
    psi = atan2(-b, x_S - a)（S 相对 P2 的方位角）。

    退化情形（两条射线平行）返回 None。
    """
    p2 = np.array([a, b])
    psi = math.atan2(-b, x_s - a)
    pts = []
    for t1 in (alpha, -alpha):
        u1 = np.array([math.cos(t1), math.sin(t1)])
        for t2 in (psi + alpha, psi - alpha):
            u2 = np.array([math.cos(t2), math.sin(t2)])
            den = u1[0] * u2[1] - u1[1] * u2[0]
            if abs(den) < 1e-14:
                return None
            # P1 + s u1 = P2 + t u2  =>  s = cross(P2, u2)/cross(u1, u2)
            s = (p2[0] * u2[1] - p2[1] * u2[0]) / den
            pts.append(s * u1)
    return np.array(pts)


def quad_diameter(x_s, a, b, alpha=ALPHA):
    """单次构型的探测域直径 D(x_S, a, b) = 四边形顶点两两距离的最大值。"""
    p = quad_vertices(x_s, a, b, alpha)
    if p is None:
        return math.inf
    d = p[:, None, :] - p[None, :, :]
    return float(np.sqrt((d ** 2).sum(-1)).max())


def _diam_batch(a, b, x_s, alpha=ALPHA):
    """向量化：一次给出同一 (a,b) 上所有 x_S 的 D 值（长度 n 的数组）。

    P1 的两条边界射线固定，P2 的两条边界射线随 x_S 变化，
    故四个交点可在 x_S 方向上一次算完；再对 4 个顶点取两两距离最大值。
    """
    x_s = np.asarray(x_s, dtype=float)
    n = x_s.size
    p2 = np.array([a, b])
    psi = np.arctan2(-b, x_s - a)
    verts = np.zeros((n, 4, 2))
    k = 0
    for t1 in (alpha, -alpha):
        u1 = np.array([math.cos(t1), math.sin(t1)])
        for dt in (alpha, -alpha):
            u2x, u2y = np.cos(psi + dt), np.sin(psi + dt)
            den = u1[0] * u2y - u1[1] * u2x
            if np.any(np.abs(den) < 1e-14):         # 探测束近共线：直径无界
                return np.full(n, math.inf)
            s = (p2[0] * u2y - p2[1] * u2x) / den
            verts[:, k, 0] = s * u1[0]
            verts[:, k, 1] = s * u1[1]
            k += 1
    diff = verts[:, :, None, :] - verts[:, None, :, :]
    return np.sqrt((diff ** 2).sum(-1)).reshape(n, 16).max(axis=1)


# ---------------------------------------------------------------------
# 2. 价值函数 Dbar(a, b)
# ---------------------------------------------------------------------
def _nodes(n):
    """x_S 的重心法分点与权重 w = P_S(x_S|P1) = 2 x_S / x_max^2。"""
    x_s = X_MAX * (np.arange(n) + 0.5) / n
    w = 2.0 * x_s / X_MAX ** 2
    return x_s, w


def dbar(a, b, n=NX_EXPECT, alpha=ALPHA):
    """期望定位区域直径 Dbar(a, b)。

    b == 0（两探测点与源点共线）时区域无界，返回 inf。
    """
    if abs(b) < 1e-9:
        return math.inf
    x_s, w = _nodes(n)
    d = _diam_batch(a, b, x_s, alpha)
    if not np.isfinite(d).all():
        return math.inf
    return float((w * d).sum() / w.sum())


# ---------------------------------------------------------------------
# 3. 最优点与候选区域
# ---------------------------------------------------------------------
def optimize(n_grid=NX_SCAN, r_max=X_MAX, a_range=(-400.0, 1800.0),
             b_range=(60.0, 1500.0)):
    """在 |P2| <= r_max 内求 Dbar 的最小值（先粗扫再逐步细化）。"""
    best = (math.inf, 0.0, 0.0)
    step = 60.0
    for a in np.arange(a_range[0], a_range[1] + 1e-9, step):
        for b in np.arange(b_range[0], b_range[1] + 1e-9, step):
            if math.hypot(a, b) > r_max:
                continue
            v = dbar(float(a), float(b), n_grid)
            if v < best[0]:
                best = (v, float(a), float(b))
    for _ in range(7):                      # 逐步细化（步长每次减半）
        step /= 2.0
        for a in np.arange(best[1] - step, best[1] + step + 1e-9, step / 2.0):
            for b in np.arange(best[2] - step, best[2] + step + 1e-9, step / 2.0):
                if b <= 0 or math.hypot(a, b) > r_max:
                    continue
                v = dbar(float(a), float(b), NX_REFINE)
                if v < best[0]:
                    best = (v, float(a), float(b))
    return best


def level_region(d_min, tol, n_grid=100, r_max=X_MAX, step=20.0):
    """Dbar <= (1+tol) Dbar_min 的等值区域在 (R, beta) 上的范围。"""
    pts = []
    for a in np.arange(0.0, r_max + 1e-9, step):
        for b in np.arange(step, r_max + 1e-9, step):
            r = math.hypot(a, b)
            if r > r_max:
                continue
            v = dbar(float(a), float(b), n_grid)
            if v <= d_min * (1.0 + tol):
                pts.append((a, b))
    aa = np.array([p[0] for p in pts])
    bb = np.array([p[1] for p in pts])
    rr = np.hypot(aa, bb)
    ang = np.degrees(np.arctan2(bb, aa))
    return {
        "tol": tol,
        "n_points": len(pts),
        "a_range": [round(float(aa.min()), 1), round(float(aa.max()), 1)],
        "b_range": [round(float(bb.min()), 1), round(float(bb.max()), 1)],
        "R_range": [round(float(rr.min()), 1), round(float(rr.max()), 1)],
        "beta_range_deg": [round(float(ang.min()), 1), round(float(ang.max()), 1)],
    }


def membership_fraction(R1, R2, t1, t2, d_min, tol,
                        n_grid=100, r_max=X_MAX, step=10.0):
    """环扇区 R∈[R1,R2]、beta∈[t1,t2] 内满足 Dbar<=(1+tol)Dbar_min 的面积占比。"""
    inside = accept = 0
    for a in np.arange(0.0, r_max + 1e-9, step):
        for b in np.arange(step, r_max + 1e-9, step):
            r = math.hypot(a, b)
            if not (R1 <= r <= R2):
                continue
            ang = math.degrees(math.atan2(b, a))
            if not (t1 <= ang <= t2):
                continue
            inside += 1
            if dbar(float(a), float(b), n_grid) <= d_min * (1.0 + tol):
                accept += 1
    return accept / max(inside, 1)


# ---------------------------------------------------------------------
# 4. 文档闭式近似（小量近似，用于对照）
# ---------------------------------------------------------------------
def _cap_F(t, a, b):
    """∫ (t^2 + 2at + a^2) sqrt(t^2 + b^2) dt 的原函数。"""
    r = math.hypot(t, b)
    return ((t ** 3) / 4.0 + a * t * t / 3.0 + (2 * a * a + b * b) * t / 8.0
            + a * b * b / 3.0) * r + b * b * (4.0 * a * a - b * b) / 8.0 * math.log(t + r)


def dbar_closed(a, b):
    """文档中的闭式解（小量近似）。"""
    if abs(b) < 1e-9:
        return math.inf
    return (math.pi / (45.0 * X_MAX ** 2 * abs(b))
            * (_cap_F(X_MAX - a, a, b) - _cap_F(-a, a, b)))


def dbar_simple(a, b, n=NX_EXPECT):
    """进一步把 kappa 近似为 |b| 后的值：E[pi x_S r2S /(90 |b|)]。"""
    x_s, w = _nodes(n)
    r2 = np.hypot(x_s - a, b)
    phi = math.pi * x_s * r2 / (90.0 * abs(b))
    return float((w * phi).sum() / w.sum())


# =====================================================================
if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "results")
    os.makedirs(out_dir, exist_ok=True)

    print("[1/4] 求最优点 …")
    d_min, a_star, b_star = optimize()
    r_star = math.hypot(a_star, b_star)
    beta_star = math.degrees(math.atan2(b_star, a_star))
    print("      Dbar_min = %.4f m  at (a,b) = (%.2f, %.2f) m, R = %.1f m, beta = %.2f deg"
          % (d_min, a_star, b_star, r_star, beta_star))

    print("[2/4] 核心表格 …")
    table = [
        ("P2 与 P1 重合", 0.0, 0.0),
        ("沿视线 500 m", 500.0 * math.cos(ALPHA), 500.0 * math.sin(ALPHA)),
        ("沿视线 1000 m", 1000.0 * math.cos(ALPHA), 1000.0 * math.sin(ALPHA)),
        ("最优位置", a_star, b_star),
        ("(1000, 600)", 1000.0, 600.0),
        ("(1000, 700)", 1000.0, 700.0),
        ("(1100, 600)", 1100.0, 600.0),
        ("(1200, 700)", 1200.0, 700.0),
        ("垂距 700 m（正对 P1）", 0.0, 700.0),
        ("(500, 700)", 500.0, 700.0),
    ]
    rows = []
    for name, a, b in table:
        v = dbar(a, b, NX_EXPECT)
        rows.append({"name": name, "a": round(a, 1), "b": round(b, 1),
                     "dbar": None if not math.isfinite(v) else round(v, 3),
                     "ratio": None if not math.isfinite(v) else round(v / d_min, 3)})
        print("      %-20s a=%7.1f b=%6.1f  Dbar=%s"
              % (name, a, b, "无界" if not math.isfinite(v) else "%.3f" % v))

    print("[3/4] 等值区域与占比 …")
    levels = [level_region(d_min, t) for t in (0.05, 0.10, 0.20)]
    for lv in levels:
        print("      tol=%.0f%%: R in %s, beta in %s deg"
              % (lv["tol"] * 100, lv["R_range"], lv["beta_range_deg"]))
    fracs = {}
    for R1, R2, t1, t2 in [(1000.0, 1500.0, 15.0, 50.0),
                           (900.0, 1500.0, 10.0, 60.0)]:
        for tol in (0.05, 0.20):
            key = "R[%g,%g]_beta[%g,%g]_tol%.0f" % (R1, R2, t1, t2, tol * 100)
            fracs[key] = round(membership_fraction(R1, R2, t1, t2, d_min, tol), 4)
            print("      占比 %s = %.3f" % (key, fracs[key]))

    print("[4/4] 近似对照与自检 …")
    approx = {}
    for a, b in [(a_star, b_star), (1000.0, 700.0), (1100.0, 600.0)]:
        exact = dbar(a, b, NX_EXPECT)
        approx["(%.1f,%.1f)" % (a, b)] = {
            "dbar": round(exact, 3),
            "dbar_simple": round(dbar_simple(a, b), 3),
            "dbar_closed": round(dbar_closed(a, b), 3),
            "closed_rel_err": round(dbar_closed(a, b) / exact - 1.0, 4),
        }
        print("      (%.1f,%.1f): 严格=%.3f  简单近似=%.3f  闭式=%.3f (相对偏差 %+.1f%%)"
              % (a, b, exact, dbar_simple(a, b), dbar_closed(a, b),
                 100 * (dbar_closed(a, b) / exact - 1.0)))

    conv = [round(dbar(a_star, b_star, n), 4) for n in (100, 200, 400, 800)]
    sym = [round(dbar(1100.0, 700.0, 400), 4), round(dbar(1100.0, -700.0, 400), 4)]
    print("      收敛性(nx=100/200/400/800):", conv)
    print("      对称性 Dbar(a,b) 与 Dbar(a,-b):", sym)

    summary = {
        "params": {"x_max": X_MAX, "alpha_deg": ALPHA_DEG, "nx_expect": NX_EXPECT},
        "optimum": {"dbar_min": round(d_min, 4), "a": round(a_star, 3),
                    "b": round(b_star, 3), "R": round(r_star, 2),
                    "beta_deg": round(beta_star, 3),
                    "a_hat": round(a_star / X_MAX, 4), "b_hat": round(b_star / X_MAX, 4)},
        "table": rows,
        "level_regions": levels,
        "membership_fractions": fracs,
        "approximation": approx,
        "checks": {"convergence": conv, "mirror_symmetry": sym},
    }
    path = os.path.join(out_dir, "q2_summary.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print("[OK] 汇总已写入 %s" % path)
