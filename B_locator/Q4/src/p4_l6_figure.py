"""L6 档（a=1100）的布局示意图：正六边形 + 原点，覆盖圈与 Voronoi 服务区。

    python src/p4_l6_figure.py            # -> out/p4_l6_layout.png
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from p3_arena import R_ARENA, R_RECV_MIN  # noqa: E402
from p4_paths import use_cjk_font  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402
from p4_run import _DummyArena  # noqa: E402


def main():
    use_cjk_font()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon

    for (a_side, outer, title, fname) in (
            (1100.0, (), "L6：a=1100 m，无外环（正六边形 + 原点，7 站）",
             "p4_l6_layout.png"),
            (1000.0, ((1850.0, 12),), "L0：a=1000 m + 外环1850×12（全覆盖，25 站）",
             "p4_l0_layout.png")):
        cfg = P4Config(grid_a=a_side, outer_rings=outer)
        rb = P4GridRobot(_DummyArena(), cfg)
        pts = [(0.0, 0.0)] + list(rb.stations)
        P = np.asarray(pts, float)

        fig, ax = plt.subplots(figsize=(8.2, 8.2))
        th = np.linspace(0, 2 * math.pi, 720)
        ax.plot(R_ARENA * np.cos(th), R_ARENA * np.sin(th), "k--", lw=1.1,
                label="靶区边界 R=1800 m")

        # 每个站位的 1000 m 覆盖圆（细线）
        for (x, y) in pts:
            ax.add_patch(Circle((x, y), R_RECV_MIN, fill=False,
                                ec="tab:blue", lw=0.35, alpha=0.20, zorder=1))
        # Voronoi 服务区边界用最近站着色近似
        gx = np.arange(-R_ARENA, R_ARENA + 1, 15.0)
        GX, GY = np.meshgrid(gx, gx)
        rr = np.hypot(GX, GY)
        m = rr <= R_ARENA
        D = np.sqrt((GX[..., None] - P[None, None, :, 0]) ** 2
                    + (GY[..., None] - P[None, None, :, 1]) ** 2)
        who = np.argmin(D, axis=-1).astype(float)
        who[~m] = np.nan
        ax.contourf(GX, GY, who, levels=np.arange(-0.5, len(pts) + 0.5, 1.0),
                    cmap="tab20", alpha=0.16, zorder=0)

        # 扫描航线（绕圈）
        sk = list(rb.spiral_tour())
        st = rb.stations
        cur = np.asarray((0.0, 0.0), float)
        xs, ys, d = [0.0], [0.0], 0.0
        for si in sk:
            q = np.asarray(st[si], float)
            d += float(np.hypot(*(q - cur)))
            xs.append(q[0])
            ys.append(q[1])
            cur = q
        if len(xs) > 2:
            xs.append(0.0)
            ys.append(0.0)
            d += float(np.hypot(*(np.asarray((0.0, 0.0)) - cur)))
        ax.plot(xs, ys, "-", color="tab:red", lw=1.4, alpha=0.85, zorder=3,
                label=f"扫描航线（绕圈，{d:.0f} m）")

        ax.plot(P[1:, 0], P[1:, 1], "^", color="tab:orange", ms=11,
                markeredgecolor="k", markeredgewidth=0.6, zorder=5,
                label=f"扫描站位（{len(pts)-1} 个 + 原点）")
        ax.plot([0], [0], "k*", ms=17, zorder=6, label="起点/原点站位")
        for k, (x, y) in enumerate(pts):
            ax.annotate(f"{k}", (x, y), fontsize=8, xytext=(6, 6),
                        textcoords="offset points", zorder=7)

        ax.set_aspect("equal")
        ax.set_xlim(-1960, 1960)
        ax.set_ylim(-1960, 1960)
        ax.grid(alpha=0.18, lw=0.5)
        ax.set_title(f"{title}\n每个站位画了它 1000 m 的'有效接收半径下界'覆盖圈；"
                     f"底色 = 最近站位的服务区", fontsize=9.5)
        ax.legend(loc="upper right", fontsize=8)
        fig.tight_layout()
        out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "out", fname)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"-> {out}")


if __name__ == "__main__":
    main()
