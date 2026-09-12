"""B 题第三问：**独立复核** + 路径图（`tour` / `adaptive` / `joint` 同场景并排）。

本脚本刻意不复用策略自己的统计口径，只做三件事：

1. **台账重算**：从 arena 的原始动作记录（`arena.actions`）按附件 1/2 的计时规则
   重新累加虚拟时间、行程、检测/清除次数，再与策略汇报值逐条比对；
2. **公平性断言**：同一 seed 下各策略必须拿到**同一个场景**（源位/接收半径逐字段相等），
   且运行期间**不许读真值**（`truth()` 在 `/exit` 前被调用即抛错）；
3. **路径图**：同场景并排画各策略的航路、检测结果与清除点。

用法（项目根目录）::

    python B_locator/Q3/src/p3_verify_paths.py                     # 三策略 × 7 个案例
    python B_locator/Q3/src/p3_verify_paths.py --policies tour,joint --cases 2
    python B_locator/Q3/src/p3_verify_paths.py --coverage-audit 20 --coverage-policy joint
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import replace

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

from p3_adaptive import AdaptiveConfig, AdaptiveRobot  # noqa: E402
from p3_adaptive_bench import make_scene  # noqa: E402
from p3_arena import (R_ARENA, T_CLEAR_FAIL, T_CLEAR_OK, T_MEASURE,  # noqa: E402
                      T_SWITCH, V_ROBOT)
from p3_bench import run_one  # noqa: E402
from p3_joint import JointConfig, JointRobot  # noqa: E402
from p3_robot import load_base  # noqa: E402
from p3_tour import TourConfig, TourRobot  # noqa: E402

_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
OUT = os.path.join(_ROOT, "out", "p3_verify")

ALL_POLICIES = (("tour", TourRobot, TourConfig),
                ("adaptive", AdaptiveRobot, AdaptiveConfig),
                ("joint", JointRobot, JointConfig))
POLICIES = ALL_POLICIES          # 运行期由 --policies 裁剪


def _setup_font():
    for cand in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        if os.path.exists(cand):
            from matplotlib.font_manager import FontProperties
            plt.rcParams["font.family"] = FontProperties(fname=cand).get_name()
            break
    plt.rcParams.update({"axes.unicode_minus": False, "axes.spines.top": False,
                         "axes.spines.right": False, "font.size": 9})


# --------------------------------------------------------------------------
# 1) 与策略无关的台账重算
# --------------------------------------------------------------------------
def audit_trace(arena):
    """按附件 1/2 的计时规则，从原始动作记录重算一遍。"""
    px = py = 0.0
    ch_state = 1                      # 机器狗进入靶区时测向机在频道 1
    vtime = travel = 0.0
    t_travel = t_meas = t_switch = t_clear = 0.0
    n_meas = n_clear = n_ok = 0
    res_count = {"direction": 0, "near": 0, "no_signal": 0}
    max_dt_err = max_dist_err = 0.0
    for a in arena.actions:
        kind = a.get("kind")
        if kind not in ("measure", "clear"):
            continue
        d = math.hypot(a["x"] - px, a["y"] - py)
        max_dist_err = max(max_dist_err, abs(d - a["dist_m"]))
        px, py = a["x"], a["y"]
        travel += d
        t_travel += d / V_ROBOT
        if kind == "measure":
            switch = T_SWITCH if int(a["channel"]) != ch_state else 0.0
            ch_state = int(a["channel"])
            dt = d / V_ROBOT + switch + T_MEASURE
            n_meas += 1
            res_count[a["measure_result"]] = res_count.get(a["measure_result"], 0) + 1
            t_switch += switch
            t_meas += T_MEASURE
        else:
            ok = a.get("clear_result") == "success"
            dt = d / V_ROBOT + (T_CLEAR_OK if ok else T_CLEAR_FAIL)
            n_clear += 1
            n_ok += int(ok)
            t_clear += T_CLEAR_OK if ok else T_CLEAR_FAIL
        max_dt_err = max(max_dt_err, abs(dt - a["dt"]))
        vtime += dt
    return {"vtime_s": vtime, "travel_m": travel, "n_measure": n_meas,
            "n_clear": n_clear, "n_clear_ok": n_ok, "results": res_count,
            "t_travel_s": t_travel, "t_measure_s": t_meas, "t_switch_s": t_switch,
            "t_clear_s": t_clear, "max_dt_err_s": max_dt_err,
            "max_dist_err_m": max_dist_err}


def block_truth(arena):
    """把 `truth()` 包一层：`/exit` 之前被调用就抛错（策略偷看真值的探针）。"""
    real = arena.truth
    state = {"calls": 0}

    def guard():
        state["calls"] += 1
        if not arena.finished:
            raise AssertionError("策略在 /exit 之前读取了真值")
        return real()

    arena.truth = guard                                     # 实例属性遮蔽方法
    return state


def scene_key(arena):
    """场景指纹：只看源位与接收半径，不看清除状态。"""
    return tuple(sorted((s.channel, round(s.x, 9), round(s.y, 9), round(s.r_recv, 9))
                        for s in arena.sources))


def run_pair(kind, seed, base):
    """同一场景分别交给两种策略跑，返回 {policy: {...}}。"""
    out, keys = {}, []
    for name, cls, cfg_cls in POLICIES:
        arena = make_scene(kind, seed)
        keys.append(scene_key(arena))
        probe = block_truth(arena)
        rep = run_one(cls, cfg_cls(), arena, base, want_path=True)
        out[name] = {"arena": arena, "rep": rep, "audit": audit_trace(arena),
                     "truth": arena.truth(), "truth_calls": probe["calls"]}
    if len(set(keys)) != 1:
        raise AssertionError(f"{kind}/{seed}：各策略拿到的场景不一致")
    return out


# --------------------------------------------------------------------------
# 2) 绘图
# --------------------------------------------------------------------------
def draw_panel(ax, arena, rep, audit, title, cmap_range=None, predicate="覆盖证书"):
    th = np.linspace(0, 2 * math.pi, 721)
    ax.plot(R_ARENA * np.cos(th), R_ARENA * np.sin(th), color="#9aa3ad",
            ls="--", lw=1.0, zorder=1)
    for s in (arena.truth() or {}).get("sources", []):
        col = "#2e8b57" if s["cleared"] else "#c0392b"
        ax.add_patch(Circle((s["x_m"], s["y_m"]), s["r_recv_m"], fill=False,
                            ls=":", lw=0.5, color=col, alpha=0.4, zorder=1))
        ax.plot([s["x_m"]], [s["y_m"]], marker="*", ms=13, color=col,
                mec="white", mew=0.6, zorder=7)
        ax.annotate(f"ch{s['channel']}", (s["x_m"], s["y_m"]), xytext=(5, 4),
                    textcoords="offset points", fontsize=7, color=col, zorder=8)

    acts = [a for a in arena.actions if a.get("kind") in ("measure", "clear")]
    if acts:
        pts = np.array([[0.0, 0.0]] + [[a["x"], a["y"]] for a in acts])
        ts = np.array([0.0] + [a["virtual_time_s"] for a in acts])
        segs = np.stack([pts[:-1], pts[1:]], axis=1)
        lo, hi = (cmap_range or (0.0, float(ts[-1])))
        lc = LineCollection(segs, cmap="viridis", array=ts[:-1], linewidths=1.5,
                            alpha=0.95, zorder=3, clim=(lo, hi))
        ax.add_collection(lc)
        sty = {"direction": ("o", "#e07b39", 5.4), "near": ("^", "#8e44ad", 7.0),
               "no_signal": ("s", "#b9c2cc", 3.4)}
        for res, (mk, col, ms) in sty.items():
            P = np.array([[a["x"], a["y"]] for a in acts
                          if a.get("kind") == "measure" and a.get("measure_result") == res])
            if len(P):
                ax.plot(P[:, 0], P[:, 1], mk, color=col, ms=ms,
                        alpha=0.85, zorder=5, mec="none")
        C = np.array([[a["x"], a["y"]] for a in acts
                      if a.get("kind") == "clear"])
        if len(C):
            ax.plot(C[:, 0], C[:, 1], ".", color="#7f8c8d", ms=6, zorder=5)
        K = np.array([[a["x"], a["y"]] for a in acts
                      if a.get("kind") == "clear" and a.get("clear_result") == "success"])
        if len(K):
            ax.plot(K[:, 0], K[:, 1], "x", color="#c0392b", ms=8, mew=1.7, zorder=6)
    ax.plot([0], [0], marker="s", ms=6, color="#252a35", zorder=8)

    last = (rep["avg_clear_time_s"] or 0.0) * rep["cleared"]
    ax.set_title(f"{title}｜清除 {rep['cleared']}/{rep['n_sources']}"
                 f"｜虚拟时间 {rep['virtual_time_s']:.0f} s"
                 f"｜末次清除 {last:.0f} s\n"
                 f"行程 {audit['travel_m'] / 1000:.2f} km"
                 f"｜检测 {audit['n_measure']} 次"
                 f"｜{predicate} {'通过' if rep.get('complete_proof') else '未通过'}"
                 f"｜接口拒绝 {rep['n_rejected']} 次",
                 fontsize=9.5)
    ax.set_xlim(-1950, 1950)
    ax.set_ylim(-1950, 1950)
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)


def legend_handles():
    return [
        Line2D([], [], color="#440154", lw=2.4, label="机器狗航路（颜色深→浅 = 时间早→晚）"),
        Line2D([], [], ls="", marker="o", color="#e07b39", ms=7, label="检测：direction（有示向度）"),
        Line2D([], [], ls="", marker="^", color="#8e44ad", ms=8, label="检测：near（≤5 m）"),
        Line2D([], [], ls="", marker="s", color="#b9c2cc", ms=5, label="检测：no_signal（无信号）"),
        Line2D([], [], ls="", marker="x", color="#c0392b", mew=1.7, ms=8, label="清除成功"),
        Line2D([], [], ls="", marker="*", color="#2e8b57", ms=13, label="已清除源位（事后标注）"),
        Line2D([], [], ls="", marker="*", color="#c0392b", ms=13, label="未清除源位（事后标注）"),
        Line2D([], [], ls=":", color="gray", label="源的有效接收半径"),
        Line2D([], [], ls="--", color="#9aa3ad", label="靶区边界 r=1800 m"),
    ]


def predicate_of(name):
    return "网格覆盖谓词" if name == "tour" else "连续覆盖证书"


def draw_case(cases, out_png, dpi=150):
    n, k = len(cases), len(POLICIES)
    fig, axes = plt.subplots(n, k, figsize=(6.35 * k, 7.0 * n), layout="constrained",
                             squeeze=False)
    for i, (label, kind, seed, pair) in enumerate(cases):
        hi = max(pair[p]["rep"]["virtual_time_s"] for p in pair)
        for j, (name, _c, _g) in enumerate(POLICIES):
            d = pair[name]
            draw_panel(axes[i, j], d["arena"], d["rep"], d["audit"],
                       f"{label}（{kind} seed={seed}）· {name}", (0.0, hi),
                       predicate_of(name))
    fig.legend(handles=legend_handles(), loc="outside lower center", ncols=5,
               fontsize=8.5, frameon=False)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)


def draw_overview(cases, out_png, dpi=115):
    n, k = len(cases), len(POLICIES)
    fig, axes = plt.subplots(n, k, figsize=(5.6 * k, 5.8 * n), layout="constrained",
                             squeeze=False)
    for i, (label, kind, seed, pair) in enumerate(cases):
        for j, (name, _c, _g) in enumerate(POLICIES):
            d = pair[name]
            draw_panel(axes[i, j], d["arena"], d["rep"], d["audit"],
                       f"{label} · {name}", predicate=predicate_of(name))
    axes[0, 0].legend(handles=legend_handles(), loc="lower right", fontsize=6.5,
                      framealpha=0.92)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)


def draw_time_split(cases, out_png, dpi=150):
    """虚拟时间去哪儿了：移动 / 检测固定 5 s / 频道切换 / 清除。"""
    rows = [(f"{lab}·{name}", pair[name]["audit"]) for lab, _k, _s, pair in cases
            for name, _c, _g in POLICIES]
    fig, ax = plt.subplots(figsize=(11.5, 0.5 * len(rows) + 1.9), layout="constrained")
    y = np.arange(len(rows))
    parts = [("t_travel_s", "移动（行程 ÷ 5 m/s）", "#3b7ea1"),
             ("t_measure_s", "检测固定 5 s/次", "#e0a03c"),
             ("t_switch_s", "频道切换 1 s/次", "#8e6fbf"),
             ("t_clear_s", "清除 5 s / 未发现 3 s", "#5aa469")]
    left = np.zeros(len(rows))
    for key, lab, col in parts:
        w = np.array([r[1][key] for r in rows])
        ax.barh(y, w, left=left, color=col, label=lab, height=0.68)
        left += w
    for i, (lab, au) in enumerate(rows):
        ax.text(left[i] + 25, y[i], f"{left[i]:.0f} s", va="center", fontsize=7.5)
    ax.set_yticks(y, [r[0] for r in rows], fontsize=7.5)
    ax.invert_yaxis()
    ax.set_xlabel("虚拟时间（s）")
    ax.set_xlim(0, float(left.max()) * 1.14)
    ax.legend(ncols=4, fontsize=8, frameon=False, loc="lower right")
    ax.set_title("虚拟时间的去向：同场景各策略对照（四段之和 = /enter→/exit 的虚拟时间）",
                 fontsize=11)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)


# --------------------------------------------------------------------------
# 3) 完工声明的独立复核（不依赖策略自己的 50 m 单元证书）
# --------------------------------------------------------------------------
def coverage_audit(kind, seeds, base, step=5.0, cls=None, cfg_cls=None):
    """用 5 m 细网格**独立**复核 `complete_proof`：

    对每个"没有清除、也没有 direction/near 记录"的频道，要求靶区圆域内**每一点**
    都落在某个该频道真实 `no_signal` 测点的 1000 m 之内。若有空洞，就说明
    "靶区内已无该频道源"的声明不成立（因为有效接收半径 >= 1000 m）。
    """
    from scipy.spatial import cKDTree

    xs = np.arange(-R_ARENA, R_ARENA + step / 2, step)
    gx, gy = np.meshgrid(xs, xs)
    inside = gx ** 2 + gy ** 2 <= R_ARENA ** 2 + 1e-9
    grid = np.column_stack([gx[inside], gy[inside]])

    out = []
    for seed in seeds:
        arena = make_scene(kind, seed)
        rep = run_one(cls or AdaptiveRobot, (cfg_cls or AdaptiveConfig)(), arena, base,
                      want_path=False)
        truth = arena.truth()
        recs = {}
        for a in arena.actions:
            if a.get("kind") != "measure":
                continue
            ch = int(a["channel"])
            recs.setdefault(ch, {"no_signal": [], "positive": 0})
            if a.get("measure_result") == "no_signal":
                recs[ch]["no_signal"].append((a["x"], a["y"]))
            else:
                recs[ch]["positive"] += 1
        cleared = {int(s["channel"]) for s in truth["sources"] if s["cleared"]}
        worst = 0.0
        worst_ch = None
        for ch in range(1, 21):
            if ch in cleared:
                continue
            info = recs.get(ch) or {"no_signal": [], "positive": 0}
            if info["positive"]:
                out.append({"kind": kind, "seed": seed, "channel": ch, "ok": False,
                            "why": "未清除但存在 direction/near 记录，声明应为 false",
                            "claimed": bool(rep["complete_proof"])})
                continue
            pts = info["no_signal"]
            if not pts:                       # 从未测过 -> 整个圆域都未排除
                d = np.full(len(grid), np.inf)
            else:
                d, _ = cKDTree(np.asarray(pts)).query(grid, k=1)
            m = float(d.max())
            if m > worst:
                worst, worst_ch = m, ch
        out.append({"kind": kind, "seed": seed, "claimed": bool(rep["complete_proof"]),
                    "ok": bool(rep["complete_proof"]) and worst <= 1000.0 + 1e-6,
                    "max_uncovered_dist_m": None if not np.isfinite(worst) else round(worst, 3),
                    "worst_channel": worst_ch,
                    "cleared": rep["cleared"], "n_sources": rep["n_sources"],
                    "virtual_time_s": rep["virtual_time_s"]})
    return out


# --------------------------------------------------------------------------
def default_case_specs(seed, count):
    """默认案例集：随机 4 局 + 外圈 + 中心 + 两个在线复刻布局。"""
    specs = [("random", seed + 37 * i, f"随机{i + 1}") for i in range(count)]
    specs += [("annulus", seed, "外圈环带"), ("center", seed, "中心聚集"),
              ("live1", seed, "在线第1局复刻"), ("live2", seed, "在线第2局复刻")]
    return specs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=777000)
    ap.add_argument("--cases", type=int, default=4, help="随机案例个数")
    ap.add_argument("--policies", default="tour,adaptive,joint",
                    help="参与对照与作图的策略（逗号分隔）")
    ap.add_argument("--coverage-audit", type=int, default=0,
                    help="额外对 N 局随机场景做 5 m 细网格完工声明复核")
    ap.add_argument("--coverage-policy", default="joint",
                    help="覆盖复核用哪个策略（默认 joint）")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    global POLICIES
    want = [p.strip() for p in args.policies.split(",") if p.strip()]
    POLICIES = tuple(p for p in ALL_POLICIES if p[0] in want)
    if not POLICIES:
        raise SystemExit(f"没有可用策略：{want}")

    _setup_font()
    os.makedirs(args.out, exist_ok=True)
    base = load_base()
    specs = default_case_specs(args.seed, args.cases)

    cases, table = [], []
    for label, kind, seed in [(s[2], s[0], s[1]) for s in specs]:
        t0 = __import__("time").time()
        pair = run_pair(kind, seed, base)
        cases.append((label, kind, seed, pair))
        for name, _c, _g in POLICIES:
            d, rep, au = pair[name], pair[name]["rep"], pair[name]["audit"]
            row = {"case": label, "kind": kind, "seed": seed, "policy": name,
                   "n_sources": rep["n_sources"], "cleared": rep["cleared"],
                   "virtual_time_s": rep["virtual_time_s"],
                   "vtime_recomputed_s": round(au["vtime_s"], 6),
                   "vtime_gap_s": round(rep["virtual_time_s"] - au["vtime_s"], 9),
                   "last_clear_s": round((rep["avg_clear_time_s"] or 0) * rep["cleared"], 3),
                   "travel_m": round(au["travel_m"], 3),
                   "travel_gap_m": round(au["travel_m"] - rep["mock_stats"]["travel_m"], 9),
                   "n_measure": au["n_measure"],
                   "n_measure_gap": au["n_measure"] - rep["n_measure"],
                   "n_clear_ok": au["n_clear_ok"],
                   "n_clear_fail": rep["n_clear_fail"],
                   "max_dt_err_s": au["max_dt_err_s"],
                   "max_dist_err_m": au["max_dist_err_m"],
                   "complete_proof": bool(rep["complete_proof"]),
                   "n_rejected": rep["n_rejected"],
                   "truth_calls": pair[name]["truth_calls"],
                   "wall_s": round(rep["_wall"], 3)}
            table.append(row)
        base_t = pair[POLICIES[0][0]]["rep"]["virtual_time_s"]
        shown = " → ".join(
            f"{n} {pair[n]['rep']['virtual_time_s']:.0f}s" for n, _c, _g in POLICIES)
        tail = "  ".join(
            f"（{n} 对 {POLICIES[0][0]} {(1 - pair[n]['rep']['virtual_time_s'] / base_t):+.1%}）"
            for n, _c, _g in POLICIES[1:])
        print(f"[ok] {label}（{kind} seed={seed}）{shown}{tail}"
              f"  {__import__('time').time() - t0:.1f}s", flush=True)

    draw_case(cases, os.path.join(args.out, "paths_pair.png"))
    draw_overview(cases, os.path.join(args.out, "paths_overview.png"))
    draw_time_split(cases, os.path.join(args.out, "time_split.png"))
    (open(os.path.join(args.out, "verify_table.json"), "w", encoding="utf-8")
     .write(json.dumps({"cases": specs, "rows": table}, ensure_ascii=False, indent=2)))

    worst = max(abs(r["vtime_gap_s"]) for r in table)
    worst_d = max(r["max_dt_err_s"] for r in table)
    worst_m = max(abs(r["travel_gap_m"]) for r in table)
    truth_calls = sum(r["truth_calls"] for r in table)
    print(f"\n台账重算：虚拟时间最大偏差 {worst:.2e} s；单步 dt 最大偏差 {worst_d:.2e} s；"
          f"行程最大偏差 {worst_m:.2e} m")
    print(f"真值探针：{truth_calls} 次 truth() 调用全部发生在 /exit 之后")
    print(f"全部清除：{sum(1 for r in table if r['cleared'] == r['n_sources'])}/{len(table)} 条记录")

    if args.coverage_audit:
        cls = next((c for n, c, _g in ALL_POLICIES if n == args.coverage_policy), None)
        cfg_cls = next((g for n, _c, g in ALL_POLICIES if n == args.coverage_policy), None)
        if cls is None:
            raise SystemExit(f"未知策略 {args.coverage_policy}")
        seeds = [args.seed + 37 * i for i in range(args.coverage_audit)]
        print(f"\n完工声明独立复核（5 m 细网格）：{args.coverage_policy} · "
              f"random 场景 {len(seeds)} 局……", flush=True)
        recs = coverage_audit("random", seeds, base, cls=cls, cfg_cls=cfg_cls)
        bad = [r for r in recs if not r["ok"]]
        vals = [r["max_uncovered_dist_m"] for r in recs
                if r.get("max_uncovered_dist_m") is not None]
        print(f"  声明 complete_proof 的局数：{sum(1 for r in recs if r['claimed'])}/{len(recs)}")
        print(f"  未被 1000 m 覆盖的最坏点距（应 <= 1000 m）："
              f"{max(vals) if vals else float('nan'):.2f} m")
        print(f"  复核不通过的局数：{len(bad)}")
        for r in bad:
            print("   ", r)
        (open(os.path.join(args.out, "coverage_audit.json"), "w", encoding="utf-8")
         .write(json.dumps(recs, ensure_ascii=False, indent=2)))

    print(f"图：{os.path.join(args.out, 'paths_pair.png')}")
    print(f"    {os.path.join(args.out, 'paths_overview.png')}")
    print(f"    {os.path.join(args.out, 'time_split.png')}")


if __name__ == "__main__":
    main()
