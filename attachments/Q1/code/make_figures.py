"""由算例和几何求解器重绘问题一的三幅正文图。"""
from pathlib import Path
import csv
import os
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "b-locator-mpl"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, FancyBboxPatch, Polygon
import numpy as np

import p1_intersection as P
import p1_experiments as E

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent / "paper"
OUT = PAPER / "figures"
BLUE, RED, ORANGE = "#2463a5", "#b73432", "#cc6500"


def setup():
    font = PAPER / "fonts" / "simsun.ttc"
    if font.exists():
        font_manager.fontManager.addfont(font)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update({"font.size": 11, "mathtext.fontset": "stix",
                         "axes.unicode_minus": False, "savefig.dpi": 300})
    OUT.mkdir(parents=True, exist_ok=True)


def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def draw_region(ax, vertices, labels=True):
    D, (A, B) = P.diameter(vertices)
    M = (A + B) / 2
    ax.add_patch(Polygon(vertices, facecolor="#f2d0ce", edgecolor=RED, lw=1.5))
    ax.add_patch(Circle(M, D / 2, fill=False, color=BLUE, lw=1.5))
    ax.plot([A[0], B[0]], [A[1], B[1]], "k-", lw=1.2)
    ax.scatter(*np.array([A, B]).T, facecolor="white", edgecolor="black", zorder=5)
    ax.plot(*M, "k+", ms=9, mew=1.2)
    if labels:
        for name, point in (("A", A), ("B", B), ("M", M)):
            ax.annotate(f"${name}$", point, xytext=(5, 5), textcoords="offset points")
    ax.set_aspect("equal")
    ax.set_xlim(M[0] - 0.74 * D, M[0] + 0.74 * D)
    ax.set_ylim(M[1] - 0.74 * D, M[1] + 0.74 * D)
    return D, A, B, M


def coverage():
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 4.2), constrained_layout=True)
    for i, ax in enumerate(axes, 1):
        with (HERE / "cases" / f"p1_case{i:02d}.csv").open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        points = [(float(r["x_m"]), float(r["y_m"])) for r in rows]
        bearings = [float(r["svd_deg"]) for r in rows]
        vertices, _ = P.region_from_bearings(points, bearings)
        D, A, B, M = draw_region(ax, vertices)
        full = E.solve_full(points, bearings)
        status = "覆盖成立" if full["covers"] else "覆盖不成立"
        ax.set_title(f"({'ab'[i-1]}) $A_{i}$：{status}\n"
                     f"$D={D:.2f}$ m，$\\max |P-M|={full['max_vertex_dist']:.2f}$ m",
                     fontsize=11, color=BLUE if full["covers"] else ORANGE)
        if not full["covers"]:
            worst = vertices[np.argmax(np.linalg.norm(vertices - M, axis=1))]
            ax.plot([M[0], worst[0]], [M[1], worst[1]], "--", color=ORANGE)
            ax.scatter(*worst, s=55, facecolor="white", edgecolor=ORANGE, zorder=6)
            ax.annotate(f"$P$（${full['worst_vertex_angle_deg']:.1f}^\\circ$）", worst,
                        xytext=(-15, -22), textcoords="offset points", color=ORANGE)
        ax.set_xlabel("$x$ / m")
        ax.set_ylabel("$y$ / m")
        ax.tick_params(labelsize=9)
    save(fig, "p1-coverage-contrast.png")


def flowchart():
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.set(xlim=(0, 10), ylim=(0, 6.8))
    ax.axis("off")
    steps = [(6.2, "输入检测点与示向度"),
             (5.05, "边界交点枚举、半平面筛选、凸包"),
             (3.9, "检查公共延伸方向"),
             (2.75, "检查顶点数"),
             (1.6, "枚举最远顶点对，求 $D$ 与 $M$"),
             (0.45, r"比较 $\max_{P\in V}|P-M|$ 与 $D/2$，输出覆盖判定")]
    for y, label in steps:
        ax.add_patch(FancyBboxPatch((0.6, y - 0.36), 6.4, 0.72,
                     boxstyle="round,pad=0.05", facecolor="#edf3f8", edgecolor=BLUE))
        ax.text(3.8, y, label, ha="center", va="center", fontsize=11)
    for (y1, _), (y2, _) in zip(steps, steps[1:]):
        ax.annotate("", (3.8, y2 + 0.39), (3.8, y1 - 0.39),
                    arrowprops={"arrowstyle": "->", "color": BLUE})
    for y, label in [(5.05, "无交点：空集"), (3.9, "存在：无界"), (2.75, "少于 3：退化")]:
        ax.annotate("", (7.9, y), (7.07, y), arrowprops={"arrowstyle": "->"})
        ax.text(8.05, y, label, ha="left", va="center", fontsize=10)
    save(fig, "p1-algorithm-flow.png")


def wedge_diagram():
    T = np.array([0.0, 0.0])
    sensors = np.array([[-900., -250.], [700., -450.], [300., 850.]])
    bearings = [P.bearing(s, T) for s in sensors]
    vertices, _ = P.region_from_bearings(sensors, bearings)
    fig, ax = plt.subplots(figsize=(8.1, 5.7))
    ax.set(xlim=(-1200, 1200), ylim=(-900, 1100), xlabel="$x$ / m", ylabel="$y$ / m")
    ax.set_aspect("equal")
    for i, (s, theta, color) in enumerate(zip(sensors, bearings, [BLUE, ORANGE, "#49864e"]), 1):
        angles = np.deg2rad([theta - P.BEARING_ERR, theta + P.BEARING_ERR])
        ends = s + 2200 * np.column_stack([np.cos(angles), np.sin(angles)])
        ax.add_patch(Polygon(np.vstack([s, ends]), facecolor=color, alpha=0.15))
        for end in ends:
            ax.plot([s[0], end[0]], [s[1], end[1]], color=color, lw=0.8)
        central = s + 2200 * np.array([np.cos(np.deg2rad(theta)), np.sin(np.deg2rad(theta))])
        ax.plot([s[0], central[0]], [s[1], central[1]], color=color, lw=.6, ls='--')
        ax.scatter(*s, color=color, s=30, zorder=4)
        ax.annotate(f"$S_{i}$", s, xytext=(6, 6), textcoords="offset points", color=color)
    ax.scatter(*T, color=RED, s=18, zorder=6)
    ax.annotate("$T$", T, xytext=(-12, 8), textcoords="offset points")
    ax.add_patch(Polygon(vertices, facecolor=RED, edgecolor=RED))
    inset = ax.inset_axes([1.02, 0.08, 0.46, 0.46])
    draw_region(inset, vertices, labels=False)
    inset.patches[0].set_facecolor((.95, .82, .81, .25))
    for s, theta, color in zip(sensors, bearings, [BLUE, ORANGE, '#49864e']):
        angles = np.deg2rad([theta - P.BEARING_ERR, theta + P.BEARING_ERR])
        ends = s + 2200 * np.column_stack([np.cos(angles), np.sin(angles)])
        inset.add_patch(Polygon(np.vstack([s, ends]), facecolor=color, alpha=.10, zorder=0))
        for end in ends:
            inset.plot([s[0], end[0]], [s[1], end[1]], color=color, lw=.8, zorder=1)
        central = s + 2200 * np.array([np.cos(np.deg2rad(theta)), np.sin(np.deg2rad(theta))])
        inset.plot([s[0], central[0]], [s[1], central[1]], color=color, lw=.6, ls='--', zorder=1)
    inset.plot(*T, marker='.', color=RED, zorder=6)
    for i, v in enumerate(vertices, 1):
        inset.annotate(f"$V_{i}$", v, xytext=(3, 4), textcoords="offset points", fontsize=8)
    _, (A, B) = P.diameter(vertices)
    inset.annotate("$M$", (A + B) / 2, xytext=(4, 4), textcoords="offset points", fontsize=9)
    inset.set_title("定位区域局部放大", fontsize=10)
    inset.tick_params(labelsize=7)
    ax.indicate_inset_zoom(inset, edgecolor="gray", alpha=0.65)
    ax.tick_params(labelsize=9)
    save(fig, "multi_sensor_wedge_diagram.png")


def main():
    setup()
    coverage()
    flowchart()
    wedge_diagram()
    print(f"问题一正文图已生成：{OUT}")


if __name__ == "__main__":
    main()
