#!/usr/bin/env python3
# =====================================================================
# 问题二插图生成
#
# 输出（写入 B_locator/paper/figures/）：
#   p2-expected-diameter.png   双面板：(a) 期望定位区域直径 Dbar(a,b) 热力图
#                              (b) 第二个检测点的候选区域（Dbar 的等值区域）
#
# 模型与数值口径见 ../src/q2_solution.py（四线交会四边形 + 2x_S/x_max^2 加权期望）。
# 色标与 Q2modeling.md 参考图一致：非线性分段映射，重点看 50~100 区间。
# 图内文字一律英文/数学符号（与问题一插图一致，避免中西文混排与缺字风险）。
#
# 运行（仓库根目录）：
#   MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python \
#       B_locator/Q2/figures/make_q2_figures.py
# =====================================================================
r"""生成论文用的问题二插图（热力图 + 候选区域）。"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib import font_manager, rcParams                      # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm  # noqa: E402
from matplotlib.gridspec import GridSpec                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))                  # B_locator/Q2/figures
Q2 = os.path.dirname(HERE)                                         # B_locator/Q2
REPO = os.path.dirname(os.path.dirname(Q2))                        # 仓库根
PAPER = os.path.join(REPO, "B_locator", "paper")
FIGDIR = os.path.join(PAPER, "figures")
SUMMARY = os.path.join(Q2, "src", "results", "q2_summary.json")

sys.path.insert(0, os.path.join(Q2, "src"))
from q2_solution import dbar, quad_vertices, X_MAX, ALPHA          # noqa: E402

# 网格与数值积分精度：nx=96 已足够（Dbar 对 nx 收敛很快，见 q2_summary.json）
NX = 96
A_LO, A_HI, NA = -1550.0, 1550.0, 125    # a 方向范围（m）与分点数
B_LO, B_HI, NB = -1550.0, 1550.0, 125    # b 方向范围（m）与分点数
TOL = 0.20                               # 候选区域取 Dbar <= 1.20 Dbar_min
X_S_DEMO = 1100.0                        # 右图示意用的源点横坐标（m）


def setup_fonts() -> None:
    """图内只用拉丁/数学符号；字体与正文一致（Times + Computer Modern）。"""
    for name in ("Times New Roman", "Nimbus Roman", "Liberation Serif", "DejaVu Serif"):
        try:
            font_manager.findfont(font_manager.FontProperties(family=name),
                                  fallback_to_default=False)
            serif = name
            break
        except Exception:
            continue
    else:
        serif = "DejaVu Serif"
    rcParams.update({
        "font.family": "serif",
        "font.serif": [serif],
        "mathtext.fontset": "cm",
        "font.size": 8,
        "axes.linewidth": 0.6,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 6.8,
        "lines.linewidth": 1.0,
        "savefig.dpi": 400,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
    })


# ---------------------------------------------------------------------
# 色标（与参考图一致）：非线性分段映射
# ---------------------------------------------------------------------
def t_val(d):
    d = np.asarray(d, dtype=float)
    t = np.where(d <= 50.0, 0.0, 0.0)
    m1 = (d > 50.0) & (d <= 100.0)
    t = np.where(m1, 0.65 * (d - 50.0) / 50.0, t)
    m2 = (d > 100.0) & (d <= 1000.0)
    t = np.where(m2, 0.65 + 0.35 * (d - 100.0) / 900.0, t)
    return np.where(d > 1000.0, 1.0, t)


def color_table():
    stops = [(0.00, (0.00, 0.20, 0.80)), (0.15, (0.00, 1.00, 1.00)),
             (0.35, (0.00, 1.00, 0.00)), (0.50, (1.00, 1.00, 0.00)),
             (0.65, (1.00, 0.65, 0.00)), (0.85, (1.00, 0.00, 0.00)),
             (1.00, (0.50, 0.00, 0.00))]
    cmap = LinearSegmentedColormap.from_list("q2diam", stops)
    cmap.set_bad("white")
    return cmap


# ---------------------------------------------------------------------
# 数值网格
# ---------------------------------------------------------------------
def compute_grid():
    """整个 (a,b) 上的 Dbar；|S2|>x_max 或近共线处为 NaN（不参与成像）。"""
    a_axis = np.linspace(A_LO, A_HI, NA)
    b_axis = np.linspace(B_LO, B_HI, NB)
    z = np.full((NB, NA), np.nan)
    for j, b in enumerate(b_axis):
        for i, a in enumerate(a_axis):
            if math.hypot(a, b) > X_MAX:
                continue
            v = dbar(float(a), float(b), NX)
            z[j, i] = v if v < 1000.0 else np.nan
        if j % 25 == 0:
            print("      ... b = %7.1f m" % b)
    return a_axis, b_axis, z


def candidate_boundary(d_min, tol=TOL, n_ang=240, r_lo=150.0):
    """候选区域边界：对每个方位角求满足 Dbar <= (1+tol) Dbar_min 的整段半径区间。

    区间的两端都用二分求解（候选区域是绕最优点的闭合区域，一般形如 [r1, r2]）。
    返回 (r1 曲线, r2 曲线)，各为 Nx2 数组；该方向上无可行区间的点被剔除。
    """
    def f(r, t):
        return dbar(r * math.cos(t), r * math.sin(t), 160)

    inner, outer = [], []
    for ang in np.linspace(1.0, 89.0, n_ang):
        t = math.radians(ang)
        thresh = d_min * (1.0 + tol)
        # 由内向外粗扫，找第一个满足条件的半径
        grid = np.arange(r_lo, X_MAX + 1.0, 25.0)
        vals = np.array([f(float(r), t) for r in grid])
        ok = vals <= thresh
        if not ok.any():
            continue
        i0 = int(np.argmax(ok))
        # 内端点：在 [grid[i0-1], grid[i0]] 内二分
        r_in = grid[i0]
        if i0 > 0:
            a_, b_ = grid[i0 - 1], grid[i0]
            for _ in range(24):
                m = 0.5 * (a_ + b_)
                if f(m, t) <= thresh:
                    b_ = m
                else:
                    a_ = m
            r_in = b_
        # 外端点：在 [grid[i0], X_MAX] 内二分（若整段都满足则取 x_max）
        r_out = X_MAX
        if not ok[-1]:
            a_, b_ = grid[int(np.argmax(~ok[i0:])) + i0 - 1], grid[int(np.argmax(~ok[i0:])) + i0]
            for _ in range(24):
                m = 0.5 * (a_ + b_)
                if f(m, t) <= thresh:
                    a_ = m
                else:
                    b_ = m
            r_out = a_
        inner.append((r_in * math.cos(t), r_in * math.sin(t)))
        outer.append((r_out * math.cos(t), r_out * math.sin(t)))
    return (np.array(inner) if inner else np.zeros((0, 2)),
            np.array(outer) if outer else np.zeros((0, 2)))


# ---------------------------------------------------------------------
# 绘图
# ---------------------------------------------------------------------
def draw_panel_a(ax, a_axis, b_axis, z, d_min):
    cmap = color_table()
    tg = t_val(np.nan_to_num(z, nan=1000.0))
    tm = np.where(np.isfinite(z), tg, np.nan)
    im = ax.pcolormesh(a_axis, b_axis, np.ma.masked_invalid(tm), cmap=cmap,
                       norm=BoundaryNorm(np.linspace(0, 1, 257), 256),
                       shading="nearest", rasterized=True)
    levels = list(np.arange(50.0, 100.0, 5.0)) + [100.0, 200.0, 500.0, 1000.0]
    with np.errstate(invalid="ignore"):
        cs = ax.contour(a_axis, b_axis, z, levels=levels, colors="k",
                        linewidths=0.35, linestyles="--", alpha=0.45)
        ax.clabel(cs, levels=[60.0, 80.0, 100.0], fmt="%d", fontsize=6.0)
    ax.axhline(0.0, color="k", lw=0.7)
    ax.axvline(0.0, color="k", lw=0.7)
    ax.plot([0.0], [0.0], "o", color="red", ms=2.8)
    ax.annotate("$S_1(0,0)$", xy=(0.0, 0.0), xytext=(120, -230), fontsize=7,
                color="red", arrowprops=dict(arrowstyle="-", color="red", lw=0.5))
    ax.plot([d_min["a"]], [d_min["b"]], "o", color="k", ms=2.8)
    ax.annotate("$(a^*,b^*)$", xy=(d_min["a"], d_min["b"]), xytext=(430, 1000),
                fontsize=7, arrowprops=dict(arrowstyle="->", color="k", lw=0.5))
    ax.text(-1500, 1470,
            "white: $|S_2S_1|>x_{max}$ or near-collinear\n"
            "blue: optimal band  $\\bar D<60$ m",
            fontsize=6.2, va="top", ha="left", color="0.25")
    ax.set_xlabel("$a$ (m)")
    ax.set_ylabel("$b$ (m)")
    ax.set_xlim(A_LO, A_HI)
    ax.set_ylim(B_LO, B_HI)
    ax.set_aspect("equal", adjustable="box")
    cbar = ax.figure.colorbar(im, ax=ax, fraction=0.045, pad=0.02,
                              ticks=[0.0, 0.13, 0.26, 0.39, 0.52, 0.65, 0.76, 0.88, 1.0])
    cbar.ax.set_yticklabels(["57", "60", "70", "80", "90", "100", "300", "600",
                             "1000+"], fontsize=6.5)
    cbar.ax.minorticks_off()
    cbar.set_label("$\\bar D$ (m)", fontsize=7.5)


def _band(inner, outer):
    """由内、外两条边界曲线拼成闭合环形区域顶点。"""
    if len(inner) == 0 or len(outer) == 0:
        return np.zeros((0, 2))
    return np.vstack([outer, [[0.0, 0.0]], inner[::-1], [outer[0]]])


def draw_panel_b(ax, d_min, cand, tight):
    inner, outer = cand
    t_in, t_out = tight
    # 可行域（|S2|<=x_max）
    tt = np.linspace(-math.pi / 2, math.pi / 2, 400)
    ax.fill_between(X_MAX * np.cos(tt), X_MAX * np.sin(tt), color="0.94",
                    edgecolor="0.7", lw=0.5, zorder=1)
    ax.plot(X_MAX * np.cos(tt), X_MAX * np.sin(tt), color="0.55", lw=0.6,
            ls="--", zorder=2)
    ax.text(1400, 300, "$|S_2S_1|=x_{max}$", fontsize=6.5, rotation=90,
            color="0.35", va="bottom", ha="center")
    ax.axhline(0.0, color="k", lw=0.7, zorder=2)
    # 最优带（5%）与候选区域（20%）
    band5 = _band(t_in, t_out)
    if len(band5):
        ax.fill(band5[:, 0], band5[:, 1], color="#0d47a1", alpha=0.30, lw=0.0,
                zorder=3)
        ax.plot(t_in[:, 0], t_in[:, 1], color="#0d47a1", lw=0.6, zorder=4)
        ax.plot(t_out[:, 0], t_out[:, 1], color="#0d47a1", lw=0.6, zorder=4)
    band20 = _band(inner, outer)
    if len(band20):
        ax.fill(band20[:, 0], band20[:, 1], color="#1976d2", alpha=0.14, lw=0.0,
                zorder=3)
        ax.plot(outer[:, 0], outer[:, 1], color="#1976d2", lw=0.8, zorder=4)
        ax.plot(inner[:, 0], inner[:, 1], color="#1976d2", lw=0.8, zorder=4)
    # 示意：S1 的视线、源点 T 与最优 S2
    ax.plot([0.0, X_S_DEMO], [0.0, 0.0], color="red", lw=0.8, ls="-.", zorder=5)
    ax.plot([X_S_DEMO], [0.0], "s", color="red", ms=3.0, zorder=6)
    ax.annotate("$T$", xy=(X_S_DEMO, 0.0), xytext=(X_S_DEMO - 190, 80),
                fontsize=7, color="red")
    ax.annotate("$\\psi_1$", xy=(0.45 * X_S_DEMO, 0.0), xytext=(560, 70),
                fontsize=7, color="red")
    ax.plot([d_min["a"]], [d_min["b"]], "o", color="k", ms=3.0, zorder=6)
    ax.annotate("$(a^*,b^*)$", xy=(d_min["a"], d_min["b"]), xytext=(700, 1090),
                fontsize=7, arrowprops=dict(arrowstyle="->", color="k", lw=0.5))
    ax.plot([0.0], [0.0], "o", color="red", ms=2.8, zorder=6)
    ax.annotate("$S_1$", xy=(0.0, 0.0), xytext=(60, -150), fontsize=7, color="red")
    ax.text(60, 1440, "dark: $\\bar D\\leq1.05\\,\\bar D_{\\min}$", fontsize=6.5,
            color="#0d47a1")
    ax.text(60, 1300, "light: $\\bar D\\leq1.20\\,\\bar D_{\\min}$", fontsize=6.5,
            color="#1976d2")
    ax.set_xlabel("$a$ (m)")
    ax.set_ylabel("$b$ (m)")
    ax.set_xlim(-120.0, X_MAX * 1.06)
    ax.set_ylim(-120.0, X_MAX * 1.10)
    ax.set_aspect("equal", adjustable="box")


def main():
    setup_fonts()
    if not os.path.exists(SUMMARY):
        raise SystemExit("缺少 %s，请先运行 src/q2_solution.py" % SUMMARY)
    with open(SUMMARY, encoding="utf-8") as fh:
        d_min = json.load(fh)["optimum"]
    os.makedirs(FIGDIR, exist_ok=True)

    print("[1/3] 计算 Dbar(a,b) 网格（%d x %d，nx=%d）…" % (NA, NB, NX))
    a_axis, b_axis, z = compute_grid()
    print("      有效网格点 %d，最小 Dbar = %.3f m"
          % (int(np.isfinite(z).sum()), np.nanmin(z)))

    print("[2/3] 二分求候选区域与最优带边界 …")
    cand = candidate_boundary(d_min["dbar_min"], tol=TOL)
    tight = candidate_boundary(d_min["dbar_min"], tol=0.05, n_ang=160)
    for tag, (inner, outer) in (("candidate(20%)", cand), ("tight(5%)", tight)):
        if len(inner) == 0:
            print("      %s: 无边界点" % tag)
            continue
        for nm, curve in (("inner", inner), ("outer", outer)):
            r = np.hypot(curve[:, 0], curve[:, 1])
            ang = np.degrees(np.arctan2(curve[:, 1], curve[:, 0]))
            print("      %s %s: beta in [%.1f, %.1f] deg, R in [%.0f, %.0f] m"
                  % (tag, nm, ang.min(), ang.max(), r.min(), r.max()))

    print("[3/3] 绘图 …")
    fig = plt.figure(figsize=(7.3, 4.0))
    gs = GridSpec(1, 2, width_ratios=[1.32, 1.0], wspace=0.30, figure=fig)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    draw_panel_a(ax_a, a_axis, b_axis, z, d_min)
    draw_panel_b(ax_b, d_min, cand, tight)
    out = os.path.join(FIGDIR, "p2-expected-diameter.png")
    fig.savefig(out, dpi=400, bbox_inches="tight")
    plt.close(fig)
    print("[OK] 已写出 %s" % out)


if __name__ == "__main__":
    main()
