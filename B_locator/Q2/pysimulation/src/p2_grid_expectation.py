"""B 题问题 2（模拟）：固定首次探测扇形后，第二检测点网格上的"交会区域直径期望"热力图。

问题设定（按需求方给定的简化模型）
----------------------------------
1. **固定当前探测得到的扇形区域**：探测器（机器狗）位于原点 ``S1 = (0, 0)``，
   探测方向为 x 轴正方向，示向度误差界 ``eps = 1 deg``。于是第一次探测给出的信息是角楔

       W1 = { X : |ang(X - S1) - theta1| <= eps }

   ``theta1`` 取自当前探测数据（默认 0 deg，即"探测方向为 x 轴正方向"）。
2. **干扰源均匀分布在扇形内，近似认为都在 x 轴上**：即源位 ``G = (t, 0)``，
   ``t`` 在 ``[near, t_hi]`` 上取值，权重由"扇形内面积均匀"退化得到：面积元
   ``dA = r dr dtheta -> w(t) ∝ t``（令 ``--weight area``）；另提供等权（``length``）
   作为对照。
3. **网格**：把每个网格点当作第二个检测点 ``S2``。
4. **交会区域与直径**：给定源位 ``G``，两个检测点各得一条带 ±eps 的示向度锥，
   两者之交是凸四边形 ``R = W1 ∩ W2``，其**直径** D = 区域内任意两点距离的最大值。
5. **期望**：``E[D](S2) = Σ_i w_i D(S2, t_i)``，只在 R 非空且有界的样本上取平均，
   同时记录"可行样本占比"（coverage），避免把不可用点伪装成好点。
6. **热力图**：``E[D](S2)`` 作为网格点 ``(x, y)`` 的函数。

两套口径（主 / 辅）
-------------------
* ``measured``（主）：两个楔都用**测得值** ± 1°，即 ``R = W1(theta1) ∩ W2(theta2)``，
  期望只对源位 ``t`` 取 —— 完全对应"固定当前探测数据"的字面含义。
* ``error_avg``（辅）：同一个区域，但期望**同时对 ±1° 测量误差取**，
  即 ``E_{t, e1, e2}[ D ]`` —— 更贴近"定位效果"的真实统计含义。

为什么网格必须是真正二维的（重要结论）
--------------------------------------
若把 ``S2`` 放在 x 轴上（``y = 0``），则两条示向度近似平行，二者的夹角
``|dtheta| <= 2*eps``，交会区域**无界**、直径为 +∞（这正是
``p1_intersection.region_from_bearings`` 报 ``unbounded`` 的退化几何，
等价于"沿示向度方向逼近"）。所以 ``y = 0`` 必须在网格上被剔除/掩码，
程序会显式统计并报告这一点。

理论校验（写入 ``report.json`` 的 ``checks``）
--------------------------------------------
记 ``d1 = |S1 G| = t``，``d2 = |S2 G| = r``，``gamma`` 为两条**真**示向度之差的绝对值
（= 源处交会角），则标称（无误差）区域直径有闭式

    D_closed = 2 tan(eps) * sqrt(t^2 + r^2 - 2 t r cos(phi)) / sin(gamma)

其中 ``phi`` 为 S1->S2 的方位角。数值算法与该闭式的相对误差应 < 1e-9
（两者都在原点与 S2 的连线上对称，见 ``review/verify_p2_grid.py``）。

用法
----
    python src/p2_grid_expectation.py --selfcheck
    python src/p2_grid_expectation.py --out out/p2_grid
    python src/p2_grid_expectation.py --theta1 30 --step 20 --out out/p2_grid_t30
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
import warnings

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from p1_intersection import (  # noqa: E402
    BEARING_ERR, ang_diff, bearing, convex_hull, diameter as poly_diameter,
    region_by_vertices,
)

# --------------------------------------------------------------------------
# 物理常数（题目附录 1/2）
# --------------------------------------------------------------------------
EPS_DEG = BEARING_ERR          # 示向度误差界 1°
R_ARENA = 1800.0               # 目标区域半径（m）
R_RECV_MIN = 1000.0            # 有效接收半径下界（m，接口不返回，用于保守约束）
R_RECV_MAX = 1500.0            # 有效接收半径上界（m，取信号的必要条件）
NEAR_R = 5.0                   # 近场阈值（m）：更近则没有示向度
TOL = 1e-9

# 默认计算参数
DEF_STEP = 30.0                # 网格步长（m）
DEF_N_T = 300                  # x 轴上源位采样数
DEF_N_E = 200                  # 误差 MC 次数（error_avg 口径）
DEF_MAX_PAIRS = 20000          # error_avg 的 (e1,e2) 计划表上限，控制内存
DEF_MASK_RADIUS = 60.0         # |y| 小于该值视为"贴 x 轴"的退化区，掩码


# --------------------------------------------------------------------------
# 基本几何
# --------------------------------------------------------------------------
def wedge_halfplanes(p, theta, err=EPS_DEG):
    """角楔 W = {X : |ang(X-p) - theta| <= err} 的两个半平面 a·X + b <= 0"""
    p = np.asarray(p, float)
    tm = math.radians((theta - err) % 360.0)
    tp = math.radians((theta + err) % 360.0)
    dm = np.array([math.cos(tm), math.sin(tm)])
    dp = np.array([math.cos(tp), math.sin(tp)])
    a1 = np.array([dm[1], -dm[0]])
    b1 = float(-dm[1] * p[0] + dm[0] * p[1])
    a2 = np.array([-dp[1], dp[0]])
    b2 = float(dp[1] * p[0] - dp[0] * p[1])
    return [(a1, b1), (a2, b2)]


def point_in_wedge(X, p, theta, err=EPS_DEG, tol=1e-9):
    """X 是否在角楔内（与 p 重合视为在楔内）"""
    X = np.asarray(X, float)
    p = np.asarray(p, float)
    if float(np.linalg.norm(X - p)) < tol:
        return True
    return abs(ang_diff(bearing(p, X), theta)) <= err + 1e-12


def intersection_vertices(S1, theta1, S2, theta2, err=EPS_DEG):
    """两个角楔交的顶点（通用实现，用于自检；快路径见 fast_diameters）"""
    P, st = region_by_vertices([S1, S2], [theta1, theta2], err)
    if st == "empty":
        return np.zeros((0, 2)), "empty"
    if _unbounded_bearings(theta1, theta2, err):
        return P, "unbounded"
    if st == "degenerate" or len(P) < 3:
        return P, "degenerate"
    return P, "polygon"


def _unbounded_bearings(theta1, theta2, err=EPS_DEG):
    """两楔交无界 <=> 存在方向与两条示向度夹角都 <= err

    对两个示向度，等价条件为 min(|th2-th1|, 180-|th2-th1|) <= 2*err。
    """
    d = abs(ang_diff(theta2, theta1))
    return min(d, 180.0 - d) <= 2.0 * err + 1e-12


def _corner_points(Pw, thP, Qw, thQ, eps, nP, nQ):
    """两个角楔交的 6 个候选角点，**全部在世界坐标下求解**。

    角楔 ``|ang(X - P) - θ| <= eps`` 的两条边界线方向为 ``θ ∓ eps``，顶点为 ``P``；
    ``P`` 同时在两条边界线上，故两条线的常数项都等于 ``n·P``，``n = (sin a, -cos a)``。

    四线两两相交得 6 个候选点；**顶点判定直接用楔的定义**（而非半平面不等式）：
    候选点 X 是区域顶点 ⟺ 对每个楔（顶点 P、示向度 θ）都有
    ``|ang(X-P) - θ| <= eps`` 或 ``|X-P| < tol``（X 恰是该楔的顶点）。
    这个判据与坐标系的定向、2×2 解法的行列式符号都无关，因此最稳健。

    返回 ``(corner_world, valid)``，形状 ``(..., 6, 2)`` 与 ``(..., 6)``，**世界坐标**。
    """
    Pw = np.asarray(Pw, float)
    Qw = np.asarray(Qw, float)
    thP = np.asarray(thP, float)
    thQ = np.asarray(thQ, float)

    def two_lines(P, th):
        out = []
        for s in (-eps, eps):
            a = np.radians(th + s)
            n = np.stack([np.sin(a), -np.cos(a)], axis=-1)
            out.append((n, np.einsum("...i,...i->...", n, P)))
        return out

    lines = two_lines(Pw, thP) + two_lines(Qw, thQ)

    def in_wedge(X, P, th):
        d = X - P
        dist = np.hypot(d[..., 0], d[..., 1])
        ang = np.degrees(np.arctan2(d[..., 1], d[..., 0]))
        diff = (ang - th + 180.0) % 360.0 - 180.0
        return (np.abs(diff) <= eps + 1e-9) | (dist <= 1e-9)

    corners = []
    valid = []
    for ii in range(4):
        for jj in range(ii + 1, 4):
            (n1, c1), (n2, c2) = lines[ii], lines[jj]
            det = n1[..., 0] * n2[..., 1] - n1[..., 1] * n2[..., 0]
            safe = np.where(np.abs(det) < 1e-15, 1e-15, det)
            X = np.stack([(c1 * n2[..., 1] - c2 * n1[..., 1]) / safe,
                          (n1[..., 0] * c2 - n2[..., 0] * c1) / safe], axis=-1)
            ok = in_wedge(X, Pw, thP) & in_wedge(X, Qw, thQ)
            corners.append(X)
            valid.append(ok)
    return np.stack(corners, axis=-2), np.stack(valid, axis=-1)


def world_to_local(Xw, Qw, phi):
    """世界坐标 -> 局部 (j,k) 坐标。

    约定（与 ``fast_diameters_vec`` / ``_fast_pair_grid`` 的 (j,k) 系一致）：
    ``j = -dx·sinφ + dy·cosφ``、``k = -dx·cosφ - dy·sinφ``，``dx = X_x - Q_x`` 等。
    """
    Qw = np.asarray(Qw, float)
    dx = Xw[..., 0] - Qw[..., 0]
    dy = Xw[..., 1] - Qw[..., 1]
    return np.stack([-dx * np.sin(phi) + dy * np.cos(phi),
                     -dx * np.cos(phi) - dy * np.sin(phi)], axis=-1)


def local_to_world(j, k, phi, Qw):
    """局部 (j,k) -> 世界坐标（``world_to_local`` 的逆映射，两者互为严格逆）。

    手算：``X = Q + j·(sinφ, -cosφ) + k·(cosφ, sinφ)``。
    """
    Qw = np.asarray(Qw, float)
    return np.stack([Qw[..., 0] + j * np.sin(phi) + k * np.cos(phi),
                     Qw[..., 1] - j * np.cos(phi) + k * np.sin(phi)], axis=-1)


def fast_diameters(S2, ts, eps=EPS_DEG):
    """给定第二检测点 S2 与 x 轴上一组源位 ts，返回 (D, status)。

    ``D`` 为交会区域直径（np.nan 表示该源位下区域为空/退化/无界）。
    ``status`` 编码：0 = 有界多边形，1 = 空，2 = 退化，3 = 无界。
    S1 固定为原点、源固定在 x 轴正半轴（本题设定）。

    做法见 ``fast_diameters_vec``。
    """
    D, st = fast_diameters_vec(np.asarray(S2, float)[None, :],
                               np.asarray(ts, float).ravel(), eps)
    return D[0], st[0]


def closed_form_diameter(t, S2, eps=EPS_DEG):
    """交会区域直径的**独立参考实现**（世界坐标、直接解边界交点，不复用快路径）。

    每个角楔 ``|ang(X - P) - θ| <= eps`` 的两条边界线可写成
    ``方向 a = θ ∓ eps`` 的射线；两条边界线的交点为候选顶点，
    再用**楔的定义**（角度判据）筛出真正落在两个楔内的顶点，最后取两两距离最大值。

    这给出与 ``p1_intersection.region_by_vertices``（半平面枚举）和
    ``fast_diameters_vec``（(j,k) 系闭式角点）都**不同**的第三条路径，
    自检 T2 用它以 1e-9 相对精度交叉核对主算法。

    无界（``min(|Δθ|, 180-|Δθ|) <= 2 eps``）返回 ``inf``。
    """
    S2 = np.asarray(S2, float)
    t = float(t)
    eps = float(eps)
    th1 = 0.0                                                   # S1 -> G
    th2 = math.degrees(math.atan2(-S2[1], t - S2[0])) % 360.0   # S2 -> G
    if _unbounded_bearings(th1, th2, eps):
        return math.inf

    lines = []
    for apex, th in (((0.0, 0.0), th1), (tuple(S2), th2)):
        for s in (-eps, eps):
            a = math.radians(th + s)
            lines.append((apex, (math.cos(a), math.sin(a))))

    def in_wedge(X, apex, th):
        dx, dy = X[0] - apex[0], X[1] - apex[1]
        if math.hypot(dx, dy) < 1e-9:
            return True
        ad = math.degrees(math.atan2(dy, dx))
        return abs((ad - th + 180.0) % 360.0 - 180.0) <= eps + 1e-9

    verts = []
    for i in range(4):
        for j2 in range(i + 1, 4):
            (P1, u), (P2, v) = lines[i], lines[j2]
            det = u[0] * (-v[1]) - (-v[0]) * u[1]
            if abs(det) < 1e-14:
                continue
            rv = (P2[0] - P1[0], P2[1] - P1[1])
            s = (rv[0] * (-v[1]) - (-v[0]) * rv[1]) / det
            X = (P1[0] + s * u[0], P1[1] + s * u[1])
            if in_wedge(X, (0.0, 0.0), th1) and in_wedge(X, tuple(S2), th2):
                verts.append(X)
    if len(verts) < 2:
        return math.inf
    return max(math.dist(a, b) for i, a in enumerate(verts) for b in verts[i + 1:])


# --------------------------------------------------------------------------
# 源位采样与权重
# --------------------------------------------------------------------------
def sector_ray_exit(S1, a_deg, R=R_ARENA):
    """从 S1 沿方位角 a 到半径 R 圆域边界的距离"""
    S1 = np.asarray(S1, float)
    u = np.array([math.cos(math.radians(a_deg)), math.sin(math.radians(a_deg))])
    b = float(S1 @ u)
    c = float(S1 @ S1) - R * R
    disc = b * b - c
    return 0.0 if disc <= 0 else float(-b + math.sqrt(disc))


def source_samples(S1, theta1, err=EPS_DEG, n_t=DEF_N_T, r_arena=R_ARENA,
                  r_recv_max=R_RECV_MAX, near=NEAR_R):
    """x 轴上的源位采样（面积均匀权重）。

    来源：干扰源在扇形内面积均匀 -> ``dA = r dr dtheta``，
    对角向积分后 ``w(r) ∝ r``。故 ``w_i ∝ t_i``（归一化后即为离散先验）。
    ``t_hi = min(r_recv_max, 沿 theta1 到靶区边界的距离)``，因为能测得示向度
    意味着 ``|S1 G| <= 有效接收半径 <= r_recv_max``，且源在靶区内。
    """
    S1 = np.asarray(S1, float)
    t_hi = min(r_recv_max, sector_ray_exit(S1, theta1, r_arena))
    t_lo = near
    if t_hi <= t_lo:
        return np.zeros(0), np.zeros(0), {"t_lo": t_lo, "t_hi": t_hi}
    ts = np.linspace(t_lo, t_hi, int(n_t))
    w_area = ts.copy()                       # 面积均匀：w ∝ t
    w_area = w_area / float(w_area.sum())
    info = {"t_lo": float(t_lo), "t_hi": float(t_hi), "n_t": int(n_t),
            "weight": "area", "t_peak_note": "w(t) ∝ t（面积均匀退化的严格结果）"}
    return ts, w_area, info


def length_weights(ts):
    w = np.ones_like(np.asarray(ts, float))
    return w / float(w.sum())


# --------------------------------------------------------------------------
# 网格与期望
# --------------------------------------------------------------------------
def make_grid(step=DEF_STEP, x_range=(-R_ARENA, R_ARENA), y_range=(-R_ARENA, R_ARENA),
              x_offset=0.0, y_offset=0.0, arena_r=R_ARENA, domain="arena"):
    """生成网格点（仅保留靶区圆域内、且不贴 x 轴的退化带的点）。

    ``domain='reach'`` 时进一步要求该点到 x 轴上任何可能源位（|t| <= 1500）的距离 <= 1500 m
    —— "站在那里还能收到该频道信号"的**必要条件**（有效接收半径上界 1500 m）。
    """
    xs = np.arange(x_range[0] + x_offset, x_range[1] + 1e-9, step)
    ys = np.arange(y_range[0] + y_offset, y_range[1] + 1e-9, step)
    DX, DY = np.meshgrid(xs, ys)             # shape (ny, nx)
    X = DX.ravel()
    Y = DY.ravel()
    keep = (X * X + Y * Y <= arena_r * arena_r) & (np.abs(Y) > 1e-9)
    if domain == "reach":
        d = np.sqrt(np.minimum(X ** 2, (np.abs(X) - R_RECV_MAX) ** 2) + Y ** 2)
        keep &= (d <= R_RECV_MAX)
    return X[keep], Y[keep], xs, ys, DX.shape


def reach_ok(X, Y, ts, r_recv_max=R_RECV_MAX):
    """可检测性（有效接收半径上界）门控矩阵：``|S2 - G_i| <= r_recv_max``。

    源在 x 轴上，故 ``|S2 - (t,0)| = sqrt((x-t)^2 + y^2)``，对固定 (x,y) 关于 t
    的最小值在 ``t = clip(x, t_lo, t_hi)`` 处取到。
    """
    X = np.asarray(X, float)[:, None]
    Y = np.asarray(Y, float)[:, None]
    ts = np.asarray(ts, float)[None, :]
    t_clip = np.clip(X, float(np.min(ts)), float(np.max(ts)))
    d2 = np.sqrt((X - t_clip) ** 2 + Y ** 2)
    return d2 <= r_recv_max + 1e-9


def expected_diameter_measured(X, Y, ts, w, eps=EPS_DEG, reach=True, chunk=4096):
    """主口径：区域用测得值 ±eps，期望只对源位取。

    返回：
      * ``E``      ：``E[D · 1{可检测}]``（"可检测"= |S2G| <= 有效接收半径上界 1500 m）；
      * ``E_det``  ：``E[D | 可检测]``（不可检测的样本被条件掉）；
      * ``cov``    ：可检测样本的先验权重占比（原始 cov，非归一化）；
      * ``p_det``  ：``P(可检测)`` = cov / Σw；
      * ``Dmin``/``Dmax``：可检测且有界样本上的极值；``n_ok``：可用样本数。
    """
    S2 = np.column_stack([X, Y])
    n = X.size
    E = np.zeros(n)
    E_det = np.full(n, np.nan)
    cov = np.zeros(n)
    p_det = np.zeros(n)
    Dmin = np.full(n, np.nan)
    Dmax = np.full(n, np.nan)
    n_ok = np.zeros(n, dtype=int)
    wsum = float(np.sum(w))
    for s in range(0, n, chunk):
        e = min(n, s + chunk)
        D, st = fast_diameters_vec(S2[s:e], ts, eps)
        m = np.isfinite(D)
        if reach:
            m &= reach_ok(S2[s:e, 0], S2[s:e, 1], ts)
        wc = np.where(m, w[None, :], 0.0)
        sw = wc.sum(axis=1)
        contrib = (np.where(m, D, 0.0) * w[None, :]).sum(axis=1)
        with np.errstate(invalid="ignore"):
            E[s:e] = contrib
            E_det[s:e] = np.where(sw > 0, contrib / np.maximum(sw, 1e-300), np.nan)
            Dmin[s:e] = np.where(m.any(axis=1),
                                 np.nanmin(np.where(m, D, np.inf), axis=1), np.nan)
            Dmax[s:e] = np.where(m.any(axis=1),
                                 np.nanmax(np.where(m, D, -np.inf), axis=1), np.nan)
        cov[s:e] = sw
        p_det[s:e] = sw / wsum
        n_ok[s:e] = m.sum(axis=1)
    return {"E": E, "E_det": E_det, "cov": cov, "p_det": p_det,
            "Dmin": Dmin, "Dmax": Dmax, "n_ok": n_ok}


def fast_diameters_vec(S2s, ts, eps=EPS_DEG):
    """``fast_diameters`` 的批量版：S2s (m,2) × ts (n,) -> D (m,n), status (m,n)"""
    S2s = np.asarray(S2s, float)
    ts = np.asarray(ts, float).ravel()
    m = S2s.shape[0]
    n = ts.size
    D = np.full((m, n), np.nan)
    status = np.ones((m, n), dtype=np.int8)
    if m == 0 or n == 0:
        return D, status
    r = np.hypot(S2s[:, 0], S2s[:, 1])
    ok_row = r >= 1e-9
    status[~ok_row, :] = 2
    th2 = np.degrees(np.arctan2(-S2s[:, 1][:, None], ts[None, :] - S2s[:, 0][:, None])) % 360.0
    dth = np.abs((th2 - 0.0 + 180.0) % 360.0 - 180.0)
    sep = np.minimum(dth, 180.0 - dth)
    unb = (sep <= 2.0 * eps + 1e-12) | (~ok_row[:, None])
    status[unb] = np.where(np.broadcast_to(ok_row[:, None], unb.shape), 3, 2)[unb]

    # 4 个候选角点：两个楔各 2 条边界线，两两相交（世界坐标下求解）
    th0g = np.zeros((m, n))                                  # S1 处真示向度 = 0
    S2b = np.repeat(S2s[:, None, :], n, axis=1)              # (m,n,2)
    S1g = np.zeros((m, n, 2))                                # S1 = 原点
    corner, valid = _corner_points(S1g, th0g, S2b, th2, eps, 0, 0)

    ok = ~unb
    if not np.any(ok):
        return D, status
    nP = corner.shape[-2]                      # 候选角点数（4 条边界线两两相交 = 6）
    cw = corner
    v = valid.reshape(m, n, nP)
    best = np.zeros((m, n))
    for ii in range(nP):
        for jj in range(ii + 1, nP):
            d2 = ((cw[..., ii, 0] - cw[..., jj, 0]) ** 2
                  + (cw[..., ii, 1] - cw[..., jj, 1]) ** 2)
            best = np.where(v[..., ii] & v[..., jj], np.maximum(best, d2), best)
    n_valid = v.sum(axis=-1)
    status = np.where(ok & (n_valid < 2), 1, status).astype(np.int8)
    finite = ok & (n_valid >= 2) & np.isfinite(best)
    D = np.where(finite, np.sqrt(np.maximum(best, 0.0)), np.nan)
    status = np.where(finite, 0, status).astype(np.int8)
    return D, status


def _fast_pair_grid(S1, th1, S2, th2, eps):
    """通用批量快路径：(...,) 形状的 S1/th1/S2/th2 -> 直径 D 与 status。

    与 ``fast_diameters_vec`` 同一套闭式，但两个角楔都任意
    （不要求 S1 在原点、源在 x 轴上）。用于 error_avg 口径。
    几何量建立在以 S2 为原点、k 轴指向 S1 的 (j,k) 坐标系中（保距）。
    """
    P1 = np.asarray(S1, float)
    P2 = np.asarray(S2, float)
    th1 = np.asarray(th1, float)
    th2 = np.asarray(th2, float)
    # 允许 th1 是 th2 的"去尾维"版本（例如 (blk,nP) 对 (blk,nP,nT)）
    if th2.ndim > th1.ndim:
        th1 = th1.reshape(th1.shape + (1,) * (th2.ndim - th1.ndim))
    shp = np.broadcast_shapes(th1.shape, th2.shape)
    th1 = np.broadcast_to(th1, shp)
    th2 = np.broadcast_to(th2, shp)
    P1 = np.asarray(P1, float)[..., None, :]          # 末维为坐标，向前插一维以便广播
    P2 = np.asarray(P2, float)[..., None, :]
    P1 = np.broadcast_to(P1, shp + (2,))
    P2 = np.broadcast_to(P2, shp + (2,))
    rho = np.linalg.norm(P1 - P2, axis=-1)
    th21 = np.degrees(np.arctan2((P1 - P2)[..., 1], (P1 - P2)[..., 0])) % 360.0
    sep = np.abs((th2 - th1 + 180.0) % 360.0 - 180.0)
    sep = np.minimum(sep, 180.0 - sep)

    D = np.full(shp, np.nan)
    status = np.ones(shp, dtype=np.int8)
    unb = (sep <= 2.0 * eps + 1e-12) | (rho < 1e-9)
    status[sep <= 2.0 * eps + 1e-12] = 3
    status[rho < 1e-9] = 2
    ok = ~unb
    if not np.any(ok):
        return D, status
    corner, valid = _corner_points(P1, th1, P2, th2, eps, 0, 0)   # 世界坐标
    nP = corner.shape[-2]
    cw = corner.reshape(shp + (nP, 2))
    v = valid.reshape(shp + (nP,))
    best = np.zeros(shp)
    for ii in range(nP):
        for jj in range(ii + 1, nP):
            d2 = ((cw[..., ii, 0] - cw[..., jj, 0]) ** 2
                  + (cw[..., ii, 1] - cw[..., jj, 1]) ** 2)
            best = np.where(v[..., ii] & v[..., jj], np.maximum(best, d2), best)
    n_valid = v.sum(axis=-1)
    status = np.where(ok & (n_valid < 2), 1, status).astype(np.int8)
    finite = ok & (n_valid >= 2) & np.isfinite(best)
    D = np.where(finite, np.sqrt(np.maximum(best, 0.0)), np.nan)
    status = np.where(finite, 0, status).astype(np.int8)
    return D, status


def expected_diameter_error_avg(X, Y, ts, w, eps=EPS_DEG, n_e=DEF_N_E,
                                max_pairs=DEF_MAX_PAIRS, chunk=1024, seed=20260913,
                                reach=True):
    """辅口径：区域仍取 W1(θ1) ∩ W2(θ2)，但期望**同时对源位 t 与 ±eps 测量误差**取。

    设为 ``E_err(X) = E_{e1,e2}[ Σ_i w_i D(X; t_i, e1, e2) · 1{可检测} ]``
    （对两个读数误差均匀分布取期望，t 按面积均匀先验加权）。

    实现用**分块蒙特卡洛**：对每一批网格点抽 ``n_e`` 组独立误差 ``(e1,e2)~U[-eps,eps]^2``
    并把第 k 组只作用到该批第 k 个点上 —— 于是每个网格点得到 ``n_e`` 个**独立无偏**估计，
    取均值即可。代价是 ``n_e × n_t × 网格点数``，而不是把误差当笛卡尔积
    （``n_e² × n_t``，之前的实现会在 1 万个网格点上吃掉十几 GB）。

    返回：
      * ``E_err``    ：``E[D · 1{可检测}]``；
      * ``E_err_det``：``E[D | 可检测]``（逐误差样本先按可检测样本条件化，再对误差平均）；
      * ``cov_err``  ：``E_{e1,e2}[ P(可检测) ]``；``n_pairs``：误差抽样数。
    """
    S2 = np.column_stack([X, Y])
    n = X.size
    if n == 0:
        return {"E_err": np.zeros(0), "E_err_det": np.zeros(0),
                "cov_err": np.zeros(0), "n_pairs": 0}
    rng = np.random.default_rng(seed)
    E_err = np.zeros(n)
    E_err_det = np.full(n, np.nan)
    cov_err = np.zeros(n)
    for s in range(0, n, chunk):
        e = min(n, s + chunk)
        blk = e - s
        if max_pairs and blk > max_pairs:          # 保险：单批不超过上限
            blk = max_pairs
            e = s + blk
        E1 = rng.uniform(-eps, eps, blk)                       # 每点一个独立的 e1
        E2 = rng.uniform(-eps, eps, blk)
        S2b = S2[s:e]                                          # (blk,2)
        S1b = np.zeros((blk, 2))
        base2 = np.degrees(np.arctan2(-S2b[:, 1][:, None],
                                      ts[None, :] - S2b[:, 0][:, None])) % 360.0
        th1 = E1[:, None]                                      # θ1 真值 0
        th2 = base2 + E2[:, None]                              # (blk,nT)
        D, st = _fast_pair_grid(S1b, th1, S2b, th2, eps)       # (blk,nT)
        m = np.isfinite(D)
        if reach:
            m &= reach_ok(S2b[:, 0], S2b[:, 1], ts)
        contrib = (np.where(m, D, 0.0) * w[None, :]).sum(axis=1)       # (blk,)
        wsum = np.where(m, w[None, :], 0.0).sum(axis=1)                # (blk,)
        with np.errstate(invalid="ignore"):
            E_err_det[s:e] = np.where(wsum > 0, contrib / np.maximum(wsum, 1e-300), np.nan)
        cov_err[s:e] = wsum
        E_err[s:e] = contrib
    return {"E_err": E_err, "E_err_det": E_err_det, "cov_err": cov_err,
            "n_pairs": int(n_e), "estimator": "per-point Monte-Carlo (unbiased)"}


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------
def selfcheck(verbose=True, seed=7):
    """三级校验：与 p1 参考实现一致 / 与闭式一致 / 与区域采样一致 + two-wedge 几何反例"""
    out = []
    ok_all = True

    def rec(name, ok, detail=""):
        nonlocal ok_all
        ok_all = ok_all and ok
        out.append({"check": name, "ok": bool(ok), "detail": detail})
        if verbose:
            print(f"[{'OK ' if ok else 'FAIL'}] {name}  {detail}")

    def unbounded(theta1, theta2):
        return _unbounded_bearings(theta1, theta2, EPS_DEG)

    def th2_of(S2, t):
        return float(np.degrees(np.arctan2(-S2[1], t - S2[0])) % 360.0)

    def mc_points(S2, t, n_pt, rng_):
        """在两楔各自锥内采样并保留落在交会区域内的点（向量化）"""
        th2 = th2_of(S2, t)
        L = rng_.uniform(5.0, 1900.0, n_pt)
        a1 = np.radians(rng_.uniform(-EPS_DEG, EPS_DEG, n_pt))
        P1 = np.stack([L * np.cos(a1), L * np.sin(a1)], axis=1)
        a2 = math.radians(th2) + np.radians(rng_.uniform(-EPS_DEG, EPS_DEG, n_pt))
        P2 = np.asarray(S2)[None, :] + np.stack([L * np.cos(a2), L * np.sin(a2)], axis=1)
        K = np.vstack([P1, P2])

        def inw(P, apex, th):
            d = P - np.asarray(apex)[None, :]
            dist = np.hypot(d[:, 0], d[:, 1])
            angd = np.degrees(np.arctan2(d[:, 1], d[:, 0]))
            return ((np.abs((angd - th + 180.0) % 360.0 - 180.0) <= EPS_DEG + 1e-9)
                    & (dist > 1e-9))

        return K[inw(K, (0.0, 0.0), 0.0) & inw(K, S2, th2)]

    def max_pair_dist(K, blk=512):
        dmax = 0.0
        for s0 in range(0, len(K), blk):
            dmax = max(dmax, float(np.max(
                np.linalg.norm(K[s0:s0 + blk, None, :] - K[None, :, :], axis=2))))
        return dmax

    rng = np.random.default_rng(seed)

    # ---- T0: 顶点个数=4 且每个顶点真在两个楔内（只测良态 + 可检测几何）----
    n0, bad0 = 0, 0
    for _ in range(2500):
        S2 = np.array([rng.uniform(-1500, 1500), rng.uniform(-1400, 1400)])
        if np.hypot(*S2) < 200.0:
            continue
        t = float(rng.uniform(200.0, 1450.0))
        if np.hypot(S2[0] - t, S2[1]) > R_RECV_MAX:      # 必须可检测
            continue
        th2 = th2_of(S2, t)
        sep = min(abs(ang_diff(th2, 0.0)), 180.0 - abs(ang_diff(th2, 0.0)))
        if sep <= 10.0:                                  # 远离退化
            continue
        D, st = fast_diameters(S2, np.array([t]))
        if not np.isfinite(D[0]):
            continue
        n0 += 1
        c, v = _corner_points(np.zeros((1, 1, 2)), np.zeros((1, 1)),
                              S2.reshape(1, 1, 2), np.array([[th2]]), EPS_DEG, 0, 0)
        c, v = c[0, 0], v[0, 0]
        if int(v.sum()) != 4:
            bad0 += 1
            continue
        for k in np.nonzero(v)[0]:
            if not (point_in_wedge(c[k], (0.0, 0.0), 0.0)
                    and point_in_wedge(c[k], S2, th2)):
                bad0 += 1
                break
    rec("T0 顶点个数=4 且每个顶点真在两个楔内", bad0 <= 2,
        f"检查 {n0} 组，异常 {bad0}（允许 ≤2 组数值退化）")

    # ---- T1: 快路径 vs p1 参考实现（良态区域 |Δθ| 明显大于 2ε）----
    n_bad, n_cmp, n_skip = 0, 0, 0
    max_dd = 0.0
    for _ in range(6000):
        S2 = np.array([rng.uniform(-1500, 1500), rng.uniform(-1500, 1500)])
        if np.hypot(*S2) < 1.0:
            continue
        t = float(rng.uniform(30.0, 1500.0))
        th2 = th2_of(S2, t)
        sep = min(abs(ang_diff(th2, 0.0)), 180.0 - abs(ang_diff(th2, 0.0)))
        if sep <= 2.0 * EPS_DEG + 0.3:      # 近临界：参考实现自身会给出病态顶点，跳过
            n_skip += 1
            continue
        D, st = fast_diameters(S2, np.array([t]))
        P, pst = region_by_vertices([(0.0, 0.0), tuple(S2)], [0.0, th2])
        if pst != "polygon" or len(P) < 3:
            continue
        n_cmp += 1
        d_ref, _ = poly_diameter(np.asarray(P, float))
        if not np.isfinite(D[0]):
            n_bad += 1
            continue
        rel = abs(float(D[0]) - d_ref) / max(d_ref, 1e-12)
        max_dd = max(max_dd, rel)
        if rel > 1e-7:
            n_bad += 1
    rec("T1 快路径 vs p1 参考实现（直径，良态）", n_bad == 0,
        f"比较 {n_cmp} 组，跳过近临界 {n_skip} 组，最大相对差 {max_dd:.3e}")

    # ---- T2: 数值直径 vs 精确闭式 D = 2 tan(eps)|S1S2|/sin|θ1-θ2| ----
    worst, worst_cfg, n2 = 0.0, None, 0
    for _ in range(8000):
        S2 = np.array([rng.uniform(-1500, 1500), rng.uniform(-1400, 1400)])
        if np.hypot(*S2) < 5.0:
            continue
        t = float(rng.uniform(20.0, 1500.0))
        th2 = th2_of(S2, t)
        sep = min(abs(ang_diff(th2, 0.0)), 180.0 - abs(ang_diff(th2, 0.0)))
        if sep <= 2.0 * EPS_DEG + 1e-6:      # 退化（无界）区域：无闭式
            continue
        D, _ = fast_diameters(S2, np.array([t]))
        if not np.isfinite(D[0]):
            continue
        dc = closed_form_diameter(t, S2)
        if not math.isfinite(dc):
            continue
        n2 += 1
        rel = abs(float(D[0]) - dc) / max(dc, 1e-12)
        if rel > worst:
            worst, worst_cfg = rel, (S2.copy(), t, float(D[0]), dc)
    rec("T2 数值直径 vs 独立实现（直接解边界交点）", worst < 1e-9,
        f"{n2} 组，最大相对差 {worst:.3e}"
        + ("" if worst_cfg is None else
           f"（最差配置 S2={np.round(worst_cfg[0],3)}, t={worst_cfg[1]:.3f}, "
           f"数值={worst_cfg[2]:.4f}, 独立实现={worst_cfg[3]:.4f}）"))

    # ---- T2b: 经验上界律 D ≈ 2 tan(eps)|S1S2| / sin(γ*)，γ*=min(γ,180-γ) ----
    #   精确直径由 T1/T2 的独立实现给出；本式只在 |Δθ| 远离 2eps 时是好的近似，
    #   近简并（区域被拉成长条）时会低估，故这里记录实测的相对偏差并断言 < 1e-2。
    worst2b, n2b, n2b_big = 0.0, 0, 0
    for _ in range(3000):
        S2 = np.array([rng.uniform(-1400, 1400), rng.uniform(-1200, 1200)])
        if np.hypot(*S2) < 5.0:
            continue
        t = float(rng.uniform(100.0, 1500.0))
        th2 = th2_of(S2, t)
        g = abs((th2 - 0.0 + 180.0) % 360.0 - 180.0)
        gstar = min(g, 180.0 - g)
        if gstar <= 2.0 * EPS_DEG + 15.0:        # 近简并区：近似式不适用，跳过
            continue
        r = float(np.hypot(*S2))
        s = math.sin(math.radians(gstar))
        if s < 1e-9:
            continue
        pred = 2 * math.tan(math.radians(EPS_DEG)) * r / s
        dc = closed_form_diameter(t, S2)
        if not math.isfinite(dc):
            continue
        n2b += 1
        rel = abs(dc - pred) / max(pred, 1e-12)
        worst2b = max(worst2b, rel)
        if rel > 1e-2:
            n2b_big += 1
    rec("T2b 近似律 D ≈ 2 tan(eps)|S1S2|/sin(γ*) 的实测精度（信息项，非判据）",
        True,
        f"{n2b} 组中 {n2b_big} 组相对差 >1e-2，最大相对差 {worst2b:.3e}"
        "（故最终结果一律用 T1/T2 的精确实现，不用该近似式）")

    # ---- T3: 蒙特卡洛真值——直径 >= 区域内采样点对最大距离 ----
    worst3, worst3_cfg, n3 = 0.0, None, 0
    for _ in range(40):
        S2 = np.array([rng.uniform(-1200, 1200), rng.uniform(-1200, 1200)])
        if np.hypot(*S2) < 50.0:
            continue
        t = float(rng.uniform(100.0, 1400.0))
        if np.hypot(S2[0] - t, S2[1]) > R_RECV_MAX:
            continue
        th2 = th2_of(S2, t)
        if unbounded(0.0, th2):
            continue
        D, _ = fast_diameters(S2, np.array([t]))
        if not np.isfinite(D[0]):
            continue
        K = mc_points(S2, t, 20000, rng)
        if len(K) < 2:
            continue
        dmax = max_pair_dist(K)
        n3 += 1
        over = dmax / float(D[0]) - 1.0                # 必须 <= 0
        if over > worst3:
            worst3, worst3_cfg = over, (S2.copy(), t, float(D[0]), dmax)
    rec("T3 直径 >= 区域内 MC 采样点对最大距离", worst3 <= 1e-9,
        f"{n3} 组，最大超出 {worst3:.3e}"
        + ("" if worst3_cfg is None else
           f"（S2={np.round(worst3_cfg[0],2)}, t={worst3_cfg[1]:.1f}, "
           f"数值={worst3_cfg[2]:.4f}, MC={worst3_cfg[3]:.4f}）"))

    # ---- T4: MC 逼近性——数值直径与 MC 最大距离同阶（比值 ∈ [0.6, 1]）----
    #     MC 采到的最大点对距离一定不超过真直径；采样覆盖足够时应有量级一致。
    n4, ratios = 0, []
    for _ in range(40):
        S2 = np.array([rng.uniform(-800, 800), rng.uniform(-800, 800)])
        if np.hypot(*S2) < 50.0:
            continue
        t = float(rng.uniform(100.0, 1400.0))
        if np.hypot(S2[0] - t, S2[1]) > R_RECV_MAX:
            continue
        th2 = th2_of(S2, t)
        if unbounded(0.0, th2):
            continue
        D, _ = fast_diameters(S2, np.array([t]))
        if not np.isfinite(D[0]):
            continue
        K = mc_points(S2, t, 40000, rng)
        if len(K) < 2:
            continue
        n4 += 1
        ratios.append(max_pair_dist(K) / float(D[0]))
    ratios = np.array(ratios)
    ok4 = bool(ratios.size and np.all(ratios >= 0.6) and np.all(ratios <= 1.0 + 1e-9))
    rec("T4 MC 最大距离 / 数值直径 ∈ [0.6, 1]", ok4,
        f"{n4} 组，最小比值 {ratios.min() if ratios.size else float('nan'):.4f}，"
        f"最大比值 {ratios.max() if ratios.size else float('nan'):.4f}")

    # ---- T5: 贴 x 轴退化：必须被判为不可用 ----
    bad5, det5 = 0, []
    for y in (0.0, 1e-6, 1.0):
        S2 = np.array([600.0, y])
        D, st = fast_diameters(S2, np.array([300.0, 900.0]))
        det5.append(f"y={y}: D={np.round(D, 3).tolist()}")
        if not np.all(np.isnan(D)):
            bad5 += 1
    rec("T5 贴 x 轴退化被识别（无界/退化）", bad5 == 0, " | ".join(det5))

    # ---- T6: 反例——y=0 且源比 S2 远 => 无界（直径 +inf，必须剔除）----
    S2 = np.array([600.0, 0.0])
    D, st = fast_diameters(S2, np.array([900.0]))
    rec("T6 y=0 且源比 S2 远 -> 无界（必须剔除）",
        np.isnan(D[0]) and int(st[0]) == 3, f"D={D[0]}, status={int(st[0])}")

    # ---- T7: 交会角 90°（S2 在源正上方 x=t）时 D ≈ 2 tan(eps)|S1S2|，误差 O(eps^2) ----
    #   此时 sin(γ*)=1，该基线下的直径最小。解析式是**近似**（把两锥边界当直线平移），
    #   残差 ~ eps^2 量级；本检查给出实测的相对误差并断言 < 2e-3。
    t = 1000.0
    t7_bad, t7_worst = [], 0.0
    for y in (30.0, 60.0, 120.0, 1000.0):
        S2 = np.array([t, y])
        Dv, _ = fast_diameters(S2, np.array([t]))
        dc = closed_form_diameter(t, S2)
        r = float(np.hypot(*S2))
        target = 2 * math.tan(math.radians(EPS_DEG)) * r      # sin γ* = 1
        rel = abs(float(Dv[0]) - target) / target
        t7_worst = max(t7_worst, rel)
        if abs(float(Dv[0]) - dc) / dc > 1e-9:                # 两条独立实现必须一致
            t7_bad.append(f"y={y}: 数值={float(Dv[0]):.6f} 独立实现={dc:.6f} 不一致")
        if rel > 2e-3:
            t7_bad.append(f"y={y}: 数值={float(Dv[0]):.6f} 解析式={target:.6f} 相对差={rel:.2e}")
    if _unbounded_bearings(0.0, 270.0):
        t7_bad.append("γ*=90° 应判定为良态（非退化）")
    rec("T7 交会角=90° 时 D ≈ 2 tan(eps)|S1S2|（实测误差 < 2e-3）", not t7_bad,
        "；".join(t7_bad) if t7_bad else f"y=30/60/120/1000 m 四组，最大相对差 {t7_worst:.2e}")

    # ---- T8: 源位采样权重归一 + 上界 ----
    ts, w, info = source_samples((0.0, 0.0), 0.0, n_t=200)
    rec("T8 源位采样权重归一 + 上界正确",
        abs(w.sum() - 1.0) < 1e-12 and abs(info["t_hi"] - min(R_RECV_MAX, R_ARENA)) < 1e-9,
        f"t∈[{info['t_lo']:.1f},{info['t_hi']:.1f}], Σw-1={w.sum()-1:.2e}")

    # ---- T9: 期望的解析核对——E[D] 与逐点加权平均一致 ----
    X = np.array([300.0, 447.2, -200.0, 900.0])
    Y = np.array([600.0, 800.0, 300.0, 0.0])
    tt, ww, _ = source_samples((0.0, 0.0), 0.0, n_t=60)
    res = expected_diameter_measured(X, Y, tt, ww)
    manual = []
    for i in range(X.size):
        num = den = 0.0
        for j in range(tt.size):
            D, _ = fast_diameters(np.array([X[i], Y[i]]), np.array([tt[j]]))
            if np.isfinite(D[0]):
                num += ww[j] * float(D[0])
                den += ww[j]
        manual.append(num / den if den > 0 else np.nan)
    ok9 = np.allclose(np.array(manual), res["E_det"], rtol=1e-10, equal_nan=True)
    rec("T9 E[D|可检测] 与逐点加权平均一致", ok9,
        f"manual={np.round(manual,4).tolist()}, batch={np.round(res['E_det'],4).tolist()}")

    if verbose:
        print(f"\n自检总结：{'全部通过' if ok_all else '存在失败项'}")
    return {"ok": ok_all, "checks": out}


# --------------------------------------------------------------------------
# 输出：CSV / JSON / 热力图
# --------------------------------------------------------------------------
def _fmt(v, nd=6):
    if v is None:
        return ""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return "nan" if math.isnan(v) else "inf"
    return round(float(v), nd)


def save_outputs(res, outdir, figures=True, tag=""):
    os.makedirs(outdir, exist_ok=True)
    X, Y, shape = res["X"], res["Y"], res["shape"]
    path = os.path.join(outdir, f"p2_grid_map{tag}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["x_m", "y_m", "r_m", "phi_deg",
                     "E_diam_given_detectable_m", "E_diam_mixed_mm",
                     "p_detectable", "cov_weight", "Dmin_m", "Dmax_m",
                     "E_diam_err_given_detectable_m", "E_diam_err_mixed_m",
                     "cov_err", "n_ok", "usable", "near_axis_unusable_band"])
        thr = res.get("usable_threshold_m", float("inf"))
        for i in range(X.size):
            r = math.hypot(X[i], Y[i])
            phi = math.degrees(math.atan2(Y[i], X[i])) % 360.0
            ed = res["E_det"][i]
            usable = int(np.isfinite(ed) and ed <= thr and res["p_det"][i] > 0)
            wr.writerow([_fmt(X[i], 4), _fmt(Y[i], 4), _fmt(r, 4), _fmt(phi, 4),
                         _fmt(ed), _fmt(res["E"][i]),
                         _fmt(res["p_det"][i]), _fmt(res["cov"][i]),
                         _fmt(res["Dmin"][i]), _fmt(res["Dmax"][i]),
                         _fmt(res["E_err_det"][i]) if res.get("E_err_det") is not None else "",
                         _fmt(res["E_err"][i]) if res.get("E_err") is not None else "",
                         _fmt(res["cov_err"][i]) if res.get("cov_err") is not None else "",
                         int(res["n_ok"][i]), usable,
                         int(np.isfinite(ed) and ed > thr)])
    # JSON 报告
    rep = {k: v for k, v in res.items()
           if k not in ("X", "Y", "E", "E_det", "cov", "p_det", "Dmin", "Dmax", "n_ok",
                        "E_err", "E_err_det", "cov_err", "usable")}
    rep["csv"] = os.path.basename(path)
    with open(os.path.join(outdir, f"p2_grid_report{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    return path


def make_figures(res, outdir, tag=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    os.makedirs(outdir, exist_ok=True)
    X, Y, xs, ys, shape = res["X"], res["Y"], res["xs"], res["ys"], res["shape"]
    ny, nx = shape
    figs = []

    def to_grid(xv, yv, vals):
        g = np.full((ny, nx), np.nan)
        xi = np.searchsorted(xs, xv)
        yi = np.searchsorted(ys, yv)
        g[yi, xi] = vals
        return g

    def show(ax, G, cmap, vmin=None, vmax=None, norm=None, ttl=None):
        kw = {"norm": norm} if norm is not None else {"vmin": vmin, "vmax": vmax}
        im = ax.imshow(G, origin="lower", extent=[xs[0], xs[-1], ys[0], ys[-1]],
                       cmap=cmap, interpolation="nearest", aspect="equal", **kw)
        ax.set_xlim(XLIM[0], XLIM[1])
        ax.set_ylim(YLIM[0], YLIM[1])
        ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
        if ttl:
            ax.set_title(ttl, fontsize=9)
        return im

    def ring(ax, style="w--", lw=1.0, alpha=0.85):
        """只画落在显示范围内的靶区圆弧（R=1800 m）"""
        cx, cy = R_ARENA * np.cos(th), R_ARENA * np.sin(th)
        m = ((cx >= XLIM[0]) & (cx <= XLIM[1]) & (cy >= YLIM[0]) & (cy <= YLIM[1]))
        ax.plot(np.where(m, cx, np.nan), np.where(m, cy, np.nan),
                style, lw=lw, alpha=alpha)

    # 关注区（E ~ 50–1500 m）用**对数色标**，低值段的差异才看得出来
    ZMIN, ZMAX = 50.0, 2000.0
    lnorm = LogNorm(vmin=ZMIN, vmax=ZMAX)
    TICKS = [50, 70, 100, 150, 200, 300, 500, 700, 1000, 1500, 2000]
    ok_use = res.get("usable", np.ones(X.size, bool))
    Gm = to_grid(X, Y, np.where(ok_use, res["E_det"], np.nan))
    Ge = (to_grid(X, Y, np.where(ok_use, res["E_err_det"], np.nan))
          if res.get("E_err_det") is not None else None)
    Gc = to_grid(X, Y, res["p_det"])
    th = np.linspace(0, 2 * math.pi, 2000)
    XLIM = (-1500.0, 2000.0)      # x 轴负方向小一点；正方向放到靶区外，不再截断
    YLIM = (-2050.0, 2050.0)

    # ---------- 图 1：主口径热力图（E[D | 可检测]，对数色标） ----------
    fig, ax = plt.subplots(figsize=(9.6, 11.0))
    im = show(ax, Gm, "viridis_r", ZMIN, ZMAX, norm=lnorm,
              ttl="B-Problem 2: expected intersection-region diameter vs 2nd detection point")
    fig.text(0.5, 0.945,
             f"log colour scale;  measured bearings;  source prior area-uniform on x-axis;\n"
             f"$\\varepsilon$={res['eps_deg']}°,  $\\theta_1$={res['theta1']}°,  "
             f"reach gate $|S_2G|\\leq${int(R_RECV_MAX)} m",
             ha="center", va="top", fontsize=9)
    cb = fig.colorbar(im, ax=ax, shrink=0.8, extend="both")
    cb.set_label("E[intersection diameter | detectable]  (m, log scale)")
    cb.set_ticks(TICKS)
    cb.ax.set_yticklabels([f"{t:g}" for t in TICKS])
    # 网格索引 -> 世界坐标（注意 Gm 是二维，argmin 给的是行主序下标，
    # 必须用 reshape 后的坐标数组，不能直接用扁平的 X/Y！）
    GX = np.full((ny, nx), np.nan)
    GY = np.full((ny, nx), np.nan)
    GX[np.searchsorted(ys, Y), np.searchsorted(xs, X)] = X
    GY[np.searchsorted(ys, Y), np.searchsorted(xs, X)] = Y

    def best_xy(G):
        r, c = np.unravel_index(int(np.nanargmin(G)), G.shape)
        return float(GX[r, c]), float(GY[r, c]), float(G[r, c])

    ring(ax)
    ax.plot([0], [0], "r*", ms=16, label="S1 = origin (detector)", zorder=8)
    bx, by, vb = best_xy(Gm)
    for yy in {by, -by}:
        ax.plot([bx], [yy], "wo", ms=10, mfc="none", mew=2, zorder=7)
    # 标签放在点左上方（图内），避免压住色标
    ax.annotate(f"best S2 = ({bx:.0f}, {by:.0f}) m\nE = {vb:.1f} m",
                xy=(bx, by), xytext=(-165, 55), textcoords="offset points",
                color="k", fontsize=9, ha="left", va="bottom",
                bbox=dict(boxstyle="round,pad=0.3", fc="w", ec="0.4", alpha=0.9),
                arrowprops=dict(arrowstyle="->", color="k", lw=1.1), zorder=9)
    ax.legend(loc="lower left", fontsize=8, framealpha=0.85)
    f1 = os.path.join(outdir, f"p2_grid_E_heatmap{tag}.png")
    fig.tight_layout(); fig.savefig(f1, dpi=150); plt.close(fig); figs.append(f1)

    # ---------- 图 2：两口径并排 ----------
    if Ge is not None:
        fig, axes = plt.subplots(1, 2, figsize=(15.0, 10.4))
        for ax2, G, ttl in (
                (axes[0], Gm, "(a) measured bearings fixed\n"
                              "expectation over source position only"),
                (axes[1], Ge, "(b) error-averaged\n"
                              "expectation over source position AND ±1° reading errors")):
            im = show(ax2, G, "viridis_r", ZMIN, ZMAX, norm=lnorm)
            ring(ax2)
            ax2.plot([0], [0], "r*", ms=12)
            ibx, iby, ibv = best_xy(G)
            ax2.plot([ibx], [iby], "wo", ms=8, mfc="none", mew=2, zorder=7)
            ax2.set_title(f"{ttl}\nmin E = {ibv:.1f} m at ({ibx:.0f}, {iby:.0f})", fontsize=9)
            cb2 = fig.colorbar(im, ax=ax2, shrink=0.75, extend="both")
            cb2.set_label("E[D | detectable] (m, log scale)")
            cb2.set_ticks([50, 100, 200, 300, 500, 1000, 2000])
        f2 = os.path.join(outdir, f"p2_grid_E_heatmap_two{tag}.png")
        fig.tight_layout(); fig.savefig(f2, dpi=150); plt.close(fig); figs.append(f2)

    # ---------- 图 3：可检测概率 ----------
    fig, ax = plt.subplots(figsize=(9.0, 11.0))
    im = show(ax, Gc, "magma", 0.0, 1.0,
              ttl="Detectability: probability the 2nd detector can even hear the channel")
    fig.colorbar(im, ax=ax, shrink=0.8).set_label("P(|S2G| ≤ 1500 m) under source prior")
    ring(ax, "c--", 1.0, 0.9)
    ax.plot([0], [0], "r*", ms=15)
    f3 = os.path.join(outdir, f"p2_grid_coverage{tag}.png")
    fig.tight_layout(); fig.savefig(f3, dpi=150); plt.close(fig); figs.append(f3)

    # ---------- 图 4：固定 phi 的 E(r) 剖面与固定 r 的 E(phi) 剖面 ----------
    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.4))
    r_all = np.hypot(X, Y)
    phi_all = np.degrees(np.arctan2(Y, X)) % 360.0
    for phi0, style in ((90.0, "-"), (80.0, "--"), (70.0, "-."), (45.0, ":")):
        m = np.abs(((phi_all - phi0 + 180) % 360) - 180) < res["step"] / (2 * np.maximum(r_all, 1)) * 1.2
        if m.sum() < 3:
            continue
        o = np.argsort(r_all[m])
        axes[0].plot(r_all[m][o], res["E_det"][m][o], style, lw=1.4, label=f"φ={phi0:.0f}°")
    axes[0].set_xlabel("baseline r = |S1S2| (m)"); axes[0].set_ylabel("E[D | detectable] (m)")
    axes[0].set_title("radial profile (measured bearings)", fontsize=10)
    axes[0].legend(fontsize=8); axes[0].grid(alpha=0.3)
    for r0, style in ((200.0, "-"), (400.0, "--"), (800.0, "-."), (1200.0, ":")):
        m = np.abs(r_all - r0) < res["step"] * 1.2
        if m.sum() < 3:
            continue
        o = np.argsort(phi_all[m])
        axes[1].plot(phi_all[m][o], res["E_det"][m][o], style, lw=1.4, label=f"r={r0:.0f} m")
    axes[1].set_xlabel("φ = arg(S2) (deg)"); axes[1].set_ylabel("E[D | detectable] (m)")
    axes[1].set_title("angular profile: minima near the 90°-crossing geometry", fontsize=10)
    axes[1].legend(fontsize=8); axes[1].grid(alpha=0.3)
    f4 = os.path.join(outdir, f"p2_grid_profiles{tag}.png")
    fig.tight_layout(); fig.savefig(f4, dpi=150); plt.close(fig); figs.append(f4)

    # ---------- 图 5：交会区域随 S2 变化的示意 ----------
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 5.2))
    t_demo = 900.0
    for ax2, (rr_, pp_) in zip(axes, ((900.0, 90.0), (180.0, 80.0), (900.0, 20.0))):
        S2 = np.array([rr_ * math.cos(math.radians(pp_)), rr_ * math.sin(math.radians(pp_))])
        th2 = float(np.degrees(np.arctan2(-S2[1], t_demo - S2[0])) % 360.0)
        P, stt = region_by_vertices([(0.0, 0.0), tuple(S2)], [0.0, th2])
        D, stf = fast_diameters(S2, np.array([t_demo]))
        for base, colr, anch in ((0.0, "tab:blue", np.zeros(2)), (th2, "tab:orange", S2)):
            for s in (-1, 1):
                a = math.radians(base + s * EPS_DEG)
                L = 2200.0
                ax2.plot([anch[0], anch[0] + L * math.cos(a)],
                         [anch[1], anch[1] + L * math.sin(a)],
                         color=colr, lw=1.0, alpha=0.75)
        if len(P) >= 3 and not _unbounded_bearings(0.0, th2):
            H = convex_hull(np.asarray(P, float))
            H = np.vstack([H, H[:1]])
            ax2.fill(H[:, 0], H[:, 1], color="crimson", alpha=0.55, zorder=5)
        ax2.plot([0], [0], "b*", ms=13, zorder=6)
        ax2.plot([S2[0]], [S2[1]], "o", color="tab:orange", ms=7, zorder=6)
        ax2.plot([t_demo], [0], "k^", ms=8, zorder=6)
        ax2.set_xlim(-1500, 2400); ax2.set_ylim(-1400, 2100)
        dv = float(D[0]) if np.isfinite(D[0]) else float("nan")
        ax2.set_title(f"source t=900 m,  r={rr_:.0f} m, φ={pp_:.0f}°\n"
                      f"intersection D = {dv:.1f} m", fontsize=9)
        ax2.set_xlabel("x (m)"); ax2.set_ylabel("y (m)"); ax2.grid(alpha=0.25)
    f5 = os.path.join(outdir, f"p2_grid_region_demo{tag}.png")
    fig.tight_layout(); fig.savefig(f5, dpi=150); plt.close(fig); figs.append(f5)
    return figs


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def run(theta1=0.0, step=DEF_STEP, n_t=DEF_N_T, n_e=DEF_N_E, weight="area",
        domain="arena", eps=EPS_DEG, outdir=None, figures=True, mask_radius=DEF_MASK_RADIUS,
        seed=20260913, reach=True, checks=True, verbose=True):
    t0 = time.time()
    S1 = (0.0, 0.0)
    ts, w_area, sinfo = source_samples(S1, theta1, eps, n_t)
    w = w_area if weight == "area" else length_weights(ts)
    if ts.size == 0:
        raise SystemExit("源位采样为空：检查 theta1 与靶区/接收半径设置")
    X, Y, xs, ys, shape = make_grid(step=step, arena_r=R_ARENA, domain=domain)
    if verbose:
        print(f"网格点 {X.size} 个（step={step} m, domain={domain}）；"
              f"源位 {ts.size} 个 t∈[{ts[0]:.1f},{ts[-1]:.1f}] m, 权重={weight}")
    meas = expected_diameter_measured(X, Y, ts, w, eps, reach=reach)
    err = expected_diameter_error_avg(X, Y, ts, w, eps, n_e=n_e, seed=seed, reach=reach)
    res = {
        "model": "P2 grid simulation: E[diameter of intersection region] over 2nd detection point",
        "theta1": float(theta1), "eps_deg": float(eps), "weight": weight, "domain": domain,
        "step": float(step), "mask_radius": float(mask_radius), "reach_gate": bool(reach),
        "source_prior": sinfo, "arena_r": R_ARENA,
        "r_recv_range": [R_RECV_MIN, R_RECV_MAX], "near_r": NEAR_R,
        "S1": list(S1), "grid_points": int(X.size), "shape": list(shape),
        "xs": [float(v) for v in xs], "ys": [float(v) for v in ys],
        "X": X, "Y": Y,
        "E": meas["E"], "E_det": meas["E_det"], "cov": meas["cov"], "p_det": meas["p_det"],
        "Dmin": meas["Dmin"], "Dmax": meas["Dmax"], "n_ok": meas["n_ok"],
        "E_err": err["E_err"], "E_err_det": err["E_err_det"],
        "cov_err": err["cov_err"], "n_err_pairs": err["n_pairs"],
    }
    # 汇总统计：主目标 = E[D|可检测]（可检测性门控），混口径 E[D·1{可检测}] 作对照
    t_nom = float(np.sum(w * ts))
    # 近轴"不可用带"阈值：E[D|可检测] 超过中位数 10 倍的点（几乎贴着 x 轴，
    # 两锥近简并、交会区域被拉成长条）标注为不可用，避免它们污染色标与结论。
    med = float(np.nanmedian(meas["E_det"]))
    usable_thr = 10.0 * med
    res["usable_threshold_m"] = usable_thr
    usable = np.isfinite(meas["E_det"]) & (meas["E_det"] <= usable_thr) & (meas["p_det"] > 0)
    res["usable"] = usable
    if np.any(usable):
        E_use = np.where(usable, meas["E_det"], np.nan)
    else:
        E_use = meas["E_det"]

    def _pick(arr):
        a = np.asarray(arr, float)
        if not np.any(np.isfinite(a)):
            return None
        i = int(np.nanargmin(a))
        return {"S2": [float(X[i]), float(Y[i])], "r_m": float(math.hypot(X[i], Y[i])),
                "phi_deg": float(math.degrees(math.atan2(Y[i], X[i])) % 360.0),
                "value_m": float(a[i]), "index": i,
                "p_det": float(meas["p_det"][i]),
                "E_mixed_m": float(meas["E"][i]),
                "E_err_det_m": (float(err["E_err_det"][i])
                                if np.isfinite(err["E_err_det"][i]) else None),
                "E_err_mixed_m": float(err["E_err"][i])}
    best_det = _pick(E_use)
    best_mix = _pick(meas["E"])
    res["summary"] = {
        "objective": "E[D | detectable]（|S2G| <= 1500 m 门控后按面积均匀先验加权）",
        "E_det_min_m": float(np.nanmin(E_use)),
        "E_det_median_m": med,
        "E_det_max_m": float(np.nanmax(meas["E_det"])),
        "E_mixed_min_m": float(np.nanmin(meas["E"])),
        "usable_points": int(usable.sum()),
        "usable_fraction": float(usable.mean()),
        "near_axis_band_points": int((np.isfinite(meas["E_det"])
                                      & (meas["E_det"] > usable_thr)).sum()),
        "near_axis_band_mean_abs_y_m": (float(np.mean(np.abs(
            Y[np.isfinite(meas["E_det"]) & (meas["E_det"] > usable_thr)])))
            if np.any(np.isfinite(meas["E_det"]) & (meas["E_det"] > usable_thr)) else None),
        "best_det": best_det, "best_mixed": best_mix,
        "best_S2": best_det["S2"] if best_det else None,
        "best_r_m": best_det["r_m"] if best_det else None,
        "best_phi_deg": best_det["phi_deg"] if best_det else None,
        "best_r_over_t": (best_det["r_m"] / t_nom) if best_det else None,
        "mean_source_range_m": t_nom,
        "theory_note": ("交会角 90° 时 D 取该基线下的最小值 ≈ 2 tan(eps)·|S1S2|；"
                        "一般情形 D 随 |S2G| 与近简并程度急剧增大"),
        "x_axis_degenerate": ("y≈0 时两示向度近平行(|Δθ|≤2eps) → 交会区域无界、直径=+∞，"
                              "被 mask_radius 剔除；其邻域(|y| 小)直径可达 10^4-10^5 m，"
                              f"已用 usable_threshold={usable_thr:.1f} m 标注为不可用带"),
        "reach_gate": ("|S2G| > 有效接收半径上界 1500 m 的源位样本不可检测，"
                       "不计入 E[D|可检测]；混口径 E[D·1{可检测}] 另列"),
        "runtime_s": None,
    }
    if checks:
        res["checks"] = selfcheck(verbose=verbose)["checks"]
    res["summary"]["runtime_s"] = round(time.time() - t0, 3)
    if outdir:
        save_outputs(res, outdir, figures=False)
        if figures:
            figs = make_figures(res, outdir)
            res["figures"] = [os.path.basename(f) for f in figs]
        save_outputs(res, outdir, figures=False)
    if verbose:
        s = res["summary"]
        b = s["best_det"]
        print(f"\n最优第二检测点 S2* = ({b['S2'][0]:.1f}, {b['S2'][1]:.1f}) m "
              f"（r={b['r_m']:.1f} m, φ={b['phi_deg']:.1f}°, r/⟨t⟩={s['best_r_over_t']:.3f}）")
        print(f"E[D|可检测] 最小 = {s['E_det_min_m']:.3f} m；中位数 = {s['E_det_median_m']:.3f} m；"
              f"单条基线 2tan(eps)r = {2*math.tan(math.radians(eps))*b['r_m']:.3f} m（同心圆下界）")
        print(f"该点 P(可检测) = {b['p_det']:.4f}；混口径 E[D·1] = {b['E_mixed_m']:.3f} m；"
              f"误差口径 E[D|可检测] = {b['E_err_det_m']}")
        print(f"可用点 {s['usable_points']}/{res['grid_points']}"
              f"（近轴不可用带 {s['near_axis_band_points']} 个，阈值 {res['usable_threshold_m']:.1f} m）")
        print(f"耗时 {s['runtime_s']} s")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="B 题问题 2：第二检测点网格上的交会区域直径期望热力图")
    ap.add_argument("--theta1", type=float, default=0.0, help="首次探测的示向度（度），默认 0（x 轴正向）")
    ap.add_argument("--step", type=float, default=DEF_STEP, help="网格步长（m）")
    ap.add_argument("--n-t", type=int, default=DEF_N_T, help="x 轴源位采样数")
    ap.add_argument("--n-e", type=int, default=DEF_N_E, help="误差 MC 采样数")
    ap.add_argument("--weight", choices=["area", "length"], default="area",
                    help="源位先验权重：area ∝ t（面积均匀，默认）/ length 等权")
    ap.add_argument("--domain", choices=["arena", "reach"], default="arena",
                    help="S2 取值范围：整个靶区圆域 / 还要满足 |S2G|<=1500")
    ap.add_argument("--out", default=None, help="输出目录")
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--no-checks", action="store_true", help="跳过自检（只出结果，快很多）")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args(argv)
    if a.selfcheck:
        r = selfcheck()
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            with open(os.path.join(a.out, "p2_grid_selfcheck.json"), "w", encoding="utf-8") as f:
                json.dump(r, f, ensure_ascii=False, indent=2)
        return 0 if r["ok"] else 1
    run(theta1=a.theta1, step=a.step, n_t=a.n_t, n_e=a.n_e, weight=a.weight,
        domain=a.domain, outdir=a.out, figures=not a.no_figures,
        checks=not a.no_checks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
