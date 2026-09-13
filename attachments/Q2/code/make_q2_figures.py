"""Q2 结果可视化：两张热力图 + 一张 60 等值线图。

数据来源
--------
1) ``Q2/MMAcode/Q2_expected_diameter_data.csv``
   列 ``a, b, d_m``，36960 点，网格 15 m，a∈[-500,1795]、b∈[-1800,1800]。
   MMA 闭式近似得到的期望交会区域直径 E[D]。
2) ``Q2/pysimulation/out/p2_grid/p2_grid_map.csv``
   列含 ``x_m, y_m, E_diam_given_detectable_m, p_detectable, usable, ...``，
   11168 点，网格 30 m，靶区圆盘内。精确四边形几何得到的 E[D|可检测]。

两套数据都以「第二检测点 S2」的位置为自变量，故三幅图共用**完全相同的
坐标系、绘图范围与着色**，可直接叠放比对。

近轴异常的处理（"用等值线截断"）
--------------------------------
MMA 的闭式近似在近轴处 sin(gamma)->0 使 d_m 发散：实测 x=1000 处
y=-45 -> 342.9，y=-30 -> 874.5，y=-15 -> 5764.4，y=0 附近可达 4.7e4，
属**数值精度异常**而非物理结果。

处理方式：把 ``E[D] > CLIP_LEVEL``（默认 1000 m）的格点掩掉。
- 不引入任何人为的 |b| 带宽，边界即为 1000 m 等值线，形态自然；
- 视觉上零损失：色标本来就规定 >1000 与 1000 同色，被掩掉的部分原本
  也是一片均匀深红，掩掉后只去掉那块"假色斑"。

着色方案（连续渐变，重点展示 55~100）
--------------------------------------
    55 深蓝 -> 65 蓝 -> 75 青 -> 85 绿 -> 93 黄 -> 100 橙
      -> 300 红 -> 1000 深红（>1000 与 1000 同色）
色标位置非线性：55~100 占前 23%，使该段的过渡清晰可辨。

用法
----
    python Q2/make_q2_figures.py                 # 输出到 Q2/figures/
    python Q2/make_q2_figures.py --out <目录>
"""
from __future__ import annotations

import argparse
import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                       # noqa: E402
from matplotlib import rcParams                                       # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize      # noqa: E402

R_ARENA = 1800.0            # 靶区半径 (m)
CLIP_LEVEL = 1000.0         # 近轴异常截断阈值：E[D] > 该值的格点掩掉
CONTOUR_LEVEL = 60.0        # 图 3 要画的等值线值
FILL_COLOR = "#bfe0f5"      # 图 3 等值线内区域的填充色（浅蓝）
AXIS_PAD = 0.0              # 坐标范围在数据范围外额外留白 (m)

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MMA = os.path.join(HERE, "MMAcode", "Q2_expected_diameter_data.csv")
DEFAULT_PY = os.path.join(HERE, "pysimulation", "out", "p2_grid", "p2_grid_map.csv")

# ---------------------------------------------------------------- 着色方案
# (数值, 颜色, 色标位置 0~1)。位置非线性：55~100 只占数值轴 4.7%，
# 若按线性映射会被压成一条细线，故给该段分配 23% 的色标宽度。
COLOR_ANCHORS = [
    (55.0,   "#08306b", 0.00),   # 深蓝
    (65.0,   "#1f6fb5", 0.05),   # 蓝
    (75.0,   "#42b6c9", 0.10),   # 青
    (85.0,   "#41ab5d", 0.15),   # 绿
    (93.0,   "#a6d96a", 0.19),   # 黄绿（向黄过渡）
    (100.0,  "#fd8d3c", 0.23),   # 橙
    (300.0,  "#e31a1c", 0.60),   # 红
    (1000.0, "#67000d", 1.00),   # 深红（>1000 全部截断到此处）
]
V_MIN, V_MAX = COLOR_ANCHORS[0][0], COLOR_ANCHORS[-1][0]
CB_TICKS = [55, 65, 75, 85, 93, 100, 300, 1000]


def _hex2rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def make_cmap():
    """按锚点插值出连续渐变 colormap（位置非等距）。"""
    pos = np.array([p for _, _, p in COLOR_ANCHORS], dtype=float)
    cs = np.array([_hex2rgb(c) for _, c, _ in COLOR_ANCHORS])
    samples = np.linspace(0.0, 1.0, 512)
    rgb = np.stack([np.interp(samples, pos, cs[:, k]) for k in range(3)], axis=1)
    return LinearSegmentedColormap.from_list("q2_diameter", rgb, N=512)


class PiecewiseNorm(Normalize):
    """把数值按 (数值, 位置) 锚点分段线性映射到 [0,1]（非线性色标的关键）。

    超出 [V_MIN, V_MAX] 的值截断到端点（>1000 与 1000 同色）。
    继承 matplotlib 的 Normalize 以便直接传给 pcolormesh / colorbar。
    """

    def __init__(self):
        super().__init__(vmin=V_MIN, vmax=V_MAX)
        self.vals = np.array([v for v, _, _ in COLOR_ANCHORS], dtype=float)
        self.pos = np.array([p for _, _, p in COLOR_ANCHORS], dtype=float)

    def __call__(self, value, clip=None):
        x = np.ma.asarray(value, dtype=float)
        out = np.interp(x.filled(np.nan), self.vals, self.pos,
                        left=self.pos[0], right=self.pos[-1])
        return np.ma.masked_invalid(out) if np.ma.isMaskedArray(x) else out

    def inverse(self, p):
        return np.interp(np.asarray(p, dtype=float), self.pos, self.vals)


# ---------------------------------------------------------------- 数据读取
def load_mma(path):
    a, b, d = [], [], []
    with open(path, encoding="utf-8-sig") as f:
        f.readline()
        for line in f:
            if not line.strip():
                continue
            p = line.split(",")
            a.append(float(p[0])); b.append(float(p[1])); d.append(float(p[2]))
    return np.array(a), np.array(b), np.array(d)


def load_py(path):
    import csv
    x, y, e, u = [], [], [], []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            x.append(float(r["x_m"])); y.append(float(r["y_m"]))
            try:
                e.append(float(r["E_diam_given_detectable_m"]))
            except (TypeError, ValueError):
                e.append(np.nan)
            u.append(int(r["usable"]))
    return np.array(x), np.array(y), np.array(e), np.array(u, dtype=bool)


def to_grid(a, b, v, step):
    """散点 -> 规则网格 (X, Y, V)，无值处为 nan。"""
    xs = np.arange(a.min(), a.max() + step * 0.5, step)
    ys = np.arange(b.min(), b.max() + step * 0.5, step)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    V = np.full(X.shape, np.nan)
    i = np.rint((a - a.min()) / step).astype(int)
    j = np.rint((b - b.min()) / step).astype(int)
    ok = (i >= 0) & (i < xs.size) & (j >= 0) & (j < ys.size)
    V[j[ok], i[ok]] = v[ok]
    return X, Y, V


def smooth_nan(V, passes=1):
    """对含 nan 的场做 3x3 均值平滑（nan 不参与，全 nan 保持 nan）。"""
    out = V.copy()
    for _ in range(passes):
        pad = np.pad(out, 1, constant_values=np.nan)
        acc = np.zeros_like(out); cnt = np.zeros_like(out)
        for dj in (0, 1, 2):
            for di in (0, 1, 2):
                w = pad[dj:dj + out.shape[0], di:di + out.shape[1]]
                m = np.isfinite(w)
                acc[m] += w[m]; cnt[m] += 1
        out = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
    return out


# ---------------------------------------------------------------- 绘图
def _setup():
    """中文字体（后端已在模块导入时固定为 Agg）。"""
    for fam in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"):
        rcParams["font.sans-serif"] = [fam] + list(rcParams["font.sans-serif"])
        break
    rcParams["axes.unicode_minus"] = False
    return plt


def _decorate(ax, extent, title):
    """统一的坐标系装饰：过原点的坐标轴 + 范围 + 标签（无图例、无靶区圆）。"""
    ax.axhline(0, color="k", lw=0.7, ls=(0, (6, 4)), alpha=0.6, zorder=5)
    ax.axvline(0, color="k", lw=0.7, ls=(0, (6, 4)), alpha=0.6, zorder=5)
    ax.set_xlim(extent[0], extent[1]); ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)  ——  S2 的横坐标")
    ax.set_ylabel("y (m)  ——  S2 的纵坐标")
    ax.set_title(title)
    ax.grid(alpha=0.22, lw=0.5)


def _info_box(ax, lines):
    """把坐标信息放到图内左上角标框（替代图例），不遮挡数据。"""
    ax.text(0.015, 0.985, "\n".join(lines), transform=ax.transAxes,
            fontsize=8.2, va="top", ha="left", zorder=12, linespacing=1.55,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#555555",
                      alpha=0.92))


def _star(ax, x, y):
    ax.plot(x, y, marker="*", ms=17, mfc="#00e5ff", mec="k", mew=0.9, zorder=9)


def _min_lines(prefix, val, x, y):
    return [f"原点 $S_1$ = (0, 0)",
            f"{prefix} $E[D]$ = {val:.2f} m",
            f"  ① ({x:.0f}, {y:.0f}) m",
            f"  ② ({x:.0f}, {-y:.0f}) m"]


def fig_mma_heatmap(plt, cmap, norm, extent, out):
    a, b, d = load_mma(DEFAULT_MMA)
    keep = (d <= CLIP_LEVEL)                 # 近轴异常：按 1000 m 等值线截断
    X, Y, V = to_grid(a, b, np.where(keep, d, np.nan), 15.0)
    Vm = np.ma.masked_invalid(V)

    fig, ax = plt.subplots(figsize=(8.8, 8.0))
    cm = cmap.copy(); cm.set_bad("white")
    im = ax.pcolormesh(X, Y, Vm, cmap=cm, norm=norm, shading="auto")
    _decorate(ax, extent,
              "根据理论闭式解的 $E[D]$ 价值函数分布（Mathematica）")
    k = int(np.argmin(d))
    _star(ax, a[k], b[k]); _star(ax, a[k], -b[k])
    _info_box(ax, _min_lines("极小值", d[k], a[k], b[k]))
    cb = fig.colorbar(im, ax=ax, shrink=0.86, pad=0.02, ticks=CB_TICKS)
    cb.set_label("$E[D]$ (m)    $>$1000 与 1000 同色")
    fig.tight_layout(); fig.savefig(out, dpi=160, bbox_inches="tight"); plt.close(fig)
    return dict(data="MMA Q2_expected_diameter_data.csv", step=15.0,
                n_total=int(a.size), n_plotted=int(keep.sum()),
                n_clipped=int((d > CLIP_LEVEL).sum()), clip_level=CLIP_LEVEL,
                min_m=float(d[k]), min_at=[float(a[k]), float(b[k])],
                vmax_plotted=float(np.nanmax(V)))


def fig_py_heatmap(plt, cmap, norm, extent, out):
    x, y, e, usable = load_py(DEFAULT_PY)
    keep = usable & np.isfinite(e) & (e <= CLIP_LEVEL)
    X, Y, V = to_grid(x, y, np.where(keep, e, np.nan), 30.0)
    Vm = np.ma.masked_invalid(V)

    fig, ax = plt.subplots(figsize=(8.8, 8.0))
    cm = cmap.copy(); cm.set_bad("white")
    im = ax.pcolormesh(X, Y, Vm, cmap=cm, norm=norm, shading="auto")
    _decorate(ax, extent,
              "根据数值模拟的 $E[D]$ 价值函数分布（Python）")
    k = int(np.argmin(np.where(keep, e, np.inf)))
    _star(ax, x[k], y[k]); _star(ax, x[k], -y[k])
    _info_box(ax, _min_lines("极小值", e[k], x[k], y[k]))
    cb = fig.colorbar(im, ax=ax, shrink=0.86, pad=0.02, ticks=CB_TICKS)
    cb.set_label("$E[D]$ (m)    $>$1000 与 1000 同色")
    fig.tight_layout(); fig.savefig(out, dpi=160, bbox_inches="tight"); plt.close(fig)
    return dict(data="pysimulation p2_grid_map.csv", step=30.0,
                n_total=int(x.size), n_plotted=int(keep.sum()),
                n_dropped_near_axis=int((~usable).sum()), clip_level=CLIP_LEVEL,
                min_m=float(e[k]), min_at=[float(x[k]), float(y[k])],
                vmax_plotted=float(np.nanmax(V)))


def _loop_bbox(loop):
    return loop[:, 0].min(), loop[:, 0].max(), loop[:, 1].min(), loop[:, 1].max()


def fig_contour60(plt, extent, out):
    a, b, d = load_mma(DEFAULT_MMA)
    keep = (d <= CLIP_LEVEL)
    X, Y, V = to_grid(a, b, np.where(keep, d, np.nan), 15.0)
    V = smooth_nan(V, 2)

    fig, ax = plt.subplots(figsize=(8.8, 8.0))
    # 等值线内区域（E[D] <= 60，即两条闭合回路内部）填浅蓝
    # zorder 低于等值线与星标，不遮挡线条
    v_lo = float(np.nanmin(V))
    ax.contourf(X, Y, V, levels=[v_lo, CONTOUR_LEVEL],
                colors=[FILL_COLOR], zorder=6)
    cs = ax.contour(X, Y, V, levels=[CONTOUR_LEVEL], colors=["#08306b"],
                    linewidths=2.2, zorder=7)
    _decorate(ax, extent, "放置第二检测点 $S_2$ 的最佳区域")

    # 注记放在等值线**外侧**（用包围盒判断可用侧），不压线，保证曲线闭合可见
    loops = [p for p in cs.allsegs[0] if len(p) > 10]
    loops.sort(key=lambda p: -p[:, 1].mean())          # 上回路在前
    for i, lp in enumerate(loops):
        x0, x1, y0, y1 = _loop_bbox(lp)
        if i == 0:      # 上回路：注记放右上外侧
            ax.annotate(f"$E[D]={CONTOUR_LEVEL:.0f}$ m", (x1, y1),
                        textcoords="offset points", xytext=(12, 4),
                        fontsize=9.5, color="#08306b", ha="left", va="bottom",
                        zorder=11)
        else:           # 下回路：注记放右下外侧
            ax.annotate(f"$E[D]={CONTOUR_LEVEL:.0f}$ m", (x1, y0),
                        textcoords="offset points", xytext=(12, -4),
                        fontsize=9.5, color="#08306b", ha="left", va="top",
                        zorder=11)

    k = int(np.argmin(d))
    _star(ax, a[k], b[k]); _star(ax, a[k], -b[k])
    _info_box(ax, _min_lines("极小值", d[k], a[k], b[k])
              + [f"等值线 $E[D]={CONTOUR_LEVEL:.0f}$ m：{len(loops)} 条闭合回路"])
    fig.tight_layout(); fig.savefig(out, dpi=160, bbox_inches="tight"); plt.close(fig)
    return dict(level=CONTOUR_LEVEL, clip_level=CLIP_LEVEL,
                n_closed_loops=len(loops),
                loop_bboxes=[[round(v, 1) for v in _loop_bbox(p)] for p in loops],
                n_contour_vertices=int(sum(len(p) for p in cs.allsegs[0])),
                min_m=float(d[k]), min_at=[float(a[k]), float(b[k])])


def main():
    ap = argparse.ArgumentParser(description="Q2 结果可视化：两热力图 + 60 等值线")
    ap.add_argument("--out", default=os.path.join(HERE, "figures"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    plt = _setup()
    cmap, norm = make_cmap(), PiecewiseNorm()

    # 三幅图共用同一坐标范围：两套数据的并集（数据本身只覆盖 a∈[-500,1795]）
    extent = (-R_ARENA - AXIS_PAD, R_ARENA + AXIS_PAD,
              -R_ARENA - AXIS_PAD, R_ARENA + AXIS_PAD)

    f1 = os.path.join(args.out, "q2_fig1_mma_heatmap.png")
    f2 = os.path.join(args.out, "q2_fig2_pysim_heatmap.png")
    f3 = os.path.join(args.out, "q2_fig3_contour60.png")
    r1 = fig_mma_heatmap(plt, cmap, norm, extent, f1)
    r2 = fig_py_heatmap(plt, cmap, norm, extent, f2)
    r3 = fig_contour60(plt, extent, f3)
    print(f"共用坐标范围: x∈[{extent[0]:.0f},{extent[1]:.0f}] "
          f"y∈[{extent[2]:.0f},{extent[3]:.0f}]；近轴截断阈值 {CLIP_LEVEL:.0f} m\n")
    for f, r in ((f1, r1), (f2, r2), (f3, r3)):
        print(f"[OK] {os.path.basename(f):32s} {os.path.getsize(f)/1024:7.1f} KB")
        for k, v in r.items():
            print(f"       {k}: {v}")
    print(f"\n输出目录: {args.out}")


if __name__ == "__main__":
    main()
