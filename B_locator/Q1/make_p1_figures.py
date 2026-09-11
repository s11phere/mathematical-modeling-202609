# -*- coding: utf-8 -*-
"""生成论文问题一的插图（PNG, 400 dpi, 单栏宽）。

输出目录：B_locator/paper/figures/
    p1-region-bounded.png    定位区域、顶点、直径端点与直径圆
    p1-coverage-contrast.png 直径圆覆盖成立 / 失败对照（左 A1，右 A2）
    p1-unbounded.png         无界情形：两示向度近似同向，区域是无界条带

说明：图内文字一律使用英文/数学符号，避免中西文字体混排，同时规避 XeLaTeX 缺字风险。
字体与正文保持一致：拉丁用 Times New Roman，数学用 Computer Modern（正文公式同款）。
运行：python make_p1_figures.py
"""
from __future__ import annotations

import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
from matplotlib import font_manager      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# 求解代码与本脚本同在扁平的 Q1/ 目录下，直接按同目录导入
from p1_intersection import analyse, region_is_unbounded, BEARING_ERR   # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, os.pardir, "paper", "figures"))


def load_cases(case_dir=HERE):
    """读入扁平的 Q1/ 下的算例：p1_case01..05.csv -> A1..A5 -> [(x, y, theta), ...]"""
    cases = {}
    for k in range(1, 6):
        with open(os.path.join(case_dir, "p1_case%02d.csv" % k), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        cases["A%d" % k] = [(float(r["x_m"]), float(r["y_m"]), float(r["svd_deg"]))
                            for r in rows]
    return cases


CASES = load_cases()


def _pick_serif():
    """正文拉丁字体是 Times New Roman，图内取同一字体（缺字则依次回退）。"""
    for name in ("Times New Roman", "Nimbus Roman", "Liberation Serif", "DejaVu Serif"):
        try:
            font_manager.findfont(font_manager.FontProperties(family=name),
                                  fallback_to_default=False)
            return name
        except Exception:
            continue
    return "DejaVu Serif"


SERIF = _pick_serif()

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": [SERIF],
    "mathtext.fontset": "cm",            # 与正文 LaTeX 公式一致
    "font.size": 8,
    "axes.linewidth": 0.6,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "lines.linewidth": 1.0,
    "savefig.dpi": 400,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

C_REGION = "#c62828"      # 定位区域
C_CIRCLE = "#1565c0"      # 直径圆
C_BAD = "#e65100"         # 落在直径圆外的顶点
C_DET = "#2e7d32"         # 检测点
C_WEDGE = "#90a4ae"       # 角楔边界


def _prep_case(key):
    """返回 (结果, 闭合顶点序列, 直径端点, 圆心, 半径, 最大顶点距, 是否覆盖)。"""
    det = CASES[key]
    r = analyse([(x, y) for (x, y, _) in det], [th for (_, _, th) in det])
    assert r["status"] == "bounded", r["status"]
    # 面板契约：图 2 的 (a) 必须是覆盖成立、图 2/备选图的 (b) 必须是覆盖失败
    assert r["diameter_circle_covers"] == (key == "A1"), \
        "面板契约被破坏：%s cover=%s" % (key, r["diameter_circle_covers"])
    V = np.array(r["vertices"] + [r["vertices"][0]])
    A, B = np.array(r["diameter_endpoints"])
    M, rad = np.array(r["circle_center"]), r["circle_radius_m"]
    return r, V, A, B, M, rad, r["max_vertex_dist_m"], r["diameter_circle_covers"]


def fig_region_bounded():
    """图 2：定位区域、区域顶点、直径端点与以直径为直径的圆。"""
    r, V, A, B, M, rad, maxvtx, cov = _prep_case("A1")
    fig, ax = plt.subplots(figsize=(3.15, 2.75))

    x0, y0 = M
    span = 1.55 * rad
    for (x, y, th) in CASES["A1"]:      # 角楔边界（裁剪到视野内）
        for s in (-1.0, 1.0):
            a = np.radians(th + s * BEARING_ERR)
            t = np.linspace(0.0, 1.0, 300)
            # 由检测点向该方向延伸，只画落在视野内的部分
            L = 4.0 * span
            xs, ys = x + L * t * np.cos(a), y + L * t * np.sin(a)
            vis = (np.abs(xs - x0) < span) & (np.abs(ys - y0) < span)
            if vis.any():
                ax.plot(xs[vis], ys[vis], color=C_WEDGE, lw=0.6, ls=(0, (4, 2)), zorder=1)

    th = np.linspace(0, 2 * np.pi, 400)
    ax.plot(M[0] + rad * np.cos(th), M[1] + rad * np.sin(th),
            color=C_CIRCLE, lw=1.0, zorder=3, label="circle with diameter $AB$")
    ax.fill(V[:, 0], V[:, 1], color=C_REGION, alpha=0.22, zorder=2,
            label="locating region $\\mathcal{R}$")
    ax.plot(V[:, 0], V[:, 1], color=C_REGION, lw=1.1, zorder=4)

    ax.plot([A[0], B[0]], [A[1], B[1]], color="k", lw=1.0, zorder=5,
            label="diameter $D=|AB|$")
    ax.plot([A[0], B[0]], [A[1], B[1]], "o", ms=3.0, mfc="w", mec="k", mew=0.8, zorder=6)
    ax.plot(*M, marker="+", color="k", ms=5, mew=0.9, zorder=6)
    for (x, y, th_) in CASES["A1"]:
        ax.plot(x, y, marker="^", color=C_DET, ms=3.6, zorder=6)

    D = r["diameter_m"]
    ax.annotate("$D=%.2f$ m" % D, xy=(0.5 * (A[0] + B[0]), 0.5 * (A[1] + B[1])),
                xytext=(x0 - 1.00 * span, y0 - 0.08 * span), fontsize=7, ha="left",
                arrowprops=dict(arrowstyle="->", lw=0.5, color="k"))
    ax.annotate("$M$", xy=M, xytext=(M[0] + 0.15 * span, M[1] - 0.10 * span),
                fontsize=8)
    ax.annotate("$A$", xy=A, xytext=(A[0] - 0.10 * span, A[1] + 0.10 * span), fontsize=8)
    ax.annotate("$B$", xy=B, xytext=(B[0] - 0.46 * span, B[1] + 0.10 * span), fontsize=8)
    ax.annotate("detecting points\nand $\\pm\\varepsilon$ wedges",
                xy=CASES["A1"][3][:2], xytext=(x0 - 1.00 * span, y0 + 0.80 * span),
                fontsize=6.4, color="#37474f",
                arrowprops=dict(arrowstyle="->", lw=0.5, color="#37474f"))

    ax.set_aspect("equal")
    ax.set_xlim(x0 - 1.28 * span, x0 + span)
    ax.set_ylim(y0 - span, y0 + span)
    ax.set_xlabel("$x$ / m")
    ax.set_ylabel("$y$ / m")
    ax.legend(loc="lower left", frameon=False, handlelength=1.6, borderpad=0.1,
              bbox_to_anchor=(-0.02, -0.02))
    title = "region $\\mathcal{R}$ is bounded here (case A1)"
    path = os.path.join(OUT, "p1-region-bounded.png")
    ax.set_title(title, fontsize=7.5)
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path)

    # 论文正文用简版：去掉标题与图例（图例信息移入图题），构图与配色不变
    fig, ax = plt.subplots(figsize=(2.95, 2.72))
    for (x, y, thi) in CASES["A1"]:
        for s in (-1.0, 1.0):
            a = np.radians(thi + s * BEARING_ERR)
            t = np.linspace(0.0, 1.0, 300)
            L = 4.0 * span
            xs, ys = x + L * t * np.cos(a), y + L * t * np.sin(a)
            vis = (np.abs(xs - x0) < span) & (np.abs(ys - y0) < span)
            if vis.any():
                ax.plot(xs[vis], ys[vis], color=C_WEDGE, lw=0.5, ls=(0, (4, 2)),
                        zorder=1)
            ax.plot(x, y, marker="^", color=C_DET, ms=3.2, zorder=6)
    ax.plot(M[0] + rad * np.cos(th), M[1] + rad * np.sin(th), color=C_CIRCLE,
            lw=0.9, zorder=3)
    ax.fill(V[:, 0], V[:, 1], color=C_REGION, alpha=0.22, zorder=2)
    ax.plot(V[:, 0], V[:, 1], color=C_REGION, lw=1.0, zorder=4)
    ax.plot([A[0], B[0]], [A[1], B[1]], color="k", lw=0.9, zorder=5)
    ax.plot([A[0], B[0]], [A[1], B[1]], "o", ms=2.6, mfc="w", mec="k", mew=0.7,
            zorder=6)
    ax.plot(*M, marker="+", color="k", ms=4.5, mew=0.8, zorder=6)
    ax.annotate("$A$", xy=A, xytext=(A[0] - 0.08 * span, A[1] + 0.08 * span),
                fontsize=8)
    ax.annotate("$B$", xy=B, xytext=(B[0] - 0.40 * span, B[1] + 0.06 * span),
                fontsize=8)
    ax.annotate("$M$", xy=M, xytext=(M[0] + 0.10 * span, M[1] - 0.12 * span),
                fontsize=8)
    ax.annotate("$D=%.2f$ m" % r["diameter_m"],
                xy=(0.5 * (A[0] + B[0]), 0.5 * (A[1] + B[1])),
                xytext=(x0 - 0.96 * span, y0 - 0.02 * span), fontsize=7, ha="left",
                arrowprops=dict(arrowstyle="->", lw=0.5, color="k"))
    ax.set_aspect("equal")
    ax.set_xlim(x0 - 1.16 * span, x0 + span)
    ax.set_ylim(y0 - 0.95 * span, y0 + 1.05 * span)
    ax.set_xlabel("$x$ / m")
    ax.set_ylabel("$y$ / m")
    path = os.path.join(OUT, "p1-region-bounded-plain.png")
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path)


def _check_inside(fig, ax, artists, tag):
    """轻量自检：标注必须完全落在坐标区内且留白 ≥ 1pt（避免文字出框/压轴线）。"""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ab = ax.get_window_extent(renderer=renderer)
    out = []
    for name, art in artists:
        bb = art.get_window_extent(renderer=renderer)
        if (bb.x0 < ab.x0 + 1 or bb.x1 > ab.x1 - 1
                or bb.y0 < ab.y0 + 1 or bb.y1 > ab.y1 - 1):
            out.append(name)
    if out:
        raise SystemExit("[FAIL] %s：标注越出坐标区 %s" % (tag, out))
    print("[check] %s：标注均在坐标区内" % tag)


def fig_coverage_contrast():
    """图 3：直径圆覆盖成立（A1，左）与覆盖失败（A2，右）对照。"""
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.95))
    for ax, key, tag in ((axes[0], "A1", "(a)"), (axes[1], "A2", "(b)")):
        r, V, A, B, M, rad, maxvtx, cov = _prep_case(key)
        span = 1.45 * rad
        x0, y0 = M
        th = np.linspace(0, 2 * np.pi, 400)
        ax.plot(M[0] + rad * np.cos(th), M[1] + rad * np.sin(th),
                color=C_CIRCLE, lw=1.0, zorder=3)
        ax.fill(V[:, 0], V[:, 1], color=C_REGION, alpha=0.22, zorder=2)
        ax.plot(V[:, 0], V[:, 1], color=C_REGION, lw=1.1, zorder=4)
        ax.plot([A[0], B[0]], [A[1], B[1]], color="k", lw=1.0, zorder=5)
        ax.plot([A[0], B[0]], [A[1], B[1]], "o", ms=3.0, mfc="w", mec="k",
                mew=0.8, zorder=6)
        ax.plot(*M, marker="+", color="k", ms=5, mew=0.9, zorder=6)
        marks = [("$M$", ax.annotate("$M$", xy=M,
                                     xytext=(M[0] + 0.09 * span, M[1] + 0.07 * span),
                                     fontsize=8, zorder=8))]

        if not cov:                                        # 标出越界顶点 P
            Vv = np.array(r["vertices"])
            far = Vv[np.argmax(np.linalg.norm(Vv - M, axis=1))]
            ax.plot(*far, "o", ms=5.0, mfc="none", mec=C_BAD, mew=0.9, zorder=7)
            ax.plot([M[0], far[0]], [M[1], far[1]], color=C_BAD, lw=0.8,
                    ls=(0, (3, 2)), zorder=6)
            # 只标字母：数值见子图标题与图题，图内不再放带框文本框
            marks.append(("$P$", ax.annotate(
                "$P$", xy=far,
                xytext=(far[0] - 0.12 * span, far[1] - 0.05 * span),
                fontsize=8, color=C_BAD, ha="center", va="top", zorder=8)))

        D = r["diameter_m"]
        msg = ("$\\max|P-M|=%.2f\\leq D/2$\ncovering holds"
               % maxvtx) if cov else ("$\\max|P-M|=%.2f>D/2$\ncovering fails"
                                      % maxvtx)
        ax.set_title("%s %s,  $D=%.2f$ m\n%s" % (tag, key, D, msg), fontsize=7.2,
                     color="#1b5e20" if cov else C_BAD)
        ax.set_aspect("equal")
        ax.set_xlim(x0 - span, x0 + span)
        ax.set_ylim(y0 - span, y0 + span)
        ax.set_xlabel("$x$ / m")
        if key == "A1":
            ax.set_ylabel("$y$ / m")
        else:
            ax.set_yticklabels([])
        _check_inside(fig, ax, marks, "图 2(%s) 标注" % tag[-2])
    path = os.path.join(OUT, "p1-coverage-contrast.png")
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path)


def fig_unbounded():
    """图 4：两示向度方向夹角 <= 2 eps 时区域无界（逃逸方向集合非空）。

    示意图：纵向尺度放大以显示角楔张角，横向仅为示意，不代表真实量级。
    """
    dets = [(1500.0, 0.0, 180.0), (600.0, 0.0, 180.6)]
    svds = [d[2] for d in dets]
    assert region_is_unbounded(svds) is not None, "示例构型应为无界"

    fig, ax = plt.subplots(figsize=(3.15, 2.15))
    L = 6.0e3
    for (x, y, thi) in dets:                      # 角楔边界（示意：纵向放大 0.6°）
        for s in (-1.0, 1.0):
            a = np.radians(thi + s * BEARING_ERR)
            t = np.linspace(0.0, 1.0, 200)
            ax.plot(x - L * t * np.cos(a), y + 0.06 * L * t * np.sin(a),
                    color=C_WEDGE, lw=0.6, ls=(0, (4, 2)), zorder=1)
        ax.plot(x, y, marker="^", color=C_DET, ms=4.0, zorder=5)

    xs = np.linspace(-1.45e3, 3.4e3, 200)         # 公共条带（示意）
    ax.fill_between(xs, -0.85e2 * np.ones_like(xs), 0.85e2 * np.ones_like(xs),
                    color=C_REGION, alpha=0.22, zorder=2)

    ax.annotate("", xy=(3.3e3, 0.0), xytext=(1.5e3, 0.0),
                arrowprops=dict(arrowstyle="-|>", lw=1.2, color=C_BAD,
                                mutation_scale=9))
    ax.text(1.4e3, 1.05e2, "escaping direction set\n"
                           "common angle interval nonempty",
            fontsize=6.6, color=C_BAD, ha="center", va="bottom")
    ax.annotate("$S_1$", xy=(1.5e3, 0.0), xytext=(1.5e3, -5.2e2), fontsize=7,
                ha="center", arrowprops=dict(arrowstyle="-", lw=0.4, color="#37474f"))
    ax.annotate("$S_2$", xy=(6.0e2, 0.0), xytext=(6.0e2, -8.2e2), fontsize=7,
                ha="center", arrowprops=dict(arrowstyle="-", lw=0.4, color="#37474f"))
    ax.text(-1.42e3, 8.4e2,
            "$|\\theta_1-\\theta_2|=%.1f^\\circ\\leq 2\\varepsilon$\n"
            "$\\Rightarrow$ region unbounded" % abs(svds[0] - svds[1]),
            fontsize=6.8, va="top", ha="left", color="#37474f")
    ax.set_xlim(-1.5e3, 4.0e3)
    ax.set_ylim(-1.5e3, 1.05e3)
    ax.set_xlabel("$x$ / m  (schematic)")
    ax.set_ylabel("$y$ / m  (exaggerated)")
    ax.set_title("unbounded case: nearly parallel sightlines", fontsize=7.5)
    path = os.path.join(OUT, "p1-unbounded.png")
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path)


def main():
    os.makedirs(OUT, exist_ok=True)
    fig_region_bounded()
    fig_coverage_contrast()
    fig_unbounded()


if __name__ == "__main__":
    main()
