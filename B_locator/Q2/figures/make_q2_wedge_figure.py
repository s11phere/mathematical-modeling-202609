#!/usr/bin/env python3
# =====================================================================
# 问题二插图：两探测束交会与探测域直径的构造（论文图 3）
#
# 输出：B_locator/paper/figures/p2-wedge-geometry.png
#
# 画“怎么来的”：P1 与 P2 的 +-1 deg 探测束如何张开、相交出探测域 ABCD、
# 直径由哪两个顶点（B、D）给出、视线交角 alpha 在源点处如何夹出。
# 图内不加标题（标题由 LaTeX \caption 给出），文字一律英文/数学符号。
#
# 为把几何看清楚，图中两探测束的张角按 TILT 放大、P1P2 连线方向也与真实
# 尺度不同——图题中已注明“示意图、张角放大”。
#
# 运行（仓库根目录）：
#   MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python \
#       B_locator/Q2/figures/make_q2_wedge_figure.py
# =====================================================================
r"""生成论文图 3：两探测束交会与探测域直径的构造。"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib import font_manager, rcParams                      # noqa: E402
from matplotlib.patches import Polygon, Wedge                      # noqa: E402
from matplotlib.lines import Line2D                                # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
Q2 = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(Q2))
FIGDIR = os.path.join(REPO, "B_locator", "paper", "figures")

# 示意构图参数（单位 m；张角放大后仍保持“四边形细长”的实际特征）
P2 = (900.0, 520.0)      # 第二个检测点
S = (1500.0, 0.0)        # 源点（位于 P1 的视线方向 x 轴上）
TILT = 2.0               # 两探测束的半张角（放大示意），真实值 1 deg
R_DRAW = 2600.0          # 画扇形用的半径

C_W1 = "#1565c0"         # P1 的探测束
C_W2 = "#e65100"         # P2 的探测束
C_QUAD = "#c62828"       # 探测域


def setup_fonts() -> None:
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
        "savefig.dpi": 400,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
    })


def ray_intersection(p1, th1, p2, th2):
    """两条射线所在直线的交点（射线方向用角度给出）。"""
    u1 = np.array([math.cos(th1), math.sin(th1)])
    u2 = np.array([math.cos(th2), math.sin(th2)])
    d = np.array(p2) - np.array(p1)
    den = u1[0] * u2[1] - u1[1] * u2[0]
    if abs(den) < 1e-12:
        return None
    s = (d[0] * u2[1] - d[1] * u2[0]) / den
    return np.array(p1) + s * u1


def main():
    setup_fonts()
    os.makedirs(FIGDIR, exist_ok=True)
    alpha = math.radians(TILT)
    psi = math.atan2(S[1] - P2[1], S[0] - P2[0])       # P2 -> S 的方位角

    # 交会四边形顶点：P1 的两条边界射线 × P2 的两条边界射线
    A = ray_intersection((0.0, 0.0), alpha, P2, psi + alpha)
    B = ray_intersection((0.0, 0.0), alpha, P2, psi - alpha)
    C = ray_intersection((0.0, 0.0), -alpha, P2, psi - alpha)
    D = ray_intersection((0.0, 0.0), -alpha, P2, psi + alpha)
    quad = [A, B, C, D]

    fig = plt.figure(figsize=(3.4, 2.6))
    ax = fig.add_axes([0.10, 0.10, 0.88, 0.86])

    # 两个探测束（扇形示意）
    ax.add_patch(Wedge((0.0, 0.0), R_DRAW, -TILT, TILT, facecolor=C_W1,
                       alpha=0.16, edgecolor=C_W1, lw=0.7, zorder=1))
    ax.add_patch(Wedge(P2, R_DRAW, math.degrees(psi) - TILT, math.degrees(psi) + TILT,
                       facecolor=C_W2, alpha=0.16, edgecolor=C_W2, lw=0.7, zorder=1))
    # 探测域
    ax.add_patch(Polygon(np.array(quad), closed=True, facecolor=C_QUAD,
                         alpha=0.35, edgecolor=C_QUAD, lw=0.8, zorder=3))
    # P1P2 连线与直径 BD
    ax.plot([0.0, P2[0]], [0.0, P2[1]], color="0.35", lw=0.7, ls="--", zorder=2)
    ax.plot([B[0], D[0]], [B[1], D[1]], color="k", lw=1.3, zorder=4)
    # 视线 P2 -> S 与 x 轴（P1 的视线）
    ax.plot([P2[0], S[0]], [P2[1], S[1]], color=C_W2, lw=0.7, ls=":", zorder=2)
    ax.plot([0.0, S[0] + 150.0], [0.0, 0.0], color=C_W1, lw=0.7, ls=":", zorder=2)
    # 关键点
    ax.plot([0.0], [0.0], "o", color=C_W1, ms=3.0, zorder=6)
    ax.plot([P2[0]], [P2[1]], "o", color=C_W2, ms=3.0, zorder=6)
    ax.plot([S[0]], [0.0], "^", color="k", ms=3.4, zorder=6)
    for pt in (A, B, C, D):
        ax.plot([pt[0]], [pt[1]], "o", color=C_QUAD, ms=2.2, zorder=6)
    ax.annotate("$P_1$", xy=(0.0, 0.0), xytext=(-30, -95), fontsize=7.5,
                color=C_W1, ha="center")
    ax.annotate("$P_2$", xy=P2, xytext=(P2[0] - 40, P2[1] + 80), fontsize=7.5,
                color=C_W2, ha="center")
    ax.annotate("$S$", xy=S, xytext=(S[0] + 80, -105), fontsize=7.5, ha="center")

    ax.set_xlabel("$x$ (m)")
    ax.set_ylabel("$y$ (m)")
    ax.set_xlim(-260.0, 1880.0)
    ax.set_ylim(-580.0, 780.0)
    ax.tick_params(labelsize=6.5)
    ax.set_aspect("equal", adjustable="box")
    handles = [
        Line2D([], [], color=C_W1, lw=1.0, label="$P_1$ beam ($\\pm\\Delta\\theta/2$)"),
        Line2D([], [], color=C_W2, lw=1.0, label="$P_2$ beam ($\\pm\\Delta\\theta/2$)"),
        Line2D([], [], color=C_QUAD, lw=4.0, alpha=0.5, label="region $ABCD$"),
        Line2D([], [], color="k", lw=1.2, label="diameter $BD$"),
    ]
    ax.legend(handles=handles, loc="lower left", frameon=False, handlelength=1.4,
              borderaxespad=0.2)

    # ---------------- 右上角局部放大：把探测域 ABCD 放大看清 ----------------
    # 视野取 B、D（直径两端）的中点为中心，保证四个顶点与其标注都在框内
    cx = 0.5 * (B[0] + D[0])
    cy = 0.5 * (B[1] + D[1])
    half = 1.35 * max(np.hypot(p[0] - cx, p[1] - cy) for p in (A, B, C, D))
    axi = ax.inset_axes([0.50, 0.545, 0.48, 0.41])
    for p in (A, B, C, D):
        axi.plot([p[0]], [p[1]], "o", color=C_QUAD, ms=3.0, zorder=6)
    axi.add_patch(Polygon(np.array(quad), closed=True, facecolor=C_QUAD,
                          alpha=0.35, edgecolor=C_QUAD, lw=0.8, zorder=3))
    axi.plot([B[0], D[0]], [B[1], D[1]], color="k", lw=1.2, zorder=4)
    axi.plot([0.0, S[0] + 300.0], [0.0, 0.0], color=C_W1, lw=0.6, ls=":", zorder=2)
    axi.plot([P2[0], S[0]], [P2[1], S[1]], color=C_W2, lw=0.6, ls=":", zorder=2)
    axi.plot([S[0]], [0.0], "^", color="k", ms=3.2, zorder=6)
    for pt, nm, dx, dy in ((A, "$A$", -0.22 * half, 0.30 * half),
                           (B, "$B$", 0.06 * half, 0.18 * half),
                           (C, "$C$", -0.02 * half, -0.22 * half),
                           (D, "$D$", -0.14 * half, -0.22 * half)):
        axi.annotate(nm, xy=pt, xytext=(pt[0] + dx, pt[1] + dy), fontsize=6.5,
                     color=C_QUAD, ha="center")
    axi.annotate("$S$", xy=S, xytext=(S[0] + 0.16 * half, -0.20 * half),
                 fontsize=6.5, ha="center")
    axi.annotate("$\\alpha$", xy=(S[0] - 0.42 * half, -0.16 * half), fontsize=7,
                 ha="center")
    axi.set_xlim(cx - half, cx + half)
    axi.set_ylim(cy - half, cy + half)
    axi.tick_params(labelsize=5.5)
    axi.set_aspect("equal", adjustable="box")
    axi.set_title("zoom on region $ABCD$", fontsize=6.0, pad=1.5)

    out = os.path.join(FIGDIR, "p2-wedge-geometry.png")
    fig.savefig(out, dpi=400, bbox_inches="tight")
    plt.close(fig)
    print("[OK] 已写出 %s" % out)


if __name__ == "__main__":
    main()
