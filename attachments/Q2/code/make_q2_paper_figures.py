"""Q2 结果图（论文排版版）：从两份原始数据重新出图。

产出（写入 paper/figures/，同时留一份在 Q2/figures/）：
  p2-mma-vs-pysim.png  MMA 与 Python 两张 E[D] 热力图并排，直接目视比对
  p2-contour60.png     E[D] <= 60 m 等值线围出的第二检测点待选区域
  p2-mma-heatmap.png   MMA 单独热力图
  p2-pysim-heatmap.png Python 单独热力图

与 ``Q2/make_q2_figures.py`` 共用同一套数据、坐标系、色标与非线性归一化，
只把画幅与字号改成适合论文单页排版的尺寸。

用法：
    python Q2/make_q2_paper_figures.py
"""
from __future__ import annotations

import os
import shutil
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                          # noqa: E402
from matplotlib import rcParams                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from make_q2_figures import (                                            # noqa: E402
    AXIS_PAD, CB_TICKS, CLIP_LEVEL, COLOR_ANCHORS, CONTOUR_LEVEL,
    DEFAULT_MMA, DEFAULT_PY, FILL_COLOR, R_ARENA, PiecewiseNorm,
    load_mma, load_py, make_cmap, smooth_nan, to_grid,
)

PAPER_FIG = os.path.normpath(os.path.join(HERE, "..", "paper", "figures"))
LOCAL_FIG = os.path.join(HERE, "figures")
EXTENT = (-R_ARENA - AXIS_PAD, R_ARENA + AXIS_PAD,
          -R_ARENA - AXIS_PAD, R_ARENA + AXIS_PAD)

# 论文排版字号：图内文字与正文字号相当
FS_TITLE = 7.6
FS_LABEL = 7.0
FS_TICK = 6.4
FS_INFO = 6.2
FS_CBAR = 6.4
FS_ANNOT = 7.0


def _setup():
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"] + list(
        rcParams["font.sans-serif"])
    rcParams["axes.unicode_minus"] = False
    rcParams["font.size"] = FS_TICK
    return plt


def _decorate(ax, title, show_ylabel=True):
    ax.axhline(0, color="k", lw=0.6, ls=(0, (6, 4)), alpha=0.6, zorder=5)
    ax.axvline(0, color="k", lw=0.6, ls=(0, (6, 4)), alpha=0.6, zorder=5)
    ax.set_xlim(EXTENT[0], EXTENT[1])
    ax.set_ylim(EXTENT[2], EXTENT[3])
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)  ——  $S_2$ 的横坐标", fontsize=FS_LABEL)
    if show_ylabel:
        ax.set_ylabel("y (m)  ——  $S_2$ 的纵坐标", fontsize=FS_LABEL)
    ax.set_title(title, fontsize=FS_TITLE)
    ax.tick_params(labelsize=FS_TICK)
    ax.grid(alpha=0.22, lw=0.4)


def _info_box(ax, lines):
    ax.text(0.015, 0.985, "\n".join(lines), transform=ax.transAxes,
            fontsize=FS_INFO, va="top", ha="left", zorder=12, linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.32", fc="white", ec="#555555",
                      alpha=0.92))


def _star(ax, x, y, ms=11):
    ax.plot(x, y, marker="*", ms=ms, mfc="#00e5ff", mec="k", mew=0.7, zorder=9)


def _min_lines(val, x, y):
    return ["原点 $S_1$ = (0, 0)",
            f"极小值 $E[D]$ = {val:.2f} m",
            f"  ① ({x:.0f}, {y:.0f}) m",
            f"  ② ({x:.0f}, {-y:.0f}) m"]


def _fields():
    """读出两份数据并转成规则网格。"""
    a, b, d = load_mma(DEFAULT_MMA)
    mma = dict(a=a, b=b, d=d,
               X_Y_V=to_grid(a, b, np.where(d <= CLIP_LEVEL, d, np.nan), 15.0),
               k=int(np.argmin(d)))
    x, y, e, usable = load_py(DEFAULT_PY)
    keep = usable & np.isfinite(e) & (e <= CLIP_LEVEL)
    py = dict(x=x, y=y, e=e, usable=usable, keep=keep,
              X_Y_V=to_grid(x, y, np.where(keep, e, np.nan), 30.0),
              k=int(np.argmin(np.where(keep, e, np.inf))))
    return mma, py


def _panel(ax, plt, cmap, norm, XYZ, vals, title, show_ylabel=True):
    X, Y, V = XYZ
    cm = cmap.copy(); cm.set_bad("white")
    im = ax.pcolormesh(X, Y, np.ma.masked_invalid(V), cmap=cm, norm=norm,
                       shading="auto")
    _decorate(ax, title, show_ylabel=show_ylabel)
    _star(ax, vals["x"], vals["y"])
    _star(ax, vals["x"], -vals["y"])
    _info_box(ax, _min_lines(vals["v"], vals["x"], vals["y"]))
    return im


def fig_mma_vs_pysim(plt, cmap, norm, mma, py, out):
    """两张热力图并排——吻合度直接目视可见。"""
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 5.55))
    X, Y, V = mma["X_Y_V"]; k = mma["k"]
    im1 = _panel(axes[0], plt, cmap, norm, mma["X_Y_V"],
                 dict(x=mma["a"][k], y=mma["b"][k], v=mma["d"][k]),
                 "（a）理论闭式解（Mathematica，15 m 网格）")
    X, Y, V = py["X_Y_V"]; k = py["k"]
    im2 = _panel(axes[1], plt, cmap, norm, py["X_Y_V"],
                 dict(x=py["x"][k], y=py["y"][k], v=py["e"][k]),
                 "（b）数值模拟（Python，30 m 网格）", show_ylabel=False)
    cb = fig.colorbar(im2, ax=axes, shrink=0.92, pad=0.015, ticks=CB_TICKS,
                      fraction=0.030)
    cb.set_label("$E[D]$ (m)    $>$1000 绘制为白色", fontsize=FS_CBAR)
    cb.ax.tick_params(labelsize=FS_TICK)
    fig.savefig(out, dpi=330, bbox_inches="tight")
    plt.close(fig)


def fig_mma_heatmap(plt, cmap, norm, mma, out):
    fig, ax = plt.subplots(figsize=(5.3, 5.3))
    k = mma["k"]
    im = _panel(ax, plt, cmap, norm, mma["X_Y_V"],
                dict(x=mma["a"][k], y=mma["b"][k], v=mma["d"][k]),
                "根据理论闭式解的 $E[D]$ 分布（Mathematica）")
    cb = fig.colorbar(im, ax=ax, shrink=0.90, pad=0.02, ticks=CB_TICKS)
    cb.set_label("$E[D]$ (m)    $>$1000 绘制为白色", fontsize=FS_CBAR)
    cb.ax.tick_params(labelsize=FS_TICK)
    fig.tight_layout(); fig.savefig(out, dpi=330, bbox_inches="tight")
    plt.close(fig)


def fig_pysim_heatmap(plt, cmap, norm, py, out):
    fig, ax = plt.subplots(figsize=(5.3, 5.3))
    k = py["k"]
    im = _panel(ax, plt, cmap, norm, py["X_Y_V"],
                dict(x=py["x"][k], y=py["y"][k], v=py["e"][k]),
                "根据数值模拟的 $E[D]$ 分布（Python）")
    cb = fig.colorbar(im, ax=ax, shrink=0.90, pad=0.02, ticks=CB_TICKS)
    cb.set_label("$E[D]$ (m)    $>$1000 绘制为白色", fontsize=FS_CBAR)
    cb.ax.tick_params(labelsize=FS_TICK)
    fig.tight_layout(); fig.savefig(out, dpi=330, bbox_inches="tight")
    plt.close(fig)


def fig_contour60(plt, mma, out):
    a, b, d = mma["a"], mma["b"], mma["d"]
    keep = d <= CLIP_LEVEL
    X, Y, V = to_grid(a, b, np.where(keep, d, np.nan), 15.0)
    V = smooth_nan(V, 2)

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    v_lo = float(np.nanmin(V))
    ax.contourf(X, Y, V, levels=[v_lo, CONTOUR_LEVEL], colors=[FILL_COLOR],
                zorder=6)
    cs = ax.contour(X, Y, V, levels=[CONTOUR_LEVEL], colors=["#08306b"],
                    linewidths=1.8, zorder=7)
    _decorate(ax, "放置第二检测点 $S_2$ 的待选区域")

    loops = [p for p in cs.allsegs[0] if len(p) > 10]
    loops.sort(key=lambda p: -p[:, 1].mean())
    for i, lp in enumerate(loops):
        x1, y1 = lp[:, 0].max(), lp[:, 1].max()
        x1b, y0 = lp[:, 0].max(), lp[:, 1].min()
        if i == 0:
            ax.annotate(f"$E[D]={CONTOUR_LEVEL:.0f}$ m", (x1, y1),
                        textcoords="offset points", xytext=(8, 3),
                        fontsize=FS_ANNOT, color="#08306b", ha="left",
                        va="bottom", zorder=11)
        else:
            ax.annotate(f"$E[D]={CONTOUR_LEVEL:.0f}$ m", (x1b, y0),
                        textcoords="offset points", xytext=(8, -3),
                        fontsize=FS_ANNOT, color="#08306b", ha="left",
                        va="top", zorder=11)

    k = mma["k"]
    _star(ax, a[k], b[k]); _star(ax, a[k], -b[k])
    # 两条边界之间的楔形（可选）：只画出待选区域所在的角向带
    _info_box(ax, _min_lines(d[k], a[k], b[k])
              + [f"等值线 $E[D]={CONTOUR_LEVEL:.0f}$ m：{len(loops)} 条闭合回路"])
    fig.tight_layout(); fig.savefig(out, dpi=330, bbox_inches="tight")
    plt.close(fig)
    return len(loops)


def main():
    plt = _setup()
    cmap, norm = make_cmap(), PiecewiseNorm()
    mma, py = _fields()
    os.makedirs(LOCAL_FIG, exist_ok=True)
    os.makedirs(PAPER_FIG, exist_ok=True)

    jobs = [
        ("p2-mma-vs-pysim.png", lambda p: fig_mma_vs_pysim(plt, cmap, norm, mma, py, p)),
        ("p2-mma-heatmap.png", lambda p: fig_mma_heatmap(plt, cmap, norm, mma, p)),
        ("p2-pysim-heatmap.png", lambda p: fig_pysim_heatmap(plt, cmap, norm, py, p)),
        ("p2-contour60.png", lambda p: fig_contour60(plt, mma, p)),
    ]
    for name, fn in jobs:
        local = os.path.join(LOCAL_FIG, name)
        fn(local)
        shutil.copy2(local, os.path.join(PAPER_FIG, name))
        print("[OK] %-24s %7.1f KB  ->  %s" % (
            name, os.path.getsize(local) / 1024, PAPER_FIG))
    print("\n极小值：MMA %.3f m @ (%.0f, %.0f)；Python %.3f m @ (%.0f, %.0f)" % (
        mma["d"][mma["k"]], mma["a"][mma["k"]], mma["b"][mma["k"]],
        py["e"][py["k"]], py["x"][py["k"]], py["y"][py["k"]]))


if __name__ == "__main__":
    main()
