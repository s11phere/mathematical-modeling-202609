"""问题 4：把演练局的实际路径画出来（逐相位着色 + 逐局指标）。

用户的诉求："给出一些测试案例的实际路径"。

    python src/p4_paths.py                       # 6 个代表场景 + 总览图
    python src/p4_paths.py --anim                # 额外生成逐帧动画 GIF（第一组）
    python src/p4_paths.py --cases 10            # 额外画 10 局随机定向案例的路径
    python src/p4_paths.py --out out/p4_paths

每张图包含：
* **橙色三角** = 三角形格网站位（未去的空心、去过的实心）；
* 路径按**相位**着色（下方图例）：
  蓝 = 扫描移动、青 = 顺路清除、紫 = 定位侧移/二分、红 = 覆盖式试探、绿点 = 清除成功；
* 紫色细线 = 每条频道的实测示向度射线；红/绿圆点 = 未清除/已清除的真源；
  黑虚线圆 = 靶区边界 R=1800 m。

同目录还会输出 `paths_summary.csv` / `.json`（逐局指标）与
`timeline_*.png`（虚拟时间轴：每个动作的相位与结果）。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from p3_arena import MockArena, MockSource, R_ARENA  # noqa: E402
from p4_arena_ext import directed_case  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402


def use_cjk_font():
    """让图上能显示中文（Windows 自带字体；找不到就退回默认并只影响文字外观）。"""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC",
                 "Source Han Sans SC", "DengXian"):
        if name in have:
            matplotlib.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return name
    return None


CJK_FONT = use_cjk_font()

# 路径着色（相位）
COLORS = {
    "scan": "#1f77b4",       # 扫描：走到下一站的移动
    "enroute": "#17becf",    # 顺路清除（扫描途中）
    "locate": "#9467bd",     # 定位：沿视线二分 / 侧移交会
    "probe": "#d62728",      # 覆盖式试探（/clear 未命中）
    "success": "#2ca02c",    # 清除成功
    "other": "#7f7f7f",
}
LABEL = {
    "scan": "扫描移动（走到下一站）",
    "enroute": "顺路清除（扫描途中）",
    "locate": "定位（沿视线二分 / 侧移交会）",
    "probe": "覆盖式试探（未命中）",
    "success": "清除成功",
    "other": "其它",
}


# --------------------------------------------------------------------------
# 复刻一局并记录"每个动作属于哪个相位"
# --------------------------------------------------------------------------
def phase_classifier(events):
    """由机器人事件流重建"某时刻处于哪个相位"。

    ``events`` 是 ``P4GridRobot.events``（``{"t": 虚拟时刻, "msg": 文本}``）。
    每个动作的虚拟时刻与事件时刻一一对应（事件是在动作前后打的），
    所以按时间轴扫描事件、记住最近一次出现的"相位关键词"即可。
    """
    marks = []
    for e in sorted(events, key=lambda x: x["t"]):
        m = e.get("msg", "")
        if "覆盖式试探" in m:
            ph = "probe"
        elif "顺路清除" in m:
            ph = "enroute"
        elif ("定位频道" in m or "侧移" in m or "沿视线" in m
              or "二分" in m or "再取一条方位" in m):
            ph = "locate"
        elif "站位" in m or "第 0 站" in m or "扫描第" in m or "扫描航线" in m:
            ph = "scan"
        else:
            continue
        marks.append((float(e["t"]), ph))

    def classify(t):
        ph = "scan"
        for (tt, p) in marks:
            if tt <= float(t) + 1e-6:
                ph = p
            else:
                break
        return ph
    return classify


def run_case(label, arena, cfg=None, verbose=False):
    rb = P4GridRobot(arena, cfg or P4Config(),
                     log=(lambda m: print("   " + m)) if verbose else None)
    rep = rb.run()
    classify = phase_classifier(rb.events)
    acts = []
    prev = (0.0, 0.0)
    for a in arena.actions:
        if a.get("kind") not in ("measure", "clear") or "x" not in a:
            continue
        t = float(a["virtual_time_s"])
        kind = a["kind"]
        res = a.get("measure_result") or a.get("clear_result") or ""
        if kind == "clear" and res == "success":
            ph = "success"
        else:
            ph = classify(t)
        acts.append({
            "kind": kind, "x": float(a["x"]), "y": float(a["y"]), "t": t,
            "res": res, "phase": ph, "ch": a.get("channel"),
            "step": float(math.hypot(a["x"] - prev[0], a["y"] - prev[1])),
        })
        prev = (float(a["x"]), float(a["y"]))
    out = {
        "label": label,
        "rep": rep,
        "robot": rb,
        "arena": arena,
        "acts": acts,
        "n_directed": sum(1 for s in arena.sources if s.cone_half < 180.0),
        "truth": [(s.channel, s.x, s.y, s.cone_half < 180.0, s.dir_deg, s.cleared)
                  for s in arena.sources],
        "stations": list(rb.stations),
        "visited": sorted(rb.visited_stations),
        "classify": classify,
    }
    return out


# --------------------------------------------------------------------------
# 画图
# --------------------------------------------------------------------------
def _setup_ax(ax, title):
    import matplotlib.pyplot as plt  # noqa: F401
    th = np.linspace(0, 2 * math.pi, 720)
    ax.plot(R_ARENA * np.cos(th), R_ARENA * np.sin(th), "k--", lw=1.0, alpha=0.8)
    ax.set_aspect("equal")
    ax.set_xlim(-1980, 1980)
    ax.set_ylim(-1980, 1980)
    ax.grid(alpha=0.2, lw=0.5)
    ax.set_title(title, fontsize=9)
    ax.tick_params(labelsize=7)


def plot_path(case, path, figsize=(8.6, 8.6), show_dpi=150):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    fig, ax = plt.subplots(figsize=figsize)
    rep = case["rep"]
    _setup_ax(ax, "")

    # ---- 站位 ----
    st = np.asarray(case["stations"], float).reshape(-1, 2)
    vis = set(case["visited"])
    if st.size:
        unv = np.array([st[i] for i in range(len(st)) if i not in vis]) \
            if len(vis) < len(st) else np.zeros((0, 2))
        ax.plot(st[:, 0], st[:, 1], "^", color="tab:orange", ms=4.5, alpha=0.35,
                label="格网站位（未访问）")
        if unv.size:
            ax.plot(unv[:, 0], unv[:, 1], "^", color="tab:orange", ms=4.5,
                    alpha=0.35)
        vp = np.array([st[i] for i in sorted(vis)]) if vis else np.zeros((0, 2))
        if vp.size:
            ax.plot(vp[:, 0], vp[:, 1], "^", color="tab:orange", ms=8.5,
                    markeredgecolor="k", markeredgewidth=0.4,
                    label="格网站位（已访问）")

    # ---- 示向度射线 ----
    for ch, rec in case["robot"].recs.items():
        for (x, y), a in zip(rec.pts, rec.svds):
            L = 900.0
            ax.plot([x, x + L * math.cos(math.radians(a))],
                    [y, y + L * math.sin(math.radians(a))],
                    color="tab:purple", lw=0.5, alpha=0.35, zorder=2)

    # ---- 路径（按相位分段着色）----
    acts = case["acts"]
    if acts:
        P = np.array([[0.0, 0.0]] + [[a["x"], a["y"]] for a in acts])
        seg_phase = ["scan"] + [a["phase"] for a in acts]
        drawn = set()
        for i in range(len(P) - 1):
            ph = seg_phase[i + 1]
            ax.plot(P[i:i + 2, 0], P[i:i + 2, 1], "-", color=COLORS[ph],
                    lw=1.0, alpha=0.85, zorder=3,
                    label=(LABEL[ph] if ph not in drawn else None))
            drawn.add(ph)

    # ---- 真源 ----
    for (ch, x, y, is_dir, ddir, cleared) in case["truth"]:
        col = "tab:green" if cleared else "tab:red"
        ax.plot([x], [y], "o", color=col, ms=8, zorder=6,
                markeredgecolor="k", markeredgewidth=0.5)
        ax.annotate(f"{ch}{'D' if is_dir else ''}", (x, y), fontsize=7.5,
                    xytext=(4, 4), textcoords="offset points", zorder=7)
        if is_dir and ddir is not None:
            # 实测确认（review/p4_dir_semantics.py）：模拟器里"能听到源的那一侧"
            # 是 dir_deg 的**反面** —— 所以图上画两条：
            #   粗红箭头 = 源实际可被听到的波束朝向（= dir_deg + 180°，与射线一致）
            #   细灰箭头 = 协议原样给出的 dir_deg 数值（容易误读，仅作对照）
            L = 300.0
            beam = (float(ddir) + 180.0) % 360.0
            ax.annotate("", xy=(x + L * math.cos(math.radians(beam)),
                                y + L * math.sin(math.radians(beam))),
                        xytext=(x, y),
                        arrowprops=dict(arrowstyle="-|>", color="tab:red",
                                        lw=1.8, alpha=0.95), zorder=6)
            L2 = 200.0
            ax.annotate("", xy=(x + L2 * math.cos(math.radians(ddir)),
                                y + L2 * math.sin(math.radians(ddir))),
                        xytext=(x, y),
                        arrowprops=dict(arrowstyle="-|>", color="0.45",
                                        lw=0.9, ls=(0, (3, 2)), alpha=0.8),
                        zorder=5)
    ax.plot([], [], "o", color="tab:green", label="真源（已清除）")
    ax.plot([], [], "o", color="tab:red", label="真源（未清除）")
    ax.plot([], [], "-", color="tab:red", lw=2.0,
            label="定向源**可被听到**的波束方向（= dir_deg+180°）")
    ax.plot([], [], "--", color="0.45", lw=1.0,
            label="协议给出的 dir_deg 原值（对照用）")

    ax.plot([0], [0], "k*", ms=15, zorder=8, label="起点 (0,0)")

    title = (f"{case['label']}｜真源 {rep['n_sources']}（定向 {case['n_directed']}）"
             f"｜清除 {rep['cleared']}/{rep['n_sources']}"
             f"｜平均定位清除 {rep['avg_clear_time_s'] or 0:.0f} s"
             f"｜虚拟 {rep['virtual_time_s']:.0f} s")
    sub = (f"行程 {rep['travel_m']:.0f} m｜检测 {rep['n_measure']} 次｜"
           f"访问站位 {len(case['visited'])}/{len(case['stations'])}"
           f"｜定向源：粗红箭头=可被听到的一侧，灰虚线=dir_deg 原值（两者相差 180°）")
    ax.set_title(title + "\n" + sub, fontsize=9)
    ax.legend(loc="upper right", fontsize=7.5, framealpha=0.9)
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=show_dpi)
    plt.close(fig)
    return path


def plot_timeline(case, path):
    """虚拟时间轴：横轴 = 虚拟时刻，纵轴 = 相位；点形/颜色标出动作结果。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    acts = case["acts"]
    fig, ax = plt.subplots(figsize=(11.0, 3.2))
    rows = {"scan": 4, "enroute": 3, "locate": 2, "probe": 1, "success": 0}
    for a in acts:
        ax.plot([a["t"]], [rows.get(a["phase"], 5)], "o", ms=2.6,
                color=COLORS.get(a["phase"], "#888"))
    for ch, rec in case["robot"].recs.items():
        if rec.cleared and rec.cleared_at:
            ax.axvline(rec.cleared_at, color="tab:green", lw=0.7, alpha=0.55)
    ax.set_yticks([0, 1, 2, 3, 4])
    ax.set_yticklabels(["清除成功", "覆盖式试探", "定位", "顺路清除", "扫描"], fontsize=8)
    ax.set_xlabel("虚拟时刻 (s)", fontsize=8)
    ax.set_title(f"{case['label']}：动作时间轴（绿竖线 = 某个源被清除的时刻）", fontsize=9)
    ax.grid(alpha=0.25, axis="x")
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_grid(cases, paths, out_path):
    """总览：把每张路径图拼成 2×3 网格。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg

    n = len(cases)
    ncol = 3
    nrow = int(math.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(7.2 * ncol, 7.4 * nrow))
    axes = np.atleast_1d(axes).ravel()
    for i, p in enumerate(paths):
        axes[i].imshow(mpimg.imread(p))
        axes[i].axis("off")
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.suptitle("问题 4：三角形格网扫描——6 个案例的实际路径"
                 "（蓝=扫描 青=顺路清除 紫=定位 红=试探 绿=清除成功）",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------
# 场景
# --------------------------------------------------------------------------
def scenarios():
    """6 个代表场景（覆盖"最好 / 最难 / 全向对照 / 外圈 / 中心 / 单个贴边"）。"""
    out = []
    # A 常规随机（定向/全向各半）
    arena, srcs = directed_case(seed=20260914, n=14, directed_frac=0.5)
    out.append(("A_常规随机14源", arena))
    # B 全部定向（最难）
    arena, srcs = directed_case(seed=20261114, n=13, directed_frac=1.0)
    out.append(("B_全定向13源", arena))
    # C 定向源偏外圈（贴边朝外）
    rng = np.random.default_rng(7)
    srcs = []
    for i, ch in enumerate([2, 5, 7, 11, 14, 17, 19]):
        r = math.sqrt(rng.uniform(1550.0 ** 2, 1790.0 ** 2))
        a = float(rng.uniform(0, 2 * math.pi))
        srcs.append(MockSource(int(ch), r * math.cos(a), r * math.sin(a),
                               float(rng.uniform(1000.0, 1400.0)),
                               cone_half=90.0,
                               dir_deg=math.degrees(a) % 360.0))
    out.append(("C_外圈贴边朝外7源", MockArena(seed=907, sources=srcs,
                                             budget_s=360000.0)))
    # D 全向对照
    arena, srcs = directed_case(seed=20260914, n=14, directed_frac=0.0)
    out.append(("D_全向对照14源", arena))
    # E 源全挤在中心附近（最好情况）
    rng = np.random.default_rng(31)
    srcs = []
    for i, ch in enumerate([1, 3, 4, 6, 8, 10, 12]):
        r = float(rng.uniform(0, 500.0))
        a = float(rng.uniform(0, 2 * math.pi))
        sd = float(rng.uniform(0, 360.0))
        srcs.append(MockSource(int(ch), r * math.cos(a), r * math.sin(a),
                               float(rng.uniform(1000.0, 1500.0)),
                               cone_half=90.0, dir_deg=sd))
    out.append(("E_中心密集7源", MockArena(seed=411, sources=srcs,
                                          budget_s=360000.0)))
    # F 单个贴边朝外的定向源（历史上最难的那一个）
    srcs = [MockSource(9, 1500.0, -168.0, 1400.0, cone_half=90.0,
                       dir_deg=math.degrees(math.atan2(-168.0, 1500.0)) % 360.0)]
    out.append(("F_单个贴边朝外1源", MockArena(seed=77, sources=srcs,
                                             budget_s=360000.0)))
    return out


def random_cases(n=10, seed=20261014, scenario="directed"):
    out = []
    for i in range(n):
        arena, _ = directed_case(seed + 100 * i, directed_frac=0.5)
        out.append((f"R{i+1}_随机{scenario}", arena))
    return out


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(_ROOT, "out", "p4_paths"))
    ap.add_argument("--cases", type=int, default=0, help="额外画 N 局随机案例")
    ap.add_argument("--anim", action="store_true", help="生成逐帧动画 GIF（第一组）")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    rows = []
    cases = scenarios()
    if a.cases:
        cases += random_cases(a.cases)

    def safe(name):
        return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)

    paths = []
    t0 = time.time()
    for (label, arena) in cases:
        case = run_case(label, arena, verbose=a.verbose)
        rep = case["rep"]
        p = plot_path(case, os.path.join(a.out, f"path_{safe(label)}.png"))
        plot_timeline(case, os.path.join(a.out, f"timeline_{safe(label)}.png"))
        paths.append(p)
        # 逐相位行程
        seg = {}
        for act in case["acts"]:
            seg[act["phase"]] = seg.get(act["phase"], 0.0) + act["step"]
        rows.append({
            "case": label, "n_sources": rep["n_sources"],
            "n_directed": case["n_directed"], "cleared": rep["cleared"],
            "clear_ratio": round(rep["cleared"] / max(rep["n_sources"], 1), 4),
            "avg_clear_time_s": round(rep["avg_clear_time_s"] or 0.0, 1),
            "virtual_time_s": round(rep["virtual_time_s"], 1),
            "travel_m": round(rep["travel_m"], 0),
            "n_measure": rep["n_measure"],
            "stations_visited": len(case["visited"]),
            "stations_total": len(case["stations"]),
            "travel_scan_m": round(seg.get("scan", 0.0), 0),
            "travel_locate_m": round(seg.get("locate", 0.0), 0),
            "travel_probe_m": round(seg.get("probe", 0.0), 0),
            "n_locate": rep.get("n_locate", 0), "n_clear": rep["n_clear"],
            "n_clear_fail": rep["n_clear_fail"],
        })
        print(f"  {label:<16} 清除 {rep['cleared']:>2}/{rep['n_sources']:<2}"
              f" 平均 {rep['avg_clear_time_s'] or 0:>6.0f} s"
              f" 虚拟 {rep['virtual_time_s']:>6.0f} s"
              f" 行程 {rep['travel_m']:>6.0f} m"
              f" 站位 {len(case['visited'])}/{len(case['stations'])}", flush=True)

    if len(paths) > 1:
        plot_grid(cases, paths, os.path.join(a.out, "grid_all.png"))

    with open(os.path.join(a.out, "paths_summary.csv"), "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(a.out, "paths_summary.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    if a.anim:
        try:
            make_anim(cases[0], os.path.join(a.out, f"anim_{safe(cases[0][0])}.gif"))
        except Exception as e:      # 动画失败不影响主输出
            print(f"  [warn] 动画生成失败：{e!r}")

    print(f"\n共 {len(cases)} 局，用时 {time.time() - t0:.1f} s")
    print(f"输出目录：{a.out}")
    print(f"  逐局路径图 path_*.png / 时间轴 timeline_*.png"
          f"{' / 总览 grid_all.png' if len(paths) > 1 else ''}")
    print("  paths_summary.csv / paths_summary.json")


def make_anim(case, path, fps=6):
    """逐帧动画：把动作序列逐条画出来（第一组场景）。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter

    acts = case["acts"][:400]
    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    _setup_ax(ax, case["label"])

    def frame(i):
        ax.clear()
        _setup_ax(ax, f"{case['label']}  t={acts[i]['t']:.0f} s")
        st = np.asarray(case["stations"], float).reshape(-1, 2)
        ax.plot(st[:, 0], st[:, 1], "^", color="tab:orange", ms=4, alpha=0.25)
        for (ch, x, y, is_dir, ddir, cleared) in case["truth"]:
            ax.plot([x], [y], "o", ms=7, color="tab:green" if cleared else "tab:red",
                    zorder=6)
        P = np.array([[0.0, 0.0]] + [[q["x"], q["y"]] for q in acts[:i + 1]])
        seg = ["scan"] + [q["phase"] for q in acts[:i + 1]]
        for k in range(len(P) - 1):
            ax.plot(P[k:k + 2, 0], P[k:k + 2, 1], "-", color=COLORS[seg[k + 1]],
                    lw=1.0, alpha=0.85, zorder=3)
        ax.plot(P[-1, 0], P[-1, 1], "o", color="k", ms=5, zorder=8)
        return []

    anim = FuncAnimation(fig, frame, frames=len(acts), interval=1000 / fps)
    anim.save(path, writer=PillowWriter(fps=fps))
    plt.close(fig)
    print(f"  动画：{path}")


if __name__ == "__main__":
    main()
