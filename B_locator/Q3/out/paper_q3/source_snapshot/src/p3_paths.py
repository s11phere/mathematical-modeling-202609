"""本地跑几组问题 3 演练，把**路径**画出来供观察。

输出（默认 `out/p3_paths/`）：
  path_<tag>.png          每个案例一张轨迹图（真源/机器人路径/扫描点/示向度射线/定位区域）
  grid_all.png            所有案例的总览网格图（一眼看不同几何下的路径形态）
  timeline_<tag>.png      虚拟时间轴：移动/检测/清除/清理阶段的时间去哪了
  path_live_first.png     用第 1 局在线日志（protocol.jsonl）重画的路径（对照本地）

用法：
    python src/p3_paths.py                 # 默认 6 组场景
    python src/p3_paths.py --anim          # 额外生成一局的逐帧动画 GIF
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import sys
from dataclasses import replace

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

# 中文字体：Windows 上优先用雅黑/黑体，避免标签变成方块
for _f in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC",
           "WenQuanYi Zen Hei", "Arial Unicode MS"):
    if any(_f.lower() in f.name.lower() for f in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [_f] + list(plt.rcParams["font.sans-serif"])
        break
plt.rcParams["axes.unicode_minus"] = False

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))

from p3_arena import MockArena, MockSource, R_ARENA  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402
from p3_sweep import SweepConfig  # noqa: E402

OUT = os.path.join(_ROOT, "out", "p3_paths")


def live_like_sources():
    return [(2, 937.0, -782.0), (5, 363.0, 418.0), (6, -939.0, -1491.0),
            (9, 1652.0, -112.0), (10, 1606.0, -590.0), (11, -591.0, -82.0),
            (13, 18.0, -197.0), (14, 470.0, -1292.0), (18, 1024.0, 1242.0),
            (20, -316.0, 241.0)]


def annulus_sources(seed, n=12, r_lo=1300.0, r_hi=1800.0):
    rng = np.random.default_rng(seed)
    chans = rng.choice(np.arange(1, 21), size=n, replace=False)
    out = []
    for ch in chans:
        r = math.sqrt(rng.uniform(r_lo ** 2, r_hi ** 2))
        a = rng.uniform(0, 2 * math.pi)
        out.append((int(ch), r * math.cos(a), r * math.sin(a),
                    float(rng.uniform(1000.0, 1500.0))))
    return out


def scenario(name, sources=None, seed=0, note="", **cfgkw):
    """返回 (tag, note, arena, cfg)。sources 为 (ch,x,y[,r_recv]) 列表或 None（随机）。"""
    if sources is None:
        arena = MockArena(seed=seed)
    else:
        src = [MockSource(t[0], t[1], t[2], t[3] if len(t) > 3 else 1300.0)
               for t in sources]
        arena = MockArena(seed=seed, sources=src)
    return name, note, arena, SweepConfig(**cfgkw)

def scenarios():
    return [
        scenario("A_默认种子", seed=20260913,
                 note="常规随机案例（默认参数 gap=1000）"),
        scenario("B_旧参数gap450", seed=20260913, note="同一案例、旧参数 gap=450（对照）",
                 nosignal_gap_m=450.0),
        scenario("C_live复刻", sources=live_like_sources(),
                 note="把在线第 1 局的 10 个真源搬到本地（3 个源在 r>1600 m 外圈）"),
        scenario("D_外圈环带", sources=annulus_sources(100),
                 note="12 个源全部在 r∈[1300,1800] 外圈（对'发现'最不利）"),
        scenario("E_中心密集", sources=[(c, *(30.0 * (c - 10), 40.0 * ((c * 7) % 9 - 4)))
                                        for c in range(1, 13)],
                 note="12 个源挤在圆心附近（对照：几何最有利）"),
        scenario("F_无信息陷阱", sources=[(1, 1700.0, 0.0, 1000.0)],
                 note="只有 1 个源且在正东 1700 m、有效接收半径 1000 m —— 用于观察空场探索路径"),
    ]


# --------------------------------------------------------------------------
def draw_path(ax, arena, robot, rep, title, note=""):
    th = np.linspace(0, 2 * math.pi, 720)
    ax.plot(R_ARENA * np.cos(th), R_ARENA * np.sin(th), "k--", lw=0.9)
    truth = arena.truth() or {}
    for s in truth.get("sources", []):
        col = "tab:green" if s["cleared"] else "tab:red"
        ax.plot([s["x_m"]], [s["y_m"]], "o", color=col, ms=8, zorder=6)
        ax.add_patch(Circle((s["x_m"], s["y_m"]), s["r_recv_m"], fill=False,
                            ls=":", lw=0.6, color=col, alpha=0.5, zorder=1))
        ax.annotate(f"ch{s['channel']}", (s["x_m"], s["y_m"]), fontsize=7,
                    xytext=(4, 4), textcoords="offset points", zorder=7)

    acts = getattr(arena, "actions", [])
    pts = [(a["x"], a["y"]) for a in acts if a.get("kind") in ("measure", "clear")]
    if pts:
        P = np.array([[0.0, 0.0]] + pts)
        ax.plot(P[:, 0], P[:, 1], "-", color="tab:blue", lw=0.9, alpha=0.75, zorder=3)
    # 清除点单独标出
    cl = [(a["x"], a["y"]) for a in acts if a.get("kind") == "clear"
          and a.get("clear_result") == "success"]
    if cl:
        C = np.array(cl)
        ax.plot(C[:, 0], C[:, 1], "x", color="tab:red", ms=8, mew=1.6, zorder=6)

    sp = np.array(rep["scan_points"]) if rep.get("scan_points") else None
    if sp is not None and len(sp):
        up = np.unique(np.round(sp, 1), axis=0)
        ax.plot(up[:, 0], up[:, 1], "s", color="tab:orange", ms=6, zorder=5)

    for ch, rec in robot.recs.items():
        for (x, y), a in zip(rec.pts, rec.svds):
            L = 900.0
            ax.plot([x, x + L * math.cos(math.radians(a))],
                    [y, y + L * math.sin(math.radians(a))],
                    color="tab:purple", lw=0.5, alpha=0.5, zorder=2)
        # 定位区域（多边形）
        br = robot.bounded_region(rec)
        if br and br.get("poly"):
            P = np.asarray(br["poly"], float)
            ax.fill(P[:, 0], P[:, 1], color="tab:green", alpha=0.25, zorder=4)

    ax.plot([0], [0], "k*", ms=14, zorder=8)
    ax.set_aspect("equal")
    ax.set_xlim(-1950, 1950)
    ax.set_ylim(-1950, 1950)
    ax.grid(alpha=0.22)
    ax.set_title(f"{title}\n{note}\n清除 {rep['cleared']}/{rep['n_sources']}  "
                 f"虚拟时间 {rep['virtual_time_s']:.0f}s  "
                 f"平均定位清除时间 {rep['avg_clear_time_s'] or 0:.0f}s  "
                 f"检测 {rep['n_measure']} 次  行程 {rep['mock_stats']['travel_m']:.0f} m",
                 fontsize=9)


def legend_handles():
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    return [Line2D([], [], color="tab:blue", lw=1.2, label="机器狗路径"),
            Line2D([], [], ls="", marker="s", color="tab:orange", label="多频道扫描停点"),
            Line2D([], [], ls="", marker="x", color="tab:red", markeredgewidth=1.6,
                   label="成功清除点"),
            Line2D([], [], ls="", marker="o", color="tab:green", label="已清除干扰源"),
            Line2D([], [], ls="", marker="o", color="tab:red", label="未清除干扰源"),
            Line2D([], [], color="tab:purple", lw=0.8, alpha=0.7, label="示向度射线"),
            Patch(facecolor="tab:green", alpha=0.25, label="定位区域（±1°交会）"),
            Line2D([], [], ls=":", color="gray", label="有效接收半径")]


def draw_timeline(ax, arena, rep):
    acts = getattr(arena, "actions", [])
    for a in acts:
        t = a.get("virtual_time_s")
        if t is None:
            continue
        k = a.get("kind")
        if k == "measure":
            col = {"direction": "tab:red", "near": "tab:orange",
                   "no_signal": "tab:gray"}[a["measure_result"]]
            ax.barh(0, a["dt"], left=t - a["dt"], height=0.5, color=col, alpha=0.9)
        elif k == "clear":
            col = "tab:green" if a.get("clear_result") == "success" else "tab:olive"
            ax.barh(1, a["dt"], left=t - a["dt"], height=0.5, color=col, alpha=0.9)
    cl = [a["virtual_time_s"] for a in acts
          if a.get("kind") == "clear" and a.get("clear_result") == "success"]
    if cl:
        ax.plot(cl, [1.2] * len(cl), "v", color="tab:red", ms=5)
        ax.annotate(f"最后一次清除 t={cl[-1]:.0f}s（用于计算平均定位清除时间）",
                    (cl[-1], 1.2), fontsize=8, color="tab:red",
                    xytext=(6, 6), textcoords="offset points")
    if acts:
        tend = max((a.get("virtual_time_s") or 0) for a in acts)
        ax.axvline(tend, color="k", ls="--", lw=0.8)
        ax.annotate(f"收工 t={tend:.0f}s", (tend, 1.6), fontsize=8,
                    xytext=(-70, 0), textcoords="offset points")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["检测", "清除"])
    ax.set_xlabel("虚拟时间 t (s)")
    ax.set_ylim(-0.6, 1.9)
    ax.grid(alpha=0.2, axis="x")
    ax.set_title(f"时间轴：红=direction 橙=near 灰=no_signal 绿=清除成功 橄榄=未发现目标"
                 f"（{rep['n_measure']} 次检测，{rep['n_clear']} 次清除）", fontsize=9)


# --------------------------------------------------------------------------
def run_all(anim=False, policy="field", cfg_over=None, side_by_side=None):
    """``cfg_over`` 覆盖配置项（如 ``{"onlap_clear": True}``）；``side_by_side`` 给定时
    额外画一张"两套配置同案例并排"的对照图（键为 (tag, cfg_over) 的列表）。"""
    os.makedirs(OUT, exist_ok=True)
    base = load_base()
    results = []
    print(f"输出目录：{OUT}；策略 {policy}；配置覆盖 {cfg_over or {}}")
    for tag, note, arena, cfg in scenarios():
        if cfg_over:
            cfg = replace(cfg, **cfg_over)
        if policy == "sweep":
            from p3_sweep import SweepConfig, SweepRobot
            rb = SweepRobot(arena, cfg, base=base, log=None)   # cfg 里含 sweep 默认参数
        elif policy == "tour":
            from p3_tour import TourConfig, TourRobot
            tcfg = TourConfig(**{k: v for k, v in cfg.__dict__.items()
                                 if k in TourConfig.__dataclass_fields__})
            rb = TourRobot(arena, tcfg, base=base, log=None)
        else:
            rb = P3Robot(arena, cfg, base=base, log=None)
        rep = rb.run()
        rep["truth"] = arena.truth()
        rep["mock_stats"] = arena.stats
        results.append((tag, note, arena, rb, rep))

        fig, ax = plt.subplots(figsize=(9.2, 9.2))
        draw_path(ax, arena, rb, rep, f"问题3 路径：{tag}", note)
        ax.legend(handles=legend_handles(), loc="lower right", fontsize=7.5, framealpha=0.9)
        fig.tight_layout()
        p = os.path.join(OUT, f"path_{tag}.png")
        fig.savefig(p, dpi=140)
        plt.close(fig)

        fig2, ax2 = plt.subplots(figsize=(12.5, 2.6))
        draw_timeline(ax2, arena, rep)
        fig2.tight_layout()
        fig2.savefig(os.path.join(OUT, f"timeline_{tag}.png"), dpi=140)
        plt.close(fig2)

        print(f"  [{tag}] 清除 {rep['cleared']}/{rep['n_sources']}  "
              f"虚拟 {rep['virtual_time_s']:.0f}s  平均 {rep['avg_clear_time_s'] or 0:.1f}s  "
              f"检测 {rep['n_measure']}  行程 {rep['mock_stats']['travel_m']:.0f}m  -> {p}")

    # 并排对照图：同一案例、两套配置
    if side_by_side:
        pairs = side_by_side
        n = len(pairs)
        fig, axes = plt.subplots(1, n, figsize=(8.6 * n, 8.8))
        axes = np.atleast_1d(axes).ravel()
        for ax, (tag, over) in zip(axes, pairs):
            scen = {t: (no, ar, cf) for (t, no, ar, cf) in scenarios()}
            _no, arena, cfg = scen[tag]
            from dataclasses import replace as _rep
            cfg = _rep(cfg, **over)
            from p3_sweep import SweepRobot as _SR
            rb = _SR(arena, cfg, base=base, log=None)
            rep = rb.run()
            rep["truth"] = arena.truth()
            rep["mock_stats"] = arena.stats
            lab = "、".join(f"{k}={v}" for k, v in over.items()) or "默认"
            draw_path(ax, arena, rb, rep, f"{tag}｜{lab}",
                      f"清除 {rep['cleared']}/{rep['n_sources']}｜虚拟 "
                      f"{rep['virtual_time_s']:.0f}s｜平均 {rep['avg_clear_time_s'] or 0:.0f}s"
                      f"｜行程 {rep['mock_stats']['travel_m']:.0f}m")
        axes[0].legend(handles=legend_handles(), loc="lower right", fontsize=7.5,
                       framealpha=0.9)
        fig.tight_layout()
        p = os.path.join(OUT, "compare_onlap.png")
        fig.savefig(p, dpi=135)
        plt.close(fig)
        print(f"  两配置对照 -> {p}")

    # 总览网格
    n = len(results)
    cols = 3
    rows = int(math.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(6.2 * cols, 6.6 * rows))
    axes = np.atleast_1d(axes).ravel()
    for ax, (tag, note, arena, rb, rep) in zip(axes, results):
        draw_path(ax, arena, rb, rep, tag, note)
    for ax in axes[len(results):]:
        ax.axis("off")
    axes[0].legend(handles=legend_handles(), loc="lower right", fontsize=6.5, framealpha=0.9)
    fig.tight_layout()
    g = os.path.join(OUT, "grid_all.png")
    fig.savefig(g, dpi=120)
    plt.close(fig)
    print(f"  总览 → {g}")

    if anim:
        make_anim(results[0])
    return results


def make_anim(item):
    """把一局的动作序列做成逐帧 GIF（观察路径随时间的展开）。"""
    tag, note, arena, rb, rep = item
    acts = [a for a in arena.actions if a.get("kind") in ("measure", "clear")]
    if not acts:
        return
    from matplotlib.animation import FuncAnimation, PillowWriter
    fig, ax = plt.subplots(figsize=(7.4, 7.4))
    th = np.linspace(0, 2 * math.pi, 720)
    ax.plot(R_ARENA * np.cos(th), R_ARENA * np.sin(th), "k--", lw=0.9)
    truth = arena.truth() or {}
    for s in truth.get("sources", []):
        ax.plot([s["x_m"]], [s["y_m"]], "o",
                color="tab:green" if s["cleared"] else "tab:red", ms=8, zorder=6)
        ax.annotate(f"ch{s['channel']}", (s["x_m"], s["y_m"]), fontsize=7,
                    xytext=(4, 4), textcoords="offset points")
    xs = [a["x"] for a in acts]
    ys = [a["y"] for a in acts]
    ax.set_xlim(-1950, 1950); ax.set_ylim(-1950, 1950)
    ax.set_aspect("equal"); ax.grid(alpha=0.22)
    line, = ax.plot([], [], "-", color="tab:blue", lw=1.0, alpha=0.8)
    dot, = ax.plot([], [], "o", color="tab:blue", ms=6)
    tt = ax.set_title("", fontsize=10)

    def upd(i):
        line.set_data([0.0] + xs[:i + 1], [0.0] + ys[:i + 1])
        dot.set_data([xs[i]], [ys[i]])
        tt.set_text(f"{tag}  动作 {i+1}/{len(acts)}  t={acts[i]['virtual_time_s']:.0f}s  "
                    f"已清除 {sum(1 for a in acts[:i+1] if a.get('clear_result') == 'success')}"
                    f"/{rep['n_sources']}")
        return line, dot, tt

    ani = FuncAnimation(fig, upd, frames=len(acts), interval=60, blit=False)
    p = os.path.join(OUT, f"anim_{tag}.gif")
    ani.save(p, writer=PillowWriter(fps=16))
    plt.close(fig)
    print(f"  动画 → {p}")


# --------------------------------------------------------------------------
def from_live_protocol(path):
    """用在线局的 protocol.jsonl 重画路径（不依赖真值，只看机器人怎么走）。"""
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    pending = collections.defaultdict(list)
    acts = []
    for r in rows:
        k = r.get("kind")
        if k == "req":
            pending[r["path"]].append(r["payload"])
        elif k == "resp":
            p = r.get("path")
            if pending[p]:
                pl = pending[p].pop(0)
                t = r["resp"].get("virtual_time_s")
                acts.append({"kind": p.lstrip("/"), "t": t,
                             "x": (pl.get("position") or {}).get("x", 0.0),
                             "y": (pl.get("position") or {}).get("y", 0.0),
                             "ch": pl.get("channel"),
                             "res": r["resp"].get("measure_result")
                             or r["resp"].get("clear_result")})
    return acts


def draw_live(ax, acts, title):
    th = np.linspace(0, 2 * math.pi, 720)
    ax.plot(R_ARENA * np.cos(th), R_ARENA * np.sin(th), "k--", lw=0.9)
    P = np.array([[0.0, 0.0]] + [[a["x"], a["y"]] for a in acts])
    ax.plot(P[:, 0], P[:, 1], "-", color="tab:blue", lw=0.9, alpha=0.75)
    sp = np.array([[a["x"], a["y"]] for a in acts if a["kind"] == "measure"])
    if len(sp):
        up = np.unique(np.round(sp, 1), axis=0)
        ax.plot(up[:, 0], up[:, 1], "s", color="tab:orange", ms=5)
    cl = np.array([[a["x"], a["y"]] for a in acts if a["kind"] == "clear"])
    if len(cl):
        ok = np.array([[a["x"], a["y"]] for a in acts
                       if a["kind"] == "clear" and a["res"] == "success"])
        ax.plot(cl[:, 0], cl[:, 1], ".", color="tab:olive", ms=7, label="清除尝试")
        if len(ok):
            ax.plot(ok[:, 0], ok[:, 1], "x", color="tab:red", ms=9, mew=1.6,
                    label="清除成功")
    ax.plot([0], [0], "k*", ms=14)
    ax.set_aspect("equal"); ax.set_xlim(-1950, 1950); ax.set_ylim(-1950, 1950)
    ax.grid(alpha=0.22)
    tend = max(a["t"] for a in acts if a["t"] is not None)
    ax.set_title(f"{title}\n{len(acts)} 个动作  虚拟时间 {tend:.0f}s", fontsize=9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anim", action="store_true", help="额外生成逐帧动画 GIF")
    ap.add_argument("--live", action="store_true", help="额外重画两局在线日志的路径")
    ap.add_argument("--policy", choices=["field", "sweep", "tour"], default="field",
                    help="field=期望场贪心 | sweep=覆盖扫圈 | tour=统一滚动航路")
    ap.add_argument("--out-suffix", default="", help="输出目录后缀，便于两套策略并存")
    ap.add_argument("--cfg", default="", help='配置覆盖，JSON，如 {"onlap_clear":true}')
    ap.add_argument("--compare-onlap", action="store_true",
                    help="额外画一张「默认 vs 边绕边清」的同案例并排对照图")
    args = ap.parse_args()
    global OUT
    if args.out_suffix:
        OUT = OUT + args.out_suffix
    over = json.loads(args.cfg) if args.cfg else None
    side = None
    if args.compare_onlap:
        side = [("A_默认种子", {}), ("A_默认种子", {"onlap_clear": True}),
                ("C_live复刻", {"onlap_clear": True}),
                ("D_外圈环带", {"onlap_clear": True})]
    run_all(anim=args.anim, policy=args.policy, cfg_over=over, side_by_side=side)

    if args.live:
        for name, sub in (("live第1局", "live_20260911_151432"),
                          ("live第2局", "live_20260911_160404")):
            p = os.path.join(_ROOT, "out", "p3", sub, "protocol.jsonl")
            if not os.path.exists(p):
                continue
            acts = from_live_protocol(p)
            fig, ax = plt.subplots(figsize=(9.2, 9.2))
            draw_live(ax, acts, f"在线实测路径：{name}（{sub}）")
            ax.legend(loc="lower right", fontsize=8)
            fig.tight_layout()
            out = os.path.join(OUT, f"path_{name}.png")
            fig.savefig(out, dpi=140)
            plt.close(fig)
            print(f"  在线路径 → {out}")


if __name__ == "__main__":
    main()
