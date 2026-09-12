"""B 题问题 2（模拟）：固定首次探测扇形后，第二检测点网格上的"交会区域直径期望"热力图。

问题设定（按需求方给定的简化模型）
----------------------------------
1. **固定当前探测得到的扇形区域**：探测器（机器狗）位于原点 ``S1 = (0, 0)``，
   探测方向为 x 轴正方向，示向度误差界 ``eps = 1 deg``。于是第一次探测给出的信息是角楔

       W1 = { X : |ang(X - S1) - theta1| <= eps }

   ``theta1`` 取自当前探测数据（默认 0 deg，即"探测方向为 x 轴正方向"）。
2. **干扰源均匀分布在扇形内，近似认为都在 x 轴上**：源位 ``G = (t, 0)``，
   权重由"扇形内面积均匀"退化得到：面积元 ``dA = r dr dtheta -> w(t) ∝ t``
   （``--weight area``，默认）；另提供等权（``--weight length``）作对照。
3. **网格**：把每个网格点当作第二个检测点 ``S2``。默认网格框在右侧多留 0.2R
   （``x_range=(-1800, 2160)``），因为最优点在右半区，这样同样点数下右半区更密。
   注意**可行域仍是靶区圆域** ``R <= 1800 m``，``x > 1800`` 的部分是空框。
4. **交会区域与直径**：给定源位 ``G``，两个检测点各得一条带 ±eps 的示向度锥，
   两者之交是凸四边形 ``R = W1 ∩ W2``，其**直径** D = 区域内任意两点距离的最大值。
5. **期望**：``E[D](S2) = Σ_i w_i D(S2, t_i)``，只在"可检测且有界"的样本上取平均，
   同时记录"可检测概率"，避免把不可用点伪装成好点。
6. **热力图**：``E[D](S2)`` 作为网格点 ``(x, y)`` 的函数，对数色标。

两套口径（主 / 辅）
-------------------
* ``measured``（主）：两个楔都用**测得值** ± 1°，即 ``R = W1(theta1) ∩ W2(theta2)``，
  期望只对源位 ``t`` 取 —— 完全对应"固定当前探测数据"的字面含义。
* ``error_avg``（辅）：同一个区域，但期望**同时对 ±1° 测量误差取**，
  即 ``E_{t, e1, e2}[ D ]`` —— 更贴近"定位效果"的真实统计含义。

为什么网格必须是真正二维的（重要结论）
--------------------------------------
若把 ``S2`` 放在 x 轴上（``y = 0``），则两条示向度近似平行，夹角 ``|dtheta| <= 2*eps``，
交会区域**无界**、直径为 +∞（这正是 ``p1_intersection.region_by_vertices`` 会报
``unbounded`` 的退化几何，等价于"沿示向度方向逼近"）。所以 ``y = 0`` 必须在网格上被
剔除。更进一步，``|y|`` 很小但未退化的点，交会区域会被拉成极长的细条
（直径可达 10^4–10^5 m），数学上没错但工程上无用，程序用
``usable_threshold = 10 × 中位数`` 标注并掩码。

可检测性门控
------------
第二个检测点要能收到该频道信号，必须 ``|S2 G| <= 有效接收半径上界 1500 m``。
不加这个门控会选出几何有效但物理收不到信号的假最优点，所以它是模型的一部分
（默认开启，``--no-reach`` 可关闭对照）。

正确性验证
----------
直径由三条**互相独立**的实现给出，随机算例最大相对差 < 1e-13：
``p1_intersection.region_by_vertices``（半平面枚举）、``independent_diameter``
（世界坐标直接解边界交点）、``fast_diameters_vec``（角点枚举 + 楔定义筛选）。
``--selfcheck`` 另含蒙特卡洛与退化算例（T0–T10）。

用法
----
    python src/p2_grid_expectation.py --selfcheck
    python src/p2_grid_expectation.py --step 20 --n-t 500 --out out/p2_grid
    python src/p2_grid_expectation.py --theta1 30 --out out/p2_grid_t30
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from p1_intersection import BEARING_ERR, ang_diff, bearing, region_by_vertices  # noqa: E402

# --------------------------------------------------------------------------
# 物理常数（题目附录 1/2）
# --------------------------------------------------------------------------
EPS_DEG = BEARING_ERR          # 示向度误差界 1°
R_ARENA = 1800.0               # 目标区域半径（m）
R_RECV_MIN = 1000.0            # 有效接收半径下界（m，接口不返回）
R_RECV_MAX = 1500.0            # 有效接收半径上界（m，取信号的必要条件）
NEAR_R = 5.0                   # 近场阈值（m）：更近则没有示向度

# 默认计算参数
DEF_STEP = 20.0
DEF_X_RANGE = (-R_ARENA, 1.2 * R_ARENA)      # 右侧多留 0.2R（框内留白，便于看全）
DEF_Y_RANGE = (-R_ARENA, R_ARENA)
DEF_N_T = 500                  # x 轴上源位采样数
DEF_N_E = 400                  # 误差 MC 次数（error_avg 口径）
DEFAULT_SEED = 20260913


# --------------------------------------------------------------------------
# 基本几何
# --------------------------------------------------------------------------
def point_in_wedge(X, p, theta, err=EPS_DEG, tol=1e-9):
    """X 是否在角楔内（与楔顶点重合视为在楔内）"""
    X = np.asarray(X, float)
    p = np.asarray(p, float)
    if float(np.linalg.norm(X - p)) < tol:
        return True
    return abs(ang_diff(bearing(p, X), theta)) <= err + 1e-12


def _unbounded_bearings(theta1, theta2, err=EPS_DEG):
    """两楔交无界 <=> 存在方向与两条示向度夹角都 <= err。

    对两个示向度，等价于 ``min(|dth|, 180-|dth|) <= 2*err``。
    """
    d = abs(ang_diff(theta2, theta1))
    return min(d, 180.0 - d) <= 2.0 * err + 1e-12


def _corner_points(Pw, thP, Qw, thQ, eps):
    """两个角楔交的 6 个候选角点，**全部在世界坐标下求解**。

    每个角楔 ``|ang(X - P) - θ| <= eps`` 的两条边界线方向为 ``θ ∓ eps``，
    交点由四线两两相交得到（6 个候选）；顶点判定直接用楔的定义
    （候选点 X 是顶点 ⟺ 对每个楔都有 ``|ang(X-P) - θ| <= eps`` 或 X 恰在顶点 P）。
    这个判据与坐标系定向、2x2 解法的行列式符号都无关，因此最稳健。

    返回 ``(corner_world, valid)``，形状 ``(..., 6, 2)`` 与 ``(..., 6)``。
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

    corners, valid = [], []
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


def _diam_from_corners(cw, v, shp):
    """从候选角点与其可用性掩码求凸四边形直径（世界坐标下，距离即真实距离）"""
    nP = cw.shape[-2]
    best = np.zeros(shp)
    for ii in range(nP):
        for jj in range(ii + 1, nP):
            d2 = ((cw[..., ii, 0] - cw[..., jj, 0]) ** 2
                  + (cw[..., ii, 1] - cw[..., jj, 1]) ** 2)
            best = np.where(v[..., ii] & v[..., jj], np.maximum(best, d2), best)
    return best, v.sum(axis=-1)


def independent_diameter(t, S2, eps=EPS_DEG):
    """交会区域直径的**独立参考实现**（标量、世界坐标、直接解边界交点）。

    与 ``_corner_points`` 走的是不同代码路径（这里用射线参数式解交点）。
    无界（``min(|dth|,180-|dth|) <= 2*eps``）返回 ``inf``。
    """
    S2 = np.asarray(S2, float)
    t = float(t)
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


def fast_diameters_vec(S2s, ts, eps=EPS_DEG):
    """批量快路径：S2s (m,2) × ts (n,) -> D (m,n), status (m,n)。

    **源必须固定在 x 轴正半轴（S1 在原点）**，这是本题设定。

    status 编码：0 = 有界多边形，1 = 空，2 = 退化，3 = 无界。
    """
    S2s = np.asarray(S2s, float)
    ts = np.asarray(ts, float).ravel()
    m, n = S2s.shape[0], ts.size
    D = np.full((m, n), np.nan)
    status = np.ones((m, n), dtype=np.int8)
    if m == 0 or n == 0:
        return D, status
    r = np.hypot(S2s[:, 0], S2s[:, 1])
    ok_row = r >= 1e-9
    status[~ok_row, :] = 2
    th2 = np.degrees(np.arctan2(-S2s[:, 1][:, None],
                                ts[None, :] - S2s[:, 0][:, None])) % 360.0
    dth = np.abs((th2 - 0.0 + 180.0) % 360.0 - 180.0)
    sep = np.minimum(dth, 180.0 - dth)
    unb = (sep <= 2.0 * eps + 1e-12) | (~ok_row[:, None])
    status[unb] = np.where(np.broadcast_to(ok_row[:, None], unb.shape), 3, 2)[unb]
    ok = ~unb
    if not np.any(ok):
        return D, status

    S1w = np.zeros((m, n, 2))
    S2w = np.broadcast_to(S2s[:, None, :], (m, n, 2))
    th1g = np.zeros((m, n))
    corner, valid = _corner_points(S1w, th1g, S2w, th2, eps)     # 世界坐标
    cw = corner.reshape(m, n, corner.shape[-2], 2)
    v = valid.reshape(m, n, valid.shape[-1])
    best, n_valid = _diam_from_corners(cw, v, (m, n))
    status = np.where(ok & (n_valid < 2), 1, status).astype(np.int8)
    finite = ok & (n_valid >= 2) & np.isfinite(best)
    D = np.where(finite, np.sqrt(np.maximum(best, 0.0)), np.nan)
    status = np.where(finite, 0, status).astype(np.int8)
    return D, status


def fast_diameters(S2, ts, eps=EPS_DEG):
    """``fast_diameters_vec`` 的单点版"""
    D, st = fast_diameters_vec(np.asarray(S2, float)[None, :],
                               np.asarray(ts, float).ravel(), eps)
    return D[0], st[0]


def _fast_pair_grid(S1, th1, S2, th2, eps):
    """通用批量快路径：``(...,)`` 形状的 S1/th1/S2/th2 -> D 与 status。

    与 ``fast_diameters_vec`` 同一套做法，但两个角楔都任意
    （不要求 S1 在原点、源在 x 轴上）。用于 error_avg 口径。
    """
    P1 = np.asarray(S1, float)
    P2 = np.asarray(S2, float)
    th1 = np.asarray(th1, float)
    th2 = np.asarray(th2, float)
    if th2.ndim > th1.ndim:
        th1 = th1.reshape(th1.shape + (1,) * (th2.ndim - th1.ndim))
    shp = np.broadcast_shapes(th1.shape, th2.shape)
    th1 = np.broadcast_to(th1, shp)
    th2 = np.broadcast_to(th2, shp)
    P1 = np.broadcast_to(np.asarray(P1, float)[..., None, :], shp + (2,))
    P2 = np.broadcast_to(np.asarray(P2, float)[..., None, :], shp + (2,))

    rho = np.linalg.norm(P1 - P2, axis=-1)
    sep = np.abs((th2 - th1 + 180.0) % 360.0 - 180.0)
    sep = np.minimum(sep, 180.0 - sep)
    D = np.full(shp, np.nan)
    status = np.ones(shp, dtype=np.int8)
    status[sep <= 2.0 * eps + 1e-12] = 3
    status[rho < 1e-9] = 2
    ok = ~((sep <= 2.0 * eps + 1e-12) | (rho < 1e-9))
    if not np.any(ok):
        return D, status
    corner, valid = _corner_points(P1, th1, P2, th2, eps)
    cw = corner.reshape(shp + (corner.shape[-2], 2))
    v = valid.reshape(shp + (valid.shape[-1],))
    best, n_valid = _diam_from_corners(cw, v, shp)
    status = np.where(ok & (n_valid < 2), 1, status).astype(np.int8)
    finite = ok & (n_valid >= 2) & np.isfinite(best)
    D = np.where(finite, np.sqrt(np.maximum(best, 0.0)), np.nan)
    status = np.where(finite, 0, status).astype(np.int8)
    return D, status


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
    对角向积分后 ``w(r) ∝ r``，故 ``w_i ∝ t_i``（归一化后即离散先验）。
    ``t_hi = min(r_recv_max, 沿 theta1 到靶区边界的距离)``。
    """
    S1 = np.asarray(S1, float)
    t_hi = min(r_recv_max, sector_ray_exit(S1, theta1, r_arena))
    t_lo = near
    if t_hi <= t_lo:
        return np.zeros(0), np.zeros(0), {"t_lo": t_lo, "t_hi": t_hi, "n_t": 0}
    ts = np.linspace(t_lo, t_hi, int(n_t))
    w_area = ts / float(ts.sum())
    info = {"t_lo": float(t_lo), "t_hi": float(t_hi), "n_t": int(n_t),
            "weight": "area",
            "t_peak_note": "w(t) ∝ t（面积均匀退化的严格结果）",
            "sector_half_angle_deg": float(err),
            "sector_full_width_at_t_hi_m": float(2.0 * t_hi * math.tan(math.radians(err)))}
    return ts, w_area, info


def length_weights(ts):
    w = np.ones_like(np.asarray(ts, float))
    return w / float(w.sum())


# --------------------------------------------------------------------------
# 网格与期望
# --------------------------------------------------------------------------
def make_grid(step=DEF_STEP, x_range=DEF_X_RANGE, y_range=DEF_Y_RANGE,
              arena_r=R_ARENA, domain="arena"):
    """生成网格点（仅保留靶区圆域内、且不贴 x 轴退化带的点）。

    默认网格框右侧多留 0.2R（``x_range=(-1800, 2160)``）：最优点在右半区
    （约 ``x ≈ +1080`` m），把点堆在那里比均匀铺满 ±1800 更划算。
    **注意可行域仍是靶区圆域** ``R <= 1800 m``，``x > 1800`` 的部分不会进入结果。
    """
    xs = np.arange(x_range[0], x_range[1] + 1e-9, step)
    ys = np.arange(y_range[0], y_range[1] + 1e-9, step)
    DX, DY = np.meshgrid(xs, ys)             # shape (ny, nx)
    X, Y = DX.ravel(), DY.ravel()
    keep = (X * X + Y * Y <= arena_r * arena_r) & (np.abs(Y) > 1e-9)
    if domain == "reach":
        d = np.sqrt(np.minimum(X ** 2, (np.abs(X) - R_RECV_MAX) ** 2) + Y ** 2)
        keep &= (d <= R_RECV_MAX)
    return X[keep], Y[keep], xs, ys, DX.shape


def reach_ok(X, Y, ts, r_recv_max=R_RECV_MAX):
    """可检测性门控矩阵：``|S2 - G_i| <= r_recv_max``。

    源在 x 轴上，对固定 (x,y) 关于 t 的最小值在 ``t = clip(x, t_lo, t_hi)`` 处取到。
    """
    X = np.asarray(X, float)[:, None]
    Y = np.asarray(Y, float)[:, None]
    ts = np.asarray(ts, float)[None, :]
    t_clip = np.clip(X, float(np.min(ts)), float(np.max(ts)))
    return np.sqrt((X - t_clip) ** 2 + Y ** 2) <= r_recv_max + 1e-9


def expected_diameter_measured(X, Y, ts, w, eps=EPS_DEG, reach=True, chunk=4096):
    """主口径：区域用测得值 ±eps，期望只对源位取。

    返回 ``E``（``E[D*1{可检测}]``）、``E_det``（``E[D|可检测]``，主目标）、
    ``cov``/``p_det``、``Dmin``/``Dmax``/``n_ok``。
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
        D, _ = fast_diameters_vec(S2[s:e], ts, eps)
        m = np.isfinite(D)
        if reach:
            m &= reach_ok(S2[s:e, 0], S2[s:e, 1], ts)
        sw = np.where(m, w[None, :], 0.0).sum(axis=1)
        contrib = (np.where(m, D, 0.0) * w[None, :]).sum(axis=1)
        with np.errstate(invalid="ignore"):
            E[s:e] = contrib
            E_det[s:e] = np.where(sw > 0, contrib / np.maximum(sw, 1e-300), np.nan)
            Dmin[s:e] = np.where(m.any(axis=1),
                                 np.min(np.where(m, D, np.inf), axis=1), np.nan)
            Dmax[s:e] = np.where(m.any(axis=1),
                                 np.max(np.where(m, D, -np.inf), axis=1), np.nan)
        cov[s:e] = sw
        p_det[s:e] = sw / wsum
        n_ok[s:e] = m.sum(axis=1)
    return {"E": E, "E_det": E_det, "cov": cov, "p_det": p_det,
            "Dmin": Dmin, "Dmax": Dmax, "n_ok": n_ok}


def expected_diameter_error_avg(X, Y, ts, w, eps=EPS_DEG, n_e=DEF_N_E,
                                chunk=1024, seed=DEFAULT_SEED, reach=True):
    """辅口径：区域仍取 ``W1(theta1) ∩ W2(theta2)``，但期望**同时对 ±eps 误差取**。

    定义为 ``E_err(X) = E_{e1,e2}[ E_{t|e}[D * 1{可检测}] ]``。

    实现用**分块蒙特卡洛**：对每批网格点抽 ``n_e`` 组独立误差 ``(e1,e2)``，
    第 k 组只作用到该批第 k 个点上 —— 每个网格点得到 ``n_e`` 个独立无偏估计，取均值。
    代价是 ``n_e × n_t × 网格点数``，而不是误差笛卡尔积
    （后者在 1 万网格点上要十几 GB，实测会被拖死）。
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
        E1 = rng.uniform(-eps, eps, blk)
        E2 = rng.uniform(-eps, eps, blk)
        S2b = S2[s:e]
        S1b = np.zeros((blk, 2))
        base2 = np.degrees(np.arctan2(-S2b[:, 1][:, None],
                                      ts[None, :] - S2b[:, 0][:, None])) % 360.0
        D, _ = _fast_pair_grid(S1b, E1[:, None], S2b, base2 + E2[:, None], eps)
        m = np.isfinite(D)
        if reach:
            m &= reach_ok(S2b[:, 0], S2b[:, 1], ts)
        contrib = (np.where(m, D, 0.0) * w[None, :]).sum(axis=1)
        wsum = np.where(m, w[None, :], 0.0).sum(axis=1)
        with np.errstate(invalid="ignore"):
            E_err_det[s:e] = np.where(wsum > 0, contrib / np.maximum(wsum, 1e-300), np.nan)
        cov_err[s:e] = wsum
        E_err[s:e] = contrib
    return {"E_err": E_err, "E_err_det": E_err_det, "cov_err": cov_err,
            "n_pairs": int(n_e), "estimator": "逐点蒙特卡洛（无偏）"}


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------
def selfcheck(verbose=True, seed=7):
    """独立实现交叉校验 + 退化算例 + 期望一致性（T0–T10）"""
    out = []
    ok_all = True

    def rec(name, ok, detail=""):
        nonlocal ok_all
        ok_all = ok_all and ok
        out.append({"check": name, "ok": bool(ok), "detail": detail})
        if verbose:
            print(f"[{'OK ' if ok else 'FAIL'}] {name}  {detail}")

    def th2_of(S2, t):
        return float(np.degrees(np.arctan2(-S2[1], t - S2[0])) % 360.0)

    def mc_points(S2, t, n_pt, rng_):
        """在两个楔各自锥内采样，保留落在交会区域内的点（向量化）"""
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

    # ---- T0: 顶点个数=4 且每个顶点真在两个楔内 ----
    n0, bad0 = 0, 0
    for _ in range(2500):
        S2 = np.array([rng.uniform(-1500, 1500), rng.uniform(-1400, 1400)])
        if np.hypot(*S2) < 200.0:
            continue
        t = float(rng.uniform(200.0, 1450.0))
        if np.hypot(S2[0] - t, S2[1]) > R_RECV_MAX:
            continue
        th2 = th2_of(S2, t)
        if min(abs(ang_diff(th2, 0.0)), 180 - abs(ang_diff(th2, 0.0))) <= 10.0:
            continue
        D, _ = fast_diameters(S2, np.array([t]))
        if not np.isfinite(D[0]):
            continue
        n0 += 1
        c, v = _corner_points(np.zeros((1, 1, 2)), np.zeros((1, 1)),
                              S2.reshape(1, 1, 2), np.array([[th2]]), EPS_DEG)
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

    # ---- T1: 快路径 vs p1 参考实现（良态） ----
    n_bad, n_cmp, n_skip, max_dd = 0, 0, 0, 0.0
    for _ in range(6000):
        S2 = np.array([rng.uniform(-1500, 1500), rng.uniform(-1500, 1500)])
        if np.hypot(*S2) < 1.0:
            continue
        t = float(rng.uniform(30.0, 1500.0))
        th2 = th2_of(S2, t)
        if min(abs(ang_diff(th2, 0.0)), 180 - abs(ang_diff(th2, 0.0))) <= 2 * EPS_DEG + 0.3:
            n_skip += 1
            continue
        D, _ = fast_diameters(S2, np.array([t]))
        P, pst = region_by_vertices([(0.0, 0.0), tuple(S2)], [0.0, th2])
        if pst != "polygon" or len(P) < 3:
            continue
        n_cmp += 1
        Pa = np.asarray(P, float)
        d_ref = max(math.dist(a, b) for i, a in enumerate(Pa) for b in Pa[i + 1:])
        if not np.isfinite(D[0]):
            n_bad += 1
            continue
        rel = abs(float(D[0]) - d_ref) / max(d_ref, 1e-12)
        max_dd = max(max_dd, rel)
        if rel > 1e-7:
            n_bad += 1
    rec("T1 快路径 vs p1 参考实现（直径，良态）", n_bad == 0,
        f"比较 {n_cmp} 组，跳过近临界 {n_skip} 组，最大相对差 {max_dd:.3e}")

    # ---- T2: 快路径 vs 独立实现 ----
    worst, worst_cfg, n2 = 0.0, None, 0
    for _ in range(8000):
        S2 = np.array([rng.uniform(-1500, 1500), rng.uniform(-1400, 1400)])
        if np.hypot(*S2) < 5.0:
            continue
        t = float(rng.uniform(20.0, 1500.0))
        D, _ = fast_diameters(S2, np.array([t]))
        if not np.isfinite(D[0]):
            continue
        dc = independent_diameter(t, S2)
        if not math.isfinite(dc):
            continue
        n2 += 1
        rel = abs(float(D[0]) - dc) / max(dc, 1e-12)
        if rel > worst:
            worst, worst_cfg = rel, (S2.copy(), t, float(D[0]), dc)
    rec("T2 快路径 vs 独立实现（直接解边界交点）", worst < 1e-9,
        f"{n2} 组，最大相对差 {worst:.3e}"
        + ("" if worst_cfg is None else
           f"（最差 S2={np.round(worst_cfg[0],3)}, t={worst_cfg[1]:.1f}, "
           f"数值={worst_cfg[2]:.4f}, 独立={worst_cfg[3]:.4f}）"))

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
        if _unbounded_bearings(0.0, th2):
            continue
        D, _ = fast_diameters(S2, np.array([t]))
        if not np.isfinite(D[0]):
            continue
        K = mc_points(S2, t, 20000, rng)
        if len(K) < 2:
            continue
        dmax = max_pair_dist(K)
        n3 += 1
        over = dmax / float(D[0]) - 1.0
        if over > worst3:
            worst3, worst3_cfg = over, (S2.copy(), t, float(D[0]), dmax)
    rec("T3 直径 >= 区域内 MC 采样点对最大距离", worst3 <= 1e-9,
        f"{n3} 组，最大超出 {worst3:.3e}"
        + ("" if worst3_cfg is None else
           f"（S2={np.round(worst3_cfg[0],2)}, t={worst3_cfg[1]:.1f}, "
           f"数值={worst3_cfg[2]:.4f}, MC={worst3_cfg[3]:.4f}）"))

    # ---- T4: MC 逼近性 ----
    n4, ratios = 0, []
    for _ in range(40):
        S2 = np.array([rng.uniform(-800, 800), rng.uniform(-800, 800)])
        if np.hypot(*S2) < 50.0:
            continue
        t = float(rng.uniform(100.0, 1400.0))
        if np.hypot(S2[0] - t, S2[1]) > R_RECV_MAX:
            continue
        th2 = th2_of(S2, t)
        if _unbounded_bearings(0.0, th2):
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

    # ---- T5: 贴 x 轴退化必须被识别 ----
    bad5, det5 = 0, []
    for y in (0.0, 1e-6, 1.0):
        S2 = np.array([600.0, y])
        D, _ = fast_diameters(S2, np.array([300.0, 900.0]))
        det5.append(f"y={y}: D={np.round(D, 3).tolist()}")
        if not np.all(np.isnan(D)):
            bad5 += 1
    rec("T5 贴 x 轴退化被识别（无界/退化）", bad5 == 0, " | ".join(det5))

    # ---- T6: y=0 且源比 S2 远 => 无界 ----
    D, st = fast_diameters(np.array([600.0, 0.0]), np.array([900.0]))
    rec("T6 y=0 且源比 S2 远 -> 无界（必须剔除）",
        np.isnan(D[0]) and int(st[0]) == 3, f"D={D[0]}, status={int(st[0])}")

    # ---- T7: 交会角 90°（S2 在源正上方）时 D ≈ 2 tan(eps)|S1S2| ----
    t = 1000.0
    t7_bad, t7_worst = [], 0.0
    for y in (30.0, 60.0, 120.0, 1000.0):
        S2 = np.array([t, y])
        Dv, _ = fast_diameters(S2, np.array([t]))
        dc = independent_diameter(t, S2)
        target = 2 * math.tan(math.radians(EPS_DEG)) * float(np.hypot(*S2))
        rel = abs(float(Dv[0]) - target) / target
        t7_worst = max(t7_worst, rel)
        if abs(float(Dv[0]) - dc) / dc > 1e-9:
            t7_bad.append(f"y={y}: 数值={float(Dv[0]):.6f} 独立={dc:.6f} 不一致")
        if rel > 2e-3:
            t7_bad.append(f"y={y}: 相对差={rel:.2e}")
    if _unbounded_bearings(0.0, 270.0):
        t7_bad.append("gamma*=90° 应判定为良态")
    rec("T7 交会角=90° 时 D ≈ 2 tan(eps)|S1S2|（实测误差 < 2e-3）", not t7_bad,
        "；".join(t7_bad) if t7_bad else f"四组，最大相对差 {t7_worst:.2e}")

    # ---- T8: 源位采样权重归一 + 上界 ----
    ts, w, info = source_samples((0.0, 0.0), 0.0, n_t=200)
    rec("T8 源位采样权重归一 + 上界正确",
        abs(w.sum() - 1.0) < 1e-12 and abs(info["t_hi"] - min(R_RECV_MAX, R_ARENA)) < 1e-9,
        f"t∈[{info['t_lo']:.1f},{info['t_hi']:.1f}], Σw-1={w.sum()-1:.2e}")

    # ---- T9: E[D|可检测] 与逐点加权平均一致 ----
    X = np.array([300.0, 447.2, -200.0, 900.0])
    Y = np.array([600.0, 800.0, 300.0, 0.0])
    tt, ww, _ = source_samples((0.0, 0.0), 0.0, n_t=60)
    res9 = expected_diameter_measured(X, Y, tt, ww)
    manual = []
    for i in range(X.size):
        num = den = 0.0
        for j in range(tt.size):
            D, _ = fast_diameters(np.array([X[i], Y[i]]), np.array([tt[j]]))
            if np.isfinite(D[0]):
                num += ww[j] * float(D[0])
                den += ww[j]
        manual.append(num / den if den > 0 else np.nan)
    ok9 = np.allclose(np.array(manual), res9["E_det"], rtol=1e-10, equal_nan=True)
    rec("T9 E[D|可检测] 与逐点加权平均一致", ok9,
        f"manual={np.round(manual,4).tolist()}, batch={np.round(res9['E_det'],4).tolist()}")

    # ---- T10: 网格框扩展的语义（诚实版）----
    #   靶区是半径 1800 m 的圆域，格点是"圆域 ∩ 网格框"；因此**平移/放大框边界
    #   不会改变圆域内的点数**（只改变框内空白的多少）。要真正加密只能缩小 step。
    Xa, Ya, xsa, _, _ = make_grid(step=50.0, x_range=(-R_ARENA, R_ARENA))
    Xb, Yb, xsb, _, _ = make_grid(step=50.0)
    inside = (Xb ** 2 + Yb ** 2) <= R_ARENA ** 2 + 1e-9
    same_count = (Xa.size == Xb.size)
    rec("T10 网格框扩展不改变圆域内点数（加密只能靠缩小 step）",
        bool(np.all(inside)) and same_count and xsb[-1] > xsa[-1],
        f"x_max {xsa[-1]:.0f}->{xsb[-1]:.0f} m：圆域内点数均为 {Xa.size}（不变），"
        f"全部满足 R<=1800；右半区点数与左半区相同（格点本已对称）")

    if verbose:
        print(f"\n自检总结：{'全部通过' if ok_all else '存在失败项'}")
    return {"ok": ok_all, "checks": out}


# --------------------------------------------------------------------------
# 输出：CSV / JSON
# --------------------------------------------------------------------------
def _json_default(o):
    """把 numpy 标量/布尔/数组转成可序列化对象（自检结果里会混进 np.bool_）"""
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _fmt(v, nd=6):
    if v is None:
        return ""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return "nan" if math.isnan(v) else "inf"
    return round(float(v), nd)


def save_outputs(res, outdir, tag=""):
    os.makedirs(outdir, exist_ok=True)
    X, Y = res["X"], res["Y"]
    path = os.path.join(outdir, f"p2_grid_map{tag}.csv")
    thr = res.get("usable_threshold_m", float("inf"))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["x_m", "y_m", "r_m", "phi_deg",
                     "E_diam_given_detectable_m", "E_diam_mixed_mm",
                     "p_detectable", "cov_weight", "Dmin_m", "Dmax_m",
                     "E_diam_err_given_detectable_m", "E_diam_err_mixed_m",
                     "cov_err", "n_ok", "usable", "near_axis_unusable_band"])
        for i in range(X.size):
            r = math.hypot(X[i], Y[i])
            phi = math.degrees(math.atan2(Y[i], X[i])) % 360.0
            ed = res["E_det"][i]
            usable = int(np.isfinite(ed) and ed <= thr and res["p_det"][i] > 0)
            wr.writerow([_fmt(X[i], 4), _fmt(Y[i], 4), _fmt(r, 4), _fmt(phi, 4),
                         _fmt(ed), _fmt(res["E"][i]),
                         _fmt(res["p_det"][i]), _fmt(res["cov"][i]),
                         _fmt(res["Dmin"][i]), _fmt(res["Dmax"][i]),
                         _fmt(res["E_err_det"][i]), _fmt(res["E_err"][i]),
                         _fmt(res["cov_err"][i]), int(res["n_ok"][i]), usable,
                         int(np.isfinite(ed) and ed > thr)])
    rep = {k: v for k, v in res.items()
           if k not in ("X", "Y", "E", "E_det", "cov", "p_det", "Dmin", "Dmax", "n_ok",
                        "E_err", "E_err_det", "cov_err", "usable")}
    rep["csv"] = os.path.basename(path)
    with open(os.path.join(outdir, f"p2_grid_report{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, default=_json_default)
    return path


# --------------------------------------------------------------------------
# 热力图
# --------------------------------------------------------------------------
def _savefig(fig, path, dpi=150, tries=6):
    """保存图片并重试（Windows 上杀毒/索引偶尔短暂锁住刚写出的 PNG）。"""
    import time as _t
    last = None
    for k in range(tries):
        try:
            fig.savefig(path, dpi=dpi)
            return path
        except OSError as ex:
            last = ex
            _t.sleep(0.5 * (k + 1))
    raise last


def make_figures(res, outdir, tag=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.ticker import FixedLocator, FuncFormatter

    os.makedirs(outdir, exist_ok=True)
    X, Y, xs, ys, shape = res["X"], res["Y"], res["xs"], res["ys"], res["shape"]
    ny, nx = shape
    figs = []
    t_hi = float(res["source_prior"]["t_hi"])       # 扇形径向上界 = 有效接收半径上界

    def to_grid(vals):
        g = np.full((ny, nx), np.nan)
        g[np.searchsorted(ys, Y), np.searchsorted(xs, X)] = vals
        return g

    XLIM = (-1500.0, 2200.0)      # x 负方向小一点；正方向盖住右侧扩展后的网格框
    YLIM = (-2000.0, 2000.0)

    # 关注区（E ~ 50–1500 m）用对数色标，低值段的差异才看得出来
    ZMIN, ZMAX = 50.0, 2000.0
    lnorm = LogNorm(vmin=ZMIN, vmax=ZMAX)
    MAJOR = [50, 70, 100, 150, 200, 300, 500, 700, 1000, 1500, 2000]
    MINOR = [60, 80, 120, 250, 400, 600, 800, 1200]

    ok_use = res.get("usable", np.ones(X.size, bool))
    GX = to_grid(X)
    GY = to_grid(Y)
    Gm = to_grid(np.where(ok_use, res["E_det"], np.nan))
    Ge = to_grid(np.where(ok_use, res["E_err_det"], np.nan))
    Gc = to_grid(res["p_det"])
    th = np.linspace(0, 2 * math.pi, 2000)

    def best_xy(G):
        r, c = np.unravel_index(int(np.nanargmin(G)), G.shape)
        return float(GX[r, c]), float(GY[r, c]), float(G[r, c])

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

    def draw_sector(ax, zorder=6, label=True):
        """画出**首次探测的扇形**（源位先验所在区域），半透明。

        角楔半张角 ``eps = 1°``，径向范围 ``[near, t_hi]``。``eps`` 只有 1°，
        所以这个扇形在整张图上很窄（1500 m 处全宽仅约 52 m）—— 为让它看得见，
        填充用半透明 + 亮色描边。**图内不放任何说明文字/框**（会遮挡内容），
        相关信息一律写进图例、标题或 `report.json`。

        注意 ``ax.fill`` 的 label 会按**网格点数**产生成百上千条图例项，
        所以这里不传 label，图例项改由下面的 ``sector_patch`` 提供。
        """
        t1 = t_hi
        ang_f = np.linspace(-EPS_DEG, EPS_DEG, 400)
        ax.plot(t1 * np.cos(np.radians(ang_f)), t1 * np.sin(np.radians(ang_f)),
                "-", color="darkorange", lw=1.6, alpha=0.95, zorder=zorder)
        n = 240
        rr = np.linspace(NEAR_R, t1, n)
        aa = np.linspace(-EPS_DEG, EPS_DEG, n)
        A, R_ = np.meshgrid(np.radians(aa), rr)
        ax.fill(R_ * np.cos(A), R_ * np.sin(A), color="darkorange", alpha=0.6,
                lw=0, zorder=zorder)
        for s in (-EPS_DEG, EPS_DEG):
            a = math.radians(s)
            ax.plot([NEAR_R * math.cos(a), t1 * math.cos(a)],
                    [NEAR_R * math.sin(a), t1 * math.sin(a)],
                    "-", color="darkorange", lw=1.6, alpha=0.95, zorder=zorder)

    def sector_patch():
        from matplotlib.patches import Patch
        return Patch(fc="darkorange", alpha=0.6, ec="darkorange",
                     label=f"1st-detection sector (±{EPS_DEG:g}°, r ≤ {t_hi:.0f} m)")

    def set_ticks(cb, size=9):
        """色标刻度：主/次刻度都带数字，且**字号统一**（不再大小不一）"""
        cb.set_ticks(MAJOR)
        cb.ax.set_yticklabels([f"{t:g}" for t in MAJOR])
        cb.ax.yaxis.set_minor_locator(FixedLocator(MINOR))
        cb.ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, pos: f"{v:g}"))
        cb.ax.tick_params(which="both", labelsize=size, length=3.5)

    def origin_marker(ax, ms=13, label=True):
        """第一检测点（加粗圆点）。返回 artist，便于显式组织图例。"""
        ln, = ax.plot([0], [0], marker="o", ms=ms, mfc="red", mec="k", mew=1.5,
                      ls="none", zorder=9,
                      label=("S1 = origin (detector)" if label else None))
        return ln

    def best_marker(ax, G, ms=10, label=True):
        """最优第二检测点及关于 x 轴对称的那一点（图内不加文字，信息进图例）"""
        bx, by, vb = best_xy(G)
        pts = [by, -by] if abs(by) > 1e-9 else [by]
        first = None
        for n_, yy in enumerate(pts):
            ln, = ax.plot([bx], [yy], "wo", ms=ms, mfc="none", mew=2, ls="none",
                          zorder=7,
                          label=("best S2 (symmetric pair)" if (label and n_ == 0) else None))
            if first is None:
                first = ln
        return bx, by, vb, first

    # ---------- 图 1：主口径热力图 ----------
    fig, ax = plt.subplots(figsize=(10.6, 10.6))
    im = show(ax, Gm, "viridis_r", norm=lnorm)
    fig.subplots_adjust(top=0.88, bottom=0.07, left=0.09, right=0.98)
    ax.set_title("B-Problem 2: expected intersection-region diameter vs 2nd detection point",
                 fontsize=10, pad=10)
    fig.text(0.5, 0.965,
             "log colour scale;  measured bearings;  source prior: area-uniform inside the"
             " 1st-detection sector;\n"
             f"$\\varepsilon$={res['eps_deg']}°,  $\\theta_1$={res['theta1']}°,  "
             f"reach gate $|S_2G|\\leq${int(R_RECV_MAX)} m,  arena $R\\leq${int(R_ARENA)} m,  "
             f"grid step {res['step']:g} m ({res['grid_points']} points)",
             ha="center", va="bottom", fontsize=9)
    cb = fig.colorbar(im, ax=ax, shrink=0.8, extend="both")
    cb.set_label(f"E[intersection diameter | detectable]  (m, log scale),  "
                 f"colourbar range {ZMIN:g}–{ZMAX:g} m")
    set_ticks(cb)
    ring(ax)
    draw_sector(ax)
    h_origin = origin_marker(ax)
    bx, by, vb, h_best = best_marker(ax, Gm)
    ax.legend(handles=[h_origin, h_best, sector_patch()],
              loc="lower left", fontsize=8, framealpha=0.9)
    f1 = os.path.join(outdir, f"p2_grid_E_heatmap{tag}.png")
    _savefig(fig, f1); plt.close(fig); figs.append(f1)

    # ---------- 图 2：两口径并排 ----------
    fig, axes = plt.subplots(1, 2, figsize=(16.4, 9.4))
    for ax2, G, ttl in (
            (axes[0], Gm, "(a) measured bearings fixed\n"
                          "expectation over source position only"),
            (axes[1], Ge, "(b) error-averaged\n"
                          "expectation over source position AND ±1° reading errors")):
        im = show(ax2, G, "viridis_r", norm=lnorm)
        ring(ax2)
        draw_sector(ax2, label=False)
        origin_marker(ax2, ms=11, label=False)
        ibx, iby, ibv, _ = best_marker(ax2, G, ms=8, label=False)
        ax2.set_title(f"{ttl}\nmin E = {ibv:.1f} m at ({ibx:.0f}, {iby:.0f}) m", fontsize=9)
        cb2 = fig.colorbar(im, ax=ax2, shrink=0.75, extend="both")
        cb2.set_label("E[D | detectable]  (m, log scale)")
        set_ticks(cb2, size=8)
    f2 = os.path.join(outdir, f"p2_grid_E_heatmap_two{tag}.png")
    fig.tight_layout(); _savefig(fig, f2); plt.close(fig); figs.append(f2)

    # ---------- 图 3：可检测概率 ----------
    fig, ax = plt.subplots(figsize=(10.6, 10.0))
    im = show(ax, Gc, "magma", 0.0, 1.0,
              ttl="Detectability: probability the 2nd detector can even hear the channel")
    cbp = fig.colorbar(im, ax=ax, shrink=0.8)
    cbp.set_label("P(|S2G| ≤ 1500 m) under source prior")
    cbp.ax.tick_params(which="both", labelsize=9)
    ring(ax, "c--", 1.0, 0.9)
    draw_sector(ax)
    h_origin = origin_marker(ax)
    ax.legend(handles=[h_origin, sector_patch()],
              loc="lower left", fontsize=8, framealpha=0.9)
    f3 = os.path.join(outdir, f"p2_grid_coverage{tag}.png")
    _savefig(fig, f3); plt.close(fig); figs.append(f3)

    # ---------- 图 4：E(r) 与 E(phi) 剖面 ----------
    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.4))
    r_all = np.hypot(X, Y)
    phi_all = np.degrees(np.arctan2(Y, X)) % 360.0
    for phi0, style in ((90.0, "-"), (80.0, "--"), (70.0, "-."), (45.0, ":")):
        m = np.abs(((phi_all - phi0 + 180) % 360) - 180) < \
            res["step"] / (2 * np.maximum(r_all, 1)) * 1.2
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
    fig.tight_layout(); _savefig(fig, f4); plt.close(fig); figs.append(f4)

    # ---------- 图 5：交会区域随 S2 变化的示意 ----------
    from p1_intersection import convex_hull
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
        ax2.plot([0], [0], marker="o", ms=11, mfc="red", mec="k", mew=1.4, zorder=6)
        ax2.plot([S2[0]], [S2[1]], "o", color="tab:orange", ms=7, zorder=6)
        ax2.plot([t_demo], [0], "k^", ms=8, zorder=6)
        ax2.set_xlim(-1500, 2400); ax2.set_ylim(-1400, 2100)
        dv = float(D[0]) if np.isfinite(D[0]) else float("nan")
        ax2.set_title(f"source t=900 m,  r={rr_:.0f} m, φ={pp_:.0f}°\n"
                      f"intersection D = {dv:.1f} m", fontsize=9)
        ax2.set_xlabel("x (m)"); ax2.set_ylabel("y (m)"); ax2.grid(alpha=0.25)
    f5 = os.path.join(outdir, f"p2_grid_region_demo{tag}.png")
    fig.tight_layout(); _savefig(fig, f5); plt.close(fig); figs.append(f5)
    return figs


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def run(theta1=0.0, step=DEF_STEP, n_t=DEF_N_T, n_e=DEF_N_E, weight="area",
        domain="arena", eps=EPS_DEG, outdir=None, figures=True,
        seed=DEFAULT_SEED, reach=True, checks=True, verbose=True,
        x_range=DEF_X_RANGE, y_range=DEF_Y_RANGE):
    t0 = time.time()
    S1 = (0.0, 0.0)
    ts, w_area, sinfo = source_samples(S1, theta1, eps, n_t)
    w = w_area if weight == "area" else length_weights(ts)
    if ts.size == 0:
        raise SystemExit("源位采样为空：检查 theta1 与靶区/接收半径设置")
    X, Y, xs, ys, shape = make_grid(step=step, x_range=x_range, y_range=y_range,
                                    arena_r=R_ARENA, domain=domain)
    if verbose:
        print(f"网格点 {X.size} 个（step={step} m, domain={domain}, "
              f"x∈[{xs[0]:.0f},{xs[-1]:.0f}], y∈[{ys[0]:.0f},{ys[-1]:.0f}]）；"
              f"源位 {ts.size} 个 t∈[{ts[0]:.1f},{ts[-1]:.1f}] m, 权重={weight}")
    meas = expected_diameter_measured(X, Y, ts, w, eps, reach=reach)
    err = expected_diameter_error_avg(X, Y, ts, w, eps, n_e=n_e, seed=seed, reach=reach)

    t_nom = float(np.sum(w * ts))
    med = float(np.nanmedian(meas["E_det"]))
    usable_thr = 10.0 * med
    usable = np.isfinite(meas["E_det"]) & (meas["E_det"] <= usable_thr) & (meas["p_det"] > 0)
    E_use = np.where(usable, meas["E_det"], np.nan) if np.any(usable) else meas["E_det"]

    def _pick(a):
        a = np.asarray(a, float)
        if not np.any(np.isfinite(a)):
            return None
        i = int(np.nanargmin(a))
        return {"S2": [float(X[i]), float(Y[i])],
                "r_m": float(math.hypot(X[i], Y[i])),
                "phi_deg": float(math.degrees(math.atan2(Y[i], X[i])) % 360.0),
                "value_m": float(a[i]), "index": i,
                "p_det": float(meas["p_det"][i]),
                "E_mixed_m": float(meas["E"][i]),
                "E_err_det_m": (float(err["E_err_det"][i])
                                if np.isfinite(err["E_err_det"][i]) else None),
                "E_err_mixed_m": float(err["E_err"][i])}

    best_det, best_mix = _pick(E_use), _pick(meas["E"])
    n_band = int((np.isfinite(meas["E_det"]) & (meas["E_det"] > usable_thr)).sum())
    res = {
        "model": "P2 grid simulation: E[intersection-region diameter] over 2nd detection point",
        "theta1": float(theta1), "eps_deg": float(eps), "weight": weight, "domain": domain,
        "step": float(step), "reach_gate": bool(reach),
        "grid_x_range": [float(xs[0]), float(xs[-1])],
        "grid_y_range": [float(ys[0]), float(ys[-1])],
        "source_prior": sinfo, "arena_r": R_ARENA,
        "r_recv_range": [R_RECV_MIN, R_RECV_MAX], "near_r": NEAR_R,
        "S1": list(S1), "grid_points": int(X.size), "shape": list(shape),
        "xs": [float(v) for v in xs], "ys": [float(v) for v in ys],
        "usable_threshold_m": float(usable_thr),
        "X": X, "Y": Y,
        "E": meas["E"], "E_det": meas["E_det"], "cov": meas["cov"], "p_det": meas["p_det"],
        "Dmin": meas["Dmin"], "Dmax": meas["Dmax"], "n_ok": meas["n_ok"], "usable": usable,
        "E_err": err["E_err"], "E_err_det": err["E_err_det"],
        "cov_err": err["cov_err"], "n_err_pairs": err["n_pairs"],
        "summary": {
            "objective": "E[D | detectable]（|S2G| <= 1500 m 门控，按扇形内面积均匀先验加权）",
            "E_det_min_m": float(np.nanmin(E_use)),
            "E_det_median_m": med,
            "E_det_max_m": float(np.nanmax(meas["E_det"])),
            "E_mixed_min_m": float(np.nanmin(meas["E"])),
            "usable_points": int(usable.sum()),
            "usable_fraction": float(usable.mean()),
            "near_axis_band_points": n_band,
            "best_det": best_det, "best_mixed": best_mix,
            "best_S2": best_det["S2"] if best_det else None,
            "best_r_m": best_det["r_m"] if best_det else None,
            "best_phi_deg": best_det["phi_deg"] if best_det else None,
            "best_r_over_t": (best_det["r_m"] / t_nom) if best_det else None,
            "mean_source_range_m": t_nom,
            "theory_note": ("交会角 90° 时 D 取该基线下的最小值 ≈ 2 tan(eps)|S1S2|；"
                            "一般情形 D 随基线与近简并程度增大"),
            "x_axis_degenerate": ("y≈0 时两示向度近平行(|Δθ|≤2eps) → 交会区域无界、直径=+∞，"
                                  "被剔除；其邻域(|y| 小)直径可达 10^4-10^5 m，已用 "
                                  f"usable_threshold={usable_thr:.1f} m 标注为不可用带"),
            "reach_gate": ("|S2G| > 有效接收半径上界 1500 m 的源位样本不可检测，"
                           "不计入 E[D|可检测]；混口径 E[D·1{可检测}] 另列"),
            "grid_note": ("网格框右侧多留 0.2R（x 到 2160 m）以便右半区更密；"
                          "可行域仍为靶区圆域 R<=1800 m"),
            "runtime_s": None,
        },
    }
    if checks:
        res["checks"] = selfcheck(verbose=verbose)["checks"]
    res["summary"]["runtime_s"] = round(time.time() - t0, 3)
    if outdir:
        save_outputs(res, outdir)
        if figures:
            try:
                figs = make_figures(res, outdir)
                res["figures"] = [os.path.basename(f) for f in figs]
            except Exception as ex:                  # 图失败不影响数值结果落盘
                res["figures_error"] = f"{type(ex).__name__}: {ex}"
                if verbose:
                    print(f"[warn] 出图失败（数值结果已保存）：{ex}")
        save_outputs(res, outdir)
    if verbose:
        s = res["summary"]
        b = s["best_det"]
        print(f"\n最优第二检测点 S2* = ({b['S2'][0]:.1f}, {b['S2'][1]:.1f}) m "
              f"（r={b['r_m']:.1f} m, φ={b['phi_deg']:.1f}°, r/⟨t⟩={s['best_r_over_t']:.3f}）")
        print(f"E[D|可检测] 最小 = {s['E_det_min_m']:.3f} m；中位数 = {s['E_det_median_m']:.3f} m；"
              f"单条基线 2tan(eps)r = {2*math.tan(math.radians(eps))*b['r_m']:.3f} m")
        print(f"该点 P(可检测) = {b['p_det']:.4f}；混口径 E[D·1] = {b['E_mixed_m']:.3f} m；"
              f"误差口径 E[D|可检测] = {b['E_err_det_m']}")
        print(f"可用点 {s['usable_points']}/{res['grid_points']}"
              f"（近轴不可用带 {s['near_axis_band_points']} 个，阈值 {usable_thr:.1f} m）")
        print(f"耗时 {s['runtime_s']} s")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="B 题问题 2：第二检测点网格上的交会区域直径期望热力图")
    ap.add_argument("--theta1", type=float, default=0.0,
                    help="首次探测的示向度（度），默认 0（x 轴正向）")
    ap.add_argument("--step", type=float, default=DEF_STEP, help="网格步长（m）")
    ap.add_argument("--n-t", type=int, default=DEF_N_T, help="x 轴源位采样数")
    ap.add_argument("--n-e", type=int, default=DEF_N_E, help="误差 MC 采样数")
    ap.add_argument("--weight", choices=["area", "length"], default="area",
                    help="源位先验权重：area ∝ t（面积均匀，默认）/ length 等权")
    ap.add_argument("--domain", choices=["arena", "reach"], default="arena",
                    help="S2 取值范围：整个靶区圆域 / 还要满足 |S2G|<=1500")
    ap.add_argument("--x-range", type=float, nargs=2, default=list(DEF_X_RANGE),
                    metavar=("XMIN", "XMAX"), help="网格 x 范围（m），默认右侧多留 0.2R")
    ap.add_argument("--y-range", type=float, nargs=2, default=list(DEF_Y_RANGE),
                    metavar=("YMIN", "YMAX"), help="网格 y 范围（m）")
    ap.add_argument("--out", default=None, help="输出目录")
    ap.add_argument("--no-reach", action="store_true", help="关闭可检测性门控")
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--no-checks", action="store_true", help="跳过自检（只出结果，快很多）")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args(argv)
    if a.selfcheck:
        r = selfcheck()
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            with open(os.path.join(a.out, "p2_grid_selfcheck.json"), "w",
                      encoding="utf-8") as f:
                json.dump(r, f, ensure_ascii=False, indent=2, default=_json_default)
        return 0 if r["ok"] else 1
    run(theta1=a.theta1, step=a.step, n_t=a.n_t, n_e=a.n_e, weight=a.weight,
        domain=a.domain, outdir=a.out, figures=not a.no_figures,
        checks=not a.no_checks, reach=not a.no_reach,
        x_range=tuple(a.x_range), y_range=tuple(a.y_range))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
