# -*- coding: utf-8 -*-
"""生成问题一求解算法流程图（论文 5.1.3 节）。

输出：B_locator/paper/figures/p1-algorithm-flow.png

设计约定
--------
1. **1:1 点坐标系**：坐标轴铺满整张图（``add_axes([0, 0, 1, 1])``），数据单位即排版点（pt），
   并且 ``figsize = 内容尺寸 / 72``、保存时不再用 ``bbox_inches="tight"``。这样 PNG 的物理
   尺寸就等于设计尺寸，``\\includegraphics[width=...]`` 按该宽度插入时是 1:1 渲染：
   图内字号 = 设计字号，不会出现 x/y 方向缩放不一致导致的错位。
2. **框长随文字变化**：每个节点文字排成一行，框宽 = 该行实测宽度 + 内边距（不再强行等宽），
   各框水平居中成一条主链。
3. **分支标注不重叠**：菱形右出口的"是"放在水平间隙内、靠菱形一侧；竖直出口的"否"放在
   加宽的间隙（``GAP_BRANCH``）中，右对齐在箭头左侧；间距全部由文字实测宽度/行数反算。
4. **自检**：绘制完成后逐项断言（文字不越框、是/否不碰任何框、全部内容在画布内且留白
   ≥ 1pt），任一不满足即抛错退出，避免再次出现"是/否压框"。
5. 字体：中文用仓库自带 ``paper/fonts/simsun.ttc``（与正文同源，宋体），公式用 Computer Modern
   （与正文 LaTeX 公式观感一致）。图内文字与论文一致：仅把原先两行的输入框并成一行、
   把"求直径"从合框中拆成独立一步，措辞不变。

运行：python make_p1_flowchart.py
"""
from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib import font_manager, rcParams                      # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.normpath(os.path.join(HERE, os.pardir, "paper"))
OUT = os.path.join(PAPER, "figures")
SIMSUN = os.path.join(PAPER, "fonts", "simsun.ttc")  # 与正文 \setCJKfamilyfont 同源

TEXTWIDTH_PT = 453.54        # 正文栏宽：A4 210mm - 左右各 25mm = 160mm = 453.54pt
MAX_W_FRACTION = 0.62        # 目标：图宽不超过 0.62 倍正文宽
MAX_H_PT = 178.0             # 目标：图高不超过 178pt（旧图 204pt）

C_IO = "#eef2e6"
C_BOX = "#f5f7f9"
C_DEC = "#fdf1e3"
C_BAD = "#e9eff8"
C_EDGE = "#37474f"
C_ARROW = "#263238"

FS_CANDIDATES = (10.0, 9.5, 9.0, 8.5, 8.0)   # 从大到小试，取满足尺寸上限的最大字号
FS_BAD = 7.5          # 右侧"报告不可用"终端框字号
PAD_X = 8.0           # 方框左右内边距（pt；文字不贴框）
PAD_Y = 1.4           # 方框上下内边距（pt）
BORDER = 0.6          # 线框外扩量，避免半线宽被裁（计入框宽/框高）
PAD_DEC_W = 6.0       # 菱形左右内边距（菱形在该高度上只有一半可用宽度）
PAD_DEC_H = 3.6       # 菱形上下内边距
GAP = 9.0             # 相邻框竖直间隙（pt，箭头要有可见的杆）
GAP_MIN_LABEL = 2.6   # 竖直分支标注与上下框的最小留白（pt）
GAP_H_MIN = 18.0      # 菱形右出口水平间隙最小值（pt，"是"字放在靠菱形一侧）
LABEL_INSET = 3.0     # "是"字左缘距菱形右顶点的距离（pt）
LABEL_LIFT = 1.2      # "是"字底边距水平箭头的距离（pt）
MARGIN = 2.5          # 画布四周留白（pt）
CHECK_CLEAR = 0.8     # 自检要求的最小留白（pt）

# 每个节点文字排成一行（框长随文字变化）；除菱形外均为"矩形框"
NODES = [
    ("输入：$m$ 个检测点坐标、示向度 $\\theta_i$、误差界 $\\varepsilon$",
     C_IO, "box"),
    ("有界性预判：各方位角区间求交，非空则区域无界", C_BOX, "box"),
    ("无界？", C_DEC, "dec"),
    ("区域构造：$2m$ 条边界直线求交、半平面筛选得 $\\mathcal{R}$（式 (1)）", C_BOX, "box"),
    ("求直径：枚举最远点对得 $D$、端点 $A,B$（式 (2)）", C_BOX, "box"),
    ("覆盖判定：比较 $\\max\\|P-M\\|$ 与 $D/2$（式 (3)）", C_BOX, "box"),
    ("输出：顶点集 $V$、$D$、$A,B$、圆心 $M$ 与是否覆盖", C_IO, "box"),
]
BAD_TEXT = "报告不可用：\n无界构型，不给直径"      # 措辞与原文一致，仅折成两行
DEC_INDEX = 2                                     # "无界？"所在行


# --------------------------------------------------------------------- 字体
def setup_fonts() -> str:
    """注册仓库自带宋体并返回可用的中文字族名。"""
    candidates = []
    if os.path.exists(SIMSUN):
        try:
            font_manager.fontManager.addfont(SIMSUN)
            candidates.append(font_manager.FontProperties(fname=SIMSUN).get_name())
        except Exception as exc:                              # pragma: no cover
            print("[warn] 无法注册 %s：%s" % (SIMSUN, exc))
    candidates += ["Songti SC", "STSong"]
    for name in candidates:
        try:
            path = font_manager.findfont(font_manager.FontProperties(family=name),
                                         fallback_to_default=False)
        except Exception:
            continue
        rcParams.update({
            "font.family": name,
            "mathtext.fontset": "cm",     # 与正文 LaTeX 公式一致
            "axes.unicode_minus": False,
            "savefig.dpi": 400,
        })
        print("[font] 中文 = %s (%s)" % (name, path))
        return name
    print("[warn] 未找到宋体，回退 matplotlib 默认字体")
    return "sans-serif"


# --------------------------------------------------------------------- 度量
def measure(fig, ax, renderer, text, fs):
    """实测文字宽度（pt）与行数。"""
    t = ax.text(0.0, 0.0, text, fontsize=fs, ha="center", va="center",
                linespacing=1.45)
    bb = t.get_window_extent(renderer=renderer)
    t.remove()
    return bb.width / fig.dpi * 72.0, len(text.split("\n"))


def text_block_height(fs, n_lines, linespacing=1.45):
    """文字块高度（pt）：单行按字高，多行按行距累加（不含字体自带上下余量）。"""
    return fs * (1.0 + (n_lines - 1) * linespacing)


# --------------------------------------------------------------------- 排版
def build_layout(fig, ax, renderer, fs):
    """按 fs 算出全部几何（单位 pt），返回布局字典。"""
    metrics = [measure(fig, ax, renderer, text, fs) for text, _fc, _k in NODES]

    bad_w, bad_lines = measure(fig, ax, renderer, BAD_TEXT, FS_BAD)
    bad_w += 2 * (PAD_X + BORDER)
    bad_h = text_block_height(FS_BAD, bad_lines) + 2 * (PAD_Y + BORDER)

    label_w, _ = measure(fig, ax, renderer, "是", fs - 1.0)
    gap_h = max(GAP_H_MIN, label_w + 5.0)        # 菱形右出口到终端框的水平间隙

    rows = []
    for (text, fc, kind), (w, n) in zip(NODES, metrics):
        th = text_block_height(fs, n)
        if kind == "dec":
            bw = 2 * (w + PAD_DEC_W)
            bh = th + 2 * PAD_DEC_H
        else:
            bw = w + 2 * (PAD_X + BORDER)        # 框长随本行文字变化，不再等宽
            bh = th + 2 * (PAD_Y + BORDER)
        rows.append({"text": text, "fc": fc, "kind": kind, "bw": bw, "bh": bh,
                     "th": th, "n": n})

    gap_branch = max(GAP, (fs - 1.0) + 2 * GAP_MIN_LABEL)   # 竖直分支间隙
    # 菱形所在行还要容纳右侧终端框与"是"字
    label_top = LABEL_LIFT + 1.15 * (fs - 1.0)
    half_row = max(rows[DEC_INDEX]["bh"] / 2.0, bad_h / 2.0, label_top)

    y_top = 0.0
    for i, r in enumerate(rows):
        r["half"] = half_row if i == DEC_INDEX else r["bh"] / 2.0
        r["yc"] = y_top - r["half"]
        gap = gap_branch if i == DEC_INDEX else GAP
        y_top = r["yc"] - r["half"] - gap
    y_bottom = rows[-1]["yc"] - rows[-1]["half"]

    w_max = max(r["bw"] for r in rows)           # 最宽的一行决定画布左右边界
    x_dec_right = rows[DEC_INDEX]["bw"] / 2.0
    x_bad_left = x_dec_right + gap_h
    x_min = -w_max / 2.0
    x_max = max(w_max / 2.0, x_bad_left + bad_w)

    return {"rows": rows, "w_max": w_max, "bad_w": bad_w, "bad_h": bad_h,
            "bad_left": x_bad_left, "gap_h": gap_h, "gap_branch": gap_branch,
            "x_min": x_min, "x_max": x_max, "y_top": 0.0, "y_bottom": y_bottom}


# --------------------------------------------------------------------- 绘制
def draw_layout(ax, L, fs):
    """按布局绘制全部图形，返回自检所需的包围盒清单。"""
    rects, labels = [], []

    for i, r in enumerate(L["rows"]):
        yc, bw, bh = r["yc"], r["bw"], r["bh"]
        if r["kind"] == "dec":
            ax.add_patch(Polygon([(0.0, yc + bh / 2), (bw / 2, yc),
                                  (0.0, yc - bh / 2), (-bw / 2, yc)],
                                 closed=True, linewidth=0.7, edgecolor=C_EDGE,
                                 facecolor=r["fc"], zorder=2))
            rects.append(("菱形框", (-bw / 2, yc - bh / 2, bw / 2, yc + bh / 2)))
        else:
            ax.add_patch(FancyBboxPatch((-bw / 2, yc - bh / 2), bw, bh,
                                        boxstyle="round,pad=0,rounding_size=1.2",
                                        linewidth=0.7, edgecolor=C_EDGE,
                                        facecolor=r["fc"], zorder=2))
            rects.append(("框 %d" % (i + 1), (-bw / 2, yc - bh / 2, bw / 2, yc + bh / 2)))
        t = ax.text(0.0, yc, r["text"], ha="center", va="center", fontsize=fs,
                    zorder=3)
        labels.append(("框 %d 文字" % (i + 1), t, rects[-1][1]))

    # 竖直箭头（菱形行到下一框的箭头起点取菱形下顶点，不受终端框影响）
    for i in range(len(L["rows"]) - 1):
        r0, r1 = L["rows"][i], L["rows"][i + 1]
        y0 = r0["yc"] - (r0["bh"] / 2.0 if r0["kind"] == "dec" else r0["half"])
        y1 = r1["yc"] + r1["half"]
        ax.add_patch(FancyArrowPatch((0.0, y0), (0.0, y1), arrowstyle="-|>",
                                     mutation_scale=8.0, linewidth=0.8,
                                     color=C_ARROW, zorder=1, shrinkA=0.6,
                                     shrinkB=0.6))

    # "否"：竖直分支间隙内、箭头左侧右对齐
    dec = L["rows"][DEC_INDEX]
    y_mid = dec["yc"] - dec["half"] - L["gap_branch"] / 2.0
    t_no = ax.text(-4.0, y_mid, "否", fontsize=fs - 1.0, ha="right", va="center",
                   color=C_ARROW, zorder=4)
    labels.append(("否", t_no, None))

    # 右侧终端框（是分支）+ "是"字
    yc, xb = dec["yc"], L["bad_left"]
    ax.add_patch(FancyBboxPatch((xb, yc - L["bad_h"] / 2), L["bad_w"], L["bad_h"],
                                boxstyle="round,pad=0,rounding_size=1.2",
                                linewidth=0.7, edgecolor=C_EDGE, facecolor=C_BAD,
                                zorder=2))
    bad_rect = (xb, yc - L["bad_h"] / 2, xb + L["bad_w"], yc + L["bad_h"] / 2)
    rects.append(("终端框", bad_rect))
    t_bad = ax.text(xb + L["bad_w"] / 2.0, yc, BAD_TEXT, fontsize=FS_BAD,
                    ha="center", va="center", zorder=3)
    labels.append(("终端框文字", t_bad, bad_rect))

    ax.add_patch(FancyArrowPatch((dec["bw"] / 2.0, yc), (xb, yc),
                                 arrowstyle="-|>", mutation_scale=8.0,
                                 linewidth=0.8, color=C_ARROW, zorder=1,
                                 shrinkA=0.6, shrinkB=0.6))
    t_yes = ax.text(dec["bw"] / 2.0 + LABEL_INSET, yc + LABEL_LIFT,
                    "是", fontsize=fs - 1.0, ha="left", va="bottom",
                    color=C_ARROW, zorder=4)
    labels.append(("是", t_yes, None))

    return rects, labels


# --------------------------------------------------------------------- 自检
def _bbox(ax, artist, renderer):
    bb = artist.get_window_extent(renderer=renderer)
    inv = ax.transData.inverted()
    (x0, y0), (x1, y1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _hits(a, b, clear=0.0):
    """两个包围盒在留白 clear(pt) 之内相交则返回 True。"""
    return not (a[2] + clear <= b[0] or b[2] + clear <= a[0]
                or a[3] + clear <= b[1] or b[3] + clear <= a[1])


def self_check(ax, fig, L, rects, labels, fs):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    errors = []

    own = {name: rect for name, _t, rect in labels if rect is not None}
    for name, artist, rect in labels:
        bb = _bbox(ax, artist, renderer)
        if rect is not None and own.get(name) is rect:
            # 文字必须在自己框内，且四边留白 ≥ 0.2pt
            if not (rect[0] - 0.2 <= bb[0] and bb[2] <= rect[2] + 0.2
                    and rect[1] - 0.2 <= bb[1] and bb[3] <= rect[3] + 0.2):
                errors.append("%s 越出所属框：文字 %s vs 框 %s"
                              % (name, _r(bb), _r(rect)))

    # "是/否"不得与任何框（含菱形包围盒）在 0.8pt 内相交
    frame_rects = [r for _n, r in rects]
    for name, artist, rect in labels:
        if rect is not None:
            continue
        bb = _bbox(ax, artist, renderer)
        for fname, fr in zip([n for n, _r_ in rects], frame_rects):
            if _hits(bb, fr, clear=CHECK_CLEAR):
                errors.append("%s 与%s 重叠或过近（留白 < %.1fpt）"
                              % (name, fname, CHECK_CLEAR))

    # 全部内容必须在画布内且留白 ≥ 1pt
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    for name, artist, _rect in labels:
        bb = _bbox(ax, artist, renderer)
        if not (bb[0] >= x0 + 1.0 and bb[2] <= x1 - 1.0
                and bb[1] >= y0 + 1.0 and bb[3] <= y1 - 1.0):
            errors.append("%s 距画布边缘不足 1pt：%s（画布 %.1f×%.1f）"
                          % (name, _r(bb), x1 - x0, y1 - y0))

    if errors:
        print("[FAIL] 自检未通过：")
        for e in errors:
            print("   -", e)
        raise SystemExit(1)
    print("[check] 自检通过：文字不越框、是/否无重叠、内容均在画布内")


def _r(bb):
    return "(%.1f, %.1f)–(%.1f, %.1f)" % bb


# --------------------------------------------------------------------- 主流程
def main():
    setup_fonts()

    # 先在临时画布上测量文字，选定字号与布局
    probe = plt.figure(figsize=(6.0, 3.0))
    probe_ax = probe.add_axes([0, 0, 1, 1])
    probe.canvas.draw()
    renderer = probe.canvas.get_renderer()

    chosen = None
    for fs in FS_CANDIDATES:
        L = build_layout(probe, probe_ax, renderer, fs)
        w = L["x_max"] - L["x_min"] + 2 * MARGIN
        h = L["y_top"] - L["y_bottom"] + 2 * MARGIN
        print("[try] fs=%.1f -> %.1f x %.1f pt (%.3f 倍正文宽)"
              % (fs, w, h, w / TEXTWIDTH_PT))
        if w <= MAX_W_FRACTION * TEXTWIDTH_PT and h <= MAX_H_PT:
            chosen = (fs, L, w, h)
            break
    plt.close(probe)
    if chosen is None:
        raise SystemExit("[FAIL] 找不到满足尺寸上限的字号，请检查 MAX_W_FRACTION / MAX_H_PT")

    fs, L, w, h = chosen

    fig = plt.figure(figsize=(w / 72.0, h / 72.0))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(L["x_min"] - MARGIN, L["x_max"] + MARGIN)
    ax.set_ylim(L["y_bottom"] - MARGIN, L["y_top"] + MARGIN)
    ax.axis("off")

    rcParams["savefig.bbox"] = None        # 尺寸 = figsize，保证 1:1
    rcParams["savefig.pad_inches"] = 0.0

    rects, labels = draw_layout(ax, L, fs)
    self_check(ax, fig, L, rects, labels, fs)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "p1-algorithm-flow.png")
    fig.savefig(path)
    plt.close(fig)

    px = w / 72.0 * 400.0
    print("[out] %s" % path)
    print("[out] 设计尺寸 %.1f x %.1f pt（%.3f 倍正文宽）；400dpi 位图 %.0f x %.0f px"
          % (w, h, w / TEXTWIDTH_PT, round(px), round(h / 72.0 * 400.0)))
    print("[out] 建议 LaTeX 宽度：width=%.2f\\textwidth" % (w / TEXTWIDTH_PT))


if __name__ == "__main__":
    main()
