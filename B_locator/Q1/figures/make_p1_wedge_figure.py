# -*- coding: utf-8 -*-
"""B 题问题一配图：两个角楔如何交出定位区域，直径是怎么量的，以及覆盖为什么会失败。

输出
----
B_locator/paper/figures/p1-wedge-intersection.png
    (a) 两个角楔的交会（示意构图）：两条边界射线夹出角楔，两楔交出四边形区域 R；
        最远顶点对 A、B 连成直径，M 为其中点，圆半径 D/2 由 MA、MB 两条虚线给出；
    (b) 覆盖判据的失效实例（真实算例 A2）：直径圆圆心固定在 M，而区域中距 M 最远的
        顶点 P 落在圆外——|PM| = 10.29 m > D/2 = 9.31 m，故该圆不能覆盖区域。

(a) 的示意图说明
----------------
两个角楔的交集是"细长条"：其横向尺度由两检测点的间隙决定，纵向尺度为 d·tan ε。按题面
真实数据（ε = 1°、d 数百米）画出来只是一根针，看不出交会这一步。故 (a) 取一组示意
几何（检测点相距 900 m、两站点分居两侧、半张角 5°）把交会关系画清楚，并在图中标出
顶点、直径、圆心与半径；真实的 ε 与量级由 (b) 与 5.1.4 节表格给出。

运行：python make_p1_wedge_figure.py
"""
from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402
import numpy as np                                                # noqa: E402
from matplotlib import font_manager, rcParams                     # noqa: E402
from matplotlib.patches import Polygon as MplPolygon, Wedge, Arc  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
from p1_solution import analyse_case, CASES                       # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "..", "paper", "figures"))
SIMSUN = os.path.normpath(os.path.join(HERE, "..", "..", "paper", "fonts", "simsun.ttc"))

# ---- 示意构图 (a)：两检测点分居源的两侧，各给一个角楔 ----
S1 = (0.0, 0.0)
S2 = (0.0, 900.0)
Q = [(-60.0, 350.0), (100.0, 350.0), (100.0, 550.0), (-60.0, 550.0)]   # 交集四边形（顺时针）
EPS_FIG = 5.0        # 示意半张角（度）；真实值为 1°

C_REGION = "#c62828"
C_CIRCLE = "#1565c0"
C_DET = "#1b5e20"
C_WEDGE = "#78909c"
C_BAD = "#e65100"


def setup_fonts():
    prop = font_manager.FontProperties(fname=SIMSUN)
    font_manager.fontManager.addfont(SIMSUN)
    fam = prop.get_name()
    rcParams["font.family"] = "serif"
    rcParams["font.serif"] = [fam, "Times New Roman", "Nimbus Roman", "DejaVu Serif"]
    rcParams["mathtext.fontset"] = "cm"
    rcParams.update({
        "font.size": 7.0, "axes.labelsize": 7.0, "xtick.labelsize": 6.2,
        "ytick.labelsize": 6.2, "axes.linewidth": 0.6, "lines.linewidth": 1.0,
        "savefig.dpi": 400, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })


def circumcircle(P):
    """四点共圆时返回 (圆心, 半径)；此处为构造保证。"""
    A = np.array(P[0], float)
    B = np.array(P[1], float)
    C = np.array(P[2], float)
    d = 2.0 * (A[0] * (B[1] - C[1]) + B[0] * (C[1] - A[1]) + C[0] * (A[1] - B[1]))
    ux = ((A @ A) * (B[1] - C[1]) + (B @ B) * (C[1] - A[1]) + (C @ C) * (A[1] - B[1])) / d
    uy = ((A @ A) * (C[0] - B[0]) + (B @ B) * (A[0] - C[0]) + (C @ C) * (B[0] - A[0])) / d
    M = np.array([ux, uy])
    return M, np.linalg.norm(A - M)


def panel_a(ax):
    """(a) 两角楔交会 + 直径测量（示意构图）。"""
    P = np.array(Q)
    M, rad = circumcircle(Q)

    # 角楔扇形（从检测点出发，只画到视野附近）
    for S, ang in ((S1, 90.0), (S2, 270.0)):
        ax.add_patch(Wedge(S, 720.0, ang - EPS_FIG, ang + EPS_FIG, facecolor=C_WEDGE,
                           alpha=0.22, edgecolor="none", zorder=1))
        for s in (-1.0, 1.0):
            a = np.radians(ang + s * EPS_FIG)
            ax.plot([S[0], S[0] + 720.0 * np.cos(a)], [S[1], S[1] + 720.0 * np.sin(a)],
                    color=C_WEDGE, lw=0.7, ls=(0, (4, 2)), zorder=2)
        ax.plot(*S, marker="^", color=C_DET, ms=4.2, zorder=8)
        ax.add_patch(Arc(S, 150, 150, theta1=min(ang - EPS_FIG, ang + EPS_FIG),
                         theta2=max(ang - EPS_FIG, ang + EPS_FIG),
                         color=C_DET, lw=0.6, zorder=3))

    # 定位区域
    ax.add_patch(MplPolygon(P, closed=True, facecolor=C_REGION, alpha=0.25,
                            edgecolor="none", zorder=4))
    ax.plot(np.append(P[:, 0], P[0, 0]), np.append(P[:, 1], P[0, 1]),
            color=C_REGION, lw=1.2, zorder=5)

    # 直径圆 + 两条半径
    t = np.linspace(0, 2 * np.pi, 600)
    ax.plot(M[0] + rad * np.cos(t), M[1] + rad * np.sin(t), color=C_CIRCLE, lw=1.0, zorder=3)
    A, B = P[3], P[1]                       # 最远顶点对：左上 / 右下
    for Pt in (A, B):
        ax.plot(*zip(M, Pt), color=C_CIRCLE, lw=0.8, ls=(0, (2, 2)), zorder=6)
        ax.plot(*Pt, "o", ms=3.0, mfc="w", mec="k", mew=0.8, zorder=8)
    for Pt in P:
        ax.plot(*Pt, "o", ms=2.4, mfc="w", mec=C_REGION, mew=0.7, zorder=7)
    ax.plot(*zip(A, B), color="k", lw=1.2, zorder=7)
    ax.plot(*M, marker="+", color="k", ms=5.0, mew=1.0, zorder=8)

    # 标注
    ax.annotate("$S_1$", xy=S1, xytext=(6, -10), fontsize=7.5, color=C_DET, zorder=9)
    ax.annotate("$S_2$", xy=S2, xytext=(6, 6), fontsize=7.5, color=C_DET, zorder=9)
    ax.annotate("$\\varepsilon$", xy=S1, xytext=(52, 8), fontsize=7.0, color=C_DET, zorder=9)
    ax.annotate("$\\varepsilon$", xy=S2, xytext=(52, -22), fontsize=7.0, color=C_DET, zorder=9)
    ax.annotate("$A$", xy=A, xytext=(A[0] - 14, A[1] - 2), fontsize=7.5, ha="right",
                va="center", zorder=9)
    ax.annotate("$B$", xy=B, xytext=(B[0] + 14, B[1] + 2), fontsize=7.5, ha="left",
                va="center", zorder=9)
    ax.annotate("$M$", xy=M, xytext=(M[0] + 6, M[1] + 14), fontsize=7.5, zorder=9)
    ax.annotate("$D=|AB|$", xy=(0.5 * (A + B)), xytext=(M[0] - 190, M[1] - 40),
                fontsize=7.0, ha="left", va="center",
                arrowprops=dict(arrowstyle="->", lw=0.5, color="k"), zorder=9)
    ax.annotate("$D/2$", xy=0.5 * (M + A), xytext=(M[0] - 186, M[1] + 46), fontsize=7.0,
                ha="left", va="center",
                arrowprops=dict(arrowstyle="->", lw=0.5, color=C_CIRCLE), zorder=9)
    ax.annotate("$\\mathcal{R}$", xy=P.mean(axis=0), fontsize=11, color=C_REGION,
                ha="center", va="center", zorder=9)

    ax.set_aspect("equal")
    ax.set_xlim(-235, 285)
    ax.set_ylim(215, 685)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor("#b0bec5")
    ax.set_title("(a) 两角楔交出定位区域，直径由最远顶点对 $A,B$ 给出", fontsize=7.2)


def panel_b(ax):
    """(b) 真实算例 A2：直径圆无法覆盖区域，越界顶点为 P。"""
    r = analyse_case(CASES["A2"]["det"], 1.0)
    V = np.array(r["vertices"])
    A, B = np.array(r["diameter_endpoints"])
    M = np.array(r["circle_center"])
    rad = r["circle_radius_m"]
    P = V[int(np.argmax(np.linalg.norm(V - M, axis=1)))]

    t = np.linspace(0, 2 * np.pi, 600)
    ax.plot(M[0] + rad * np.cos(t), M[1] + rad * np.sin(t), color=C_CIRCLE, lw=1.0, zorder=3)
    ax.add_patch(MplPolygon(V, closed=True, facecolor=C_REGION, alpha=0.25,
                            edgecolor="none", zorder=4))
    ax.plot(np.append(V[:, 0], V[0, 0]), np.append(V[:, 1], V[0, 1]),
            color=C_REGION, lw=1.2, zorder=5)
    ax.plot(*zip(A, B), color="k", lw=1.2, zorder=7)
    for Pt in (A, B):
        ax.plot(*zip(M, Pt), color=C_CIRCLE, lw=0.8, ls=(0, (2, 2)), zorder=6)
        ax.plot(*Pt, "o", ms=3.0, mfc="w", mec="k", mew=0.8, zorder=8)
    ax.plot(*V.T, "o", ms=2.4, mfc="w", mec=C_REGION, mew=0.7, zorder=7)
    ax.plot(*M, marker="+", color="k", ms=5.0, mew=1.0, zorder=8)
    ax.plot(*zip(M, P), color=C_BAD, lw=0.9, ls=(0, (3, 2)), zorder=7)
    ax.plot(*P, "o", ms=4.6, mfc="none", mec=C_BAD, mew=1.0, zorder=9)

    ax.annotate("$M$", xy=M, xytext=(M[0] + 0.6, M[1] + 0.7), fontsize=7.5, zorder=9)
    ax.annotate("$P$", xy=P, xytext=(P[0] - 1.9, P[1] - 1.3), fontsize=7.5, color=C_BAD,
                zorder=9)
    ax.annotate("$|PM|=%.2f\\ \\mathrm{m}$" % np.linalg.norm(P - M),
                xy=0.5 * (M + P), xytext=(M[0] - 5.4, M[1] - 5.4), fontsize=6.8,
                color=C_BAD, ha="center", va="center",
                arrowprops=dict(arrowstyle="->", lw=0.5, color=C_BAD), zorder=9)
    ax.annotate("$D/2=%.2f\\ \\mathrm{m}$" % rad, xy=0.5 * (M + A),
                xytext=(A[0] - 0.8, A[1] + 4.2), fontsize=6.8, color=C_CIRCLE, ha="left",
                va="center", arrowprops=dict(arrowstyle="->", lw=0.5, color=C_CIRCLE),
                zorder=9)

    ax.set_aspect("equal")
    ax.set_xlim(V[:, 0].min() - 4.6, V[:, 0].max() + 4.6)
    ax.set_ylim(V[:, 1].min() - 4.2, V[:, 1].max() + 5.0)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor("#b0bec5")
    ax.set_title("(b) 真实算例 $A_2$：$P$ 在直径圆外，该圆不能覆盖 $\\mathcal{R}$", fontsize=7.2)


def main():
    setup_fonts()
    fig = plt.figure(figsize=(6.7, 2.9))
    ax1 = fig.add_axes([0.02, 0.02, 0.56, 0.88])
    ax2 = fig.add_axes([0.645, 0.02, 0.35, 0.88])
    panel_a(ax1)
    panel_b(ax2)
    path = os.path.join(OUT, "p1-wedge-intersection.png")
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path)

    # 自检：示意构图的四个顶点是否共圆、直径是否为最远点对
    P = np.array(Q)
    M, rad = circumcircle(Q)
    dists = [float(np.linalg.norm(p - M)) for p in P]
    D = max(float(np.linalg.norm(P[i] - P[j])) for i in range(4) for j in range(i + 1, 4))
    print("[check] (a) 顶点到 M 的距离 %s，R=%.3f，D=%.3f，D/2=%.3f"
          % (["%.3f" % d for d in dists], rad, D, D / 2))
    assert max(dists) - min(dists) < 1e-6, "四点不共圆"
    assert abs(D - 2 * rad) < 1e-6, "直径不等于 2R"
    print("[check] (a) 四个顶点共圆、直径 = 2R ✓")


if __name__ == "__main__":
    main()
