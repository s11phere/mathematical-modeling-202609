# -*- coding: utf-8 -*-
"""生成问题一求解算法流程图（论文 5.1.3 节）。

输出：B_locator/paper/figures/p1-algorithm-flow.png
排版约定：中文用 SimSun（与正文一致），公式用 matplotlib 的 Computer Modern 数学字体
（与正文 LaTeX 公式观感一致）。方框尺寸由文字的实际渲染尺寸反算，保证文字不越界、
框与框不重叠。
运行：python make_p1_flowchart.py
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "paper", "figures"))

plt.rcParams.update({
    "font.family": "SimSun",
    "font.serif": ["SimSun"],
    "mathtext.fontset": "cm",        # 数学字体与论文 LaTeX 公式一致
    "axes.unicode_minus": False,
    "savefig.dpi": 400,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

C_IO = "#eef2e6"
C_BOX = "#f5f7f9"
C_DEC = "#fdf1e3"
C_BAD = "#e9eff8"
C_EDGE = "#37474f"
C_ARROW = "#263238"

FS = 8.0               # 正文框字号（pt）
FS_BAD = 7.4
PAD_X = 2.6            # 方框左右内边距（pt）
PAD_Y = 0.6            # 方框上下内边距（pt，压到接近字高）
GAP = 2.6              # 相邻框之间的竖直间隙（pt）
PAD_DEC_W = 6.0        # 菱形框左右内边距（pt，菱形可用宽度只有一半）
PAD_DEC_H = 3.6        # 菱形框上下内边距（pt）


def measure(fig, ax, renderer, text, fs, linespacing=1.45):
    """量出文字在图坐标下的宽（pt）与行数，支持以 \\n 分行。"""
    t = ax.text(0.0, 0.0, text, fontsize=fs, ha="center", va="center",
                linespacing=linespacing)
    bb = t.get_window_extent(renderer=renderer)
    t.remove()
    return bb.width / fig.dpi * 72.0, len(text.split("\n"))


def text_block_height(fs, n_lines, linespacing=1.45):
    """文字块高度（pt）：单行按字高，多行按行距累加。

    字体自带的上下余量不计入，故方框可以贴得比 get_window_extent 的结果更紧。
    """
    return fs * (1.0 + (n_lines - 1) * linespacing)


def main():
    # 每框文字控制在两行以内并压缩框数（8 → 6），以降低整体高度
    nodes = [
        ("输入：$m$ 个检测点坐标、示向度 $\\theta_i$\n误差界 $\\varepsilon$",
         C_IO, "box"),
        ("有界性预判：各方位角区间求交，非空则区域无界", C_BOX, "box"),
        ("无界？", C_DEC, "dec"),
        ("区域构造：$2m$ 个半平面依次裁剪得 $\\mathcal{R}$（式 (1)）\n"
         "求直径：枚举最远点对得 $D$、端点 $A,B$（式 (2)）", C_BOX, "box"),
        ("覆盖判定：比较 $\\max\\|P-M\\|$ 与 $D/2$（式 (3)）", C_BOX, "box"),
        ("输出：顶点集 $V$、$D$、$A,B$、圆心 $M$ 与是否覆盖", C_IO, "box"),
    ]

    fig, ax = plt.subplots(figsize=(6.2, 2.9))
    renderer = fig.canvas.get_renderer()

    metrics = []
    for text, _fc, kind in nodes:
        w, n_lines = measure(fig, ax, renderer, text, FS)
        metrics.append((w, n_lines, kind))

    step = []
    y_top = 0.0
    for (w, n_lines, kind) in metrics:
        h = text_block_height(FS, n_lines)      # 只按字高/行距算，不含字体自带余量
        if kind == "dec":
            # 菱形：文字沿水平中线只占一半宽度，故左右需加倍留白
            bw = 2.0 * (w + PAD_DEC_W)
            bh = h + 2 * PAD_DEC_H
        else:
            bw = w + 2 * PAD_X
            bh = h + 2 * PAD_Y
        yc = y_top - bh / 2.0
        step.append((yc, bh, bw, kind))
        y_top = yc - bh / 2.0 - GAP

    boxes = []
    for (text, fc, kind), (yc, bh, bw, k) in zip(nodes, step):
        # 保留少量外扩，使线框（线宽一半）不被裁掉
        m = 0.6
        if k == "dec":
            ax.add_patch(Polygon([(0.0, yc + bh / 2), (bw / 2, yc), (0.0, yc - bh / 2),
                                  (-bw / 2, yc)], closed=True, linewidth=0.7,
                                 edgecolor=C_EDGE, facecolor=C_DEC, zorder=2))
        else:
            ax.add_patch(FancyBboxPatch((-bw / 2 - m, yc - bh / 2 - m), bw + 2 * m,
                                        bh + 2 * m,
                                        boxstyle="round,pad=0,rounding_size=0.34",
                                        linewidth=0.7, edgecolor=C_EDGE, facecolor=fc,
                                        zorder=2))
            bw += 2 * m
            bh += 2 * m
        ax.text(0.0, yc, text, ha="center", va="center", fontsize=FS, zorder=3)
        boxes.append((yc, bh, bw, k))

    for i in range(len(boxes) - 1):
        y0, h0, _, _ = boxes[i]
        y1, h1, _, _ = boxes[i + 1]
        ax.add_patch(FancyArrowPatch((0.0, y0 - h0 / 2), (0.0, y1 + h1 / 2),
                                     arrowstyle="-|>", mutation_scale=7.5,
                                     linewidth=0.75, color=C_ARROW, zorder=1,
                                     shrinkA=0.6, shrinkB=0.6))
        if boxes[i][3] == "dec":
            ax.text(-4.4, (y0 - h0 / 2 + y1 + h1 / 2) / 2, "否", fontsize=7.4,
                    ha="center", va="center", color=C_ARROW, zorder=4)

    y_dec, _h_dec, w_dec, _ = boxes[2]
    bad_text = "报告不可用：无界构型，不给直径"
    w_t, h_t = measure(fig, ax, renderer, bad_text, FS_BAD)
    w_bad, h_bad = w_t + 2 * PAD_X, h_t + 2 * PAD_Y
    x_bad = w_dec / 2 + 8.0 + w_bad / 2
    ax.add_patch(FancyBboxPatch((x_bad - w_bad / 2, y_dec - h_bad / 2), w_bad, h_bad,
                                boxstyle="round,pad=0,rounding_size=0.34",
                                linewidth=0.7, edgecolor=C_EDGE, facecolor=C_BAD,
                                zorder=2))
    ax.text(x_bad, y_dec, bad_text, fontsize=FS_BAD, ha="center", va="center",
            zorder=3)
    ax.add_patch(FancyArrowPatch((w_dec / 2, y_dec), (x_bad - w_bad / 2, y_dec),
                                 arrowstyle="-|>", mutation_scale=7.5,
                                 linewidth=0.75, color=C_ARROW, zorder=1,
                                 shrinkA=0.6, shrinkB=0.6))
    ax.text(w_dec / 2 + 10.5, y_dec + 3.4, "是", fontsize=7.4, ha="center",
            va="center", color=C_ARROW, zorder=4)

    half_max = max(bw for _, _, bw, _ in boxes) / 2.0
    margin = 2.5
    ax.set_xlim(-(half_max + margin), x_bad + w_bad / 2 + margin)
    ax.set_ylim(boxes[-1][0] - boxes[-1][1] / 2 - margin,
                boxes[0][0] + boxes[0][1] / 2 + margin)
    ax.axis("off")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "p1-algorithm-flow.png")
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path)


if __name__ == "__main__":
    main()
