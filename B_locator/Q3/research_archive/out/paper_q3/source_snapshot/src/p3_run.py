"""B 题问题 3：机器狗策略的运行入口（可执行主程序）。

三种用法
--------
    # 1) 离线演练（可跑几百局；正式测试只有 3 次机会，所以调参必须在这里做）
    python src/p3_run.py --mode mock --cases 10 --out out/p3

    # 2) 真实模拟器（先在模拟器里登录、开始"问题3 演练测试/正式测试"，等接口就绪）
    python src/p3_run.py --mode live --robot-id <参赛队号> --url http://127.0.0.1:2026

    # 3) 参数扫描（同一批案例上比较不同距离项系数 λ / 跳测间隔等）
    python src/p3_run.py --tune dist_weight=0.1,0.35,0.7 --cases 6

统计量（按题目表 1 的口径）
---------------------------
* 被清除干扰源个数的比例 = 被清除个数 / 干扰源总数（离线演练可读到真值）
* 平均定位清除时间 = 定位清除总时间 / 被清除干扰源个数
  （总时间含移动、频道切换、检测、光学精确定位与清除；本程序取"最后一个源被清除时的虚拟时刻"）
* 程序运行时间 = 程序自身跑完的墙钟时间

> 备注：`scripts/run_p3.py` 只是本文件的转发入口。本机 `scripts/`、`data/`、`tests/`
> 目录存在 ACL 限制（子进程无法读取），因此可执行版本放在 `src/` 下。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics as st
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))

# Windows 控制台默认 GBK：中文可以，但箭头/星号等符号会直接抛 UnicodeEncodeError
# 把整局打断（实测发生过）。统一改成 UTF-8 输出，并且永不因为编码问题中断。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from p3_arena import ArenaError, HttpArena, MockArena, R_ARENA  # noqa: E402
from p3_expect_field import DEFAULT_BASE_CSV, DEFAULT_FAMILY_DIR  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402
from p3_sweep import SweepConfig, SweepRobot  # noqa: E402
from p3_tour import TourConfig, TourRobot  # noqa: E402
from p3_adaptive import AdaptiveConfig, AdaptiveRobot  # noqa: E402
from p3_joint import JointConfig, JointRobot  # noqa: E402

# 可选策略（默认 joint）：
#   joint = 联合优化清除终点、覆盖测站与逐频道检测成本（当前最优，见 review/p3-joint-design.md）
#   adaptive = 沿途逼近定位 + 动态覆盖选站（见 review/p3-adaptive-design.md）
#   tour  = 统一滚动航路（"绕圈"与"清除"合成一条动态航路，见 review/p3-tour-design.md）
#   sweep = 覆盖扫圈（先绕完一圈再统一清除）
#   field = 期望场贪心（最早的实现）
DEFAULT_POLICY = "joint"
POLICIES = {"tour": (TourRobot, TourConfig),
            "joint": (JointRobot, JointConfig),
            "adaptive": (AdaptiveRobot, AdaptiveConfig),
            "sweep": (SweepRobot, SweepConfig),
            "field": (P3Robot, P3Config)}


def make_robot(policy, arena, cfg=None, base=None, log=None):
    """按名字造机器狗。``sweep`` 用 `SweepConfig`（继承 `P3Config` 全部字段）。"""
    if policy not in POLICIES:
        raise SystemExit(f"未知策略 {policy!r}，可选：{list(POLICIES)}")
    cls, cfg_cls = POLICIES[policy]
    if cfg is None:
        cfg = cfg_cls()
    elif not isinstance(cfg, cfg_cls):
        cfg = cfg_cls(**{k: v for k, v in cfg.__dict__.items()
                         if k in cfg_cls.__dataclass_fields__})
    return cls(arena, cfg, base=base, log=log)

OUT_DEFAULT = os.path.normpath(os.path.join(_ROOT, "out", "p3"))
# mock 的默认虚拟时间上限：与真实模拟器一致（接口说明 4.5：虚拟世界限时 360000 s）
DEFAULT_VIRTUAL_BUDGET = 360000.0
# live 模式不用它：live 用 /enter 返回的 remaining_real_duration_s
LIVE_REAL_BUDGET = 1200.0


# --------------------------------------------------------------------------
def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=_json_default)
    return path


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def action_log_jsonl(path, actions):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for a in actions:
            f.write(json.dumps(a, ensure_ascii=False, default=_json_default) + "\n")
    return path


# --------------------------------------------------------------------------
def run_mock_case(seed, cfg: P3Config, base=None, outdir=None, verbose=False,
                  figure=False, budget_s=None, policy=DEFAULT_POLICY):
    """离线跑一局。

    ``budget_s`` 是 **mock 的虚拟时间上限**，必须与真实模拟器一致才可比：
    真实模拟器的虚拟世界限时是 360000 s，程序运行时间（1200 s）是**现实时间**、
    与虚拟时钟无关（接口说明 4.5）。旧版本把 mock 的虚拟上限设成 1200 s，
    等于给离线演练加了一条真实测试里并不存在的约束，会把 "定向清除率" 严重低估。
    """
    arena = MockArena(seed=seed, budget_s=(DEFAULT_VIRTUAL_BUDGET if budget_s is None
                                           else budget_s))
    rb = make_robot(policy, arena, cfg, base=base,
                    log=(lambda m: print("   " + m)) if verbose else None)
    rep = rb.run()
    rep["seed"] = seed
    if outdir:
        d = os.path.join(outdir, f"case_{seed}")
        write_json(os.path.join(d, "summary.json"), rep)
        action_log_jsonl(os.path.join(d, "actions.jsonl"), arena.actions)
        write_json(os.path.join(d, "robot_events.json"), rb.events)
        if figure:
            try:
                rep["figure"] = plot_case(arena, rb, rep, os.path.join(d, "p3_case.png"))
            except Exception as e:      # 画图失败不影响演练
                rep["figure_error"] = repr(e)
    return rep


def run_live(cfg: P3Config, url, robot_id, outdir, base=None, verbose=True,
             arena_id="default", timeout=5.0, enter_wait_s=40.0,
             policy=DEFAULT_POLICY):
    d = os.path.join(outdir, time.strftime("live_%Y%m%d_%H%M%S"))
    arena = HttpArena(base_url=url, robot_id=robot_id, arena_id=arena_id,
                      timeout=timeout, log_path=os.path.join(d, "protocol.jsonl"),
                      enter_wait_s=enter_wait_s)
    rb = make_robot(policy, arena, cfg, base=base, log=print if verbose else None)
    print(f"连接模拟器 {url}（队号 {robot_id}，策略 {policy}）；"
          f"若接口尚未开放会自动等待重试…")
    try:
        rep = rb.run()
    except ArenaError as e:
        print(f"\n[失败] {e}")
        print("请确认：① 模拟器已在线登录；② 已开始『问题3 演练测试/正式测试』；"
              "③ 5 秒倒计时结束、界面提示机器狗接口已就绪；④ --url 端口与模拟器一致。")
        write_json(os.path.join(d, "error.json"), {"error": repr(e), "url": url})
        raise SystemExit(2)
    rep["url"] = url
    write_json(os.path.join(d, "summary.json"), rep)
    action_log_jsonl(os.path.join(d, "robot_events.jsonl"), rb.events)
    print(json.dumps({k: v for k, v in rep.items()
                      if k not in ("truth", "mock_stats", "channels")},
                     ensure_ascii=False, indent=2, default=_json_default))
    return rep


def oracle_bound(seeds, budget_s=None, v=5.0, t_clear=5.0):
    """**理论上限**：假设机器狗事先知道所有干扰源位置，可以走最优航路、到点即清除。

    这是任何策略都达不到的上界（它不需要发现、不需要第二次定位测量），
    用来判断我们 40% 左右的清除率离"物理上界"还有多远。

    航路用最近邻 + 2-opt；时间模型：起点 (0,0) → 依次到各源，每源耗时 = 距离/5 + 5 s。
    返回逐案例的 (可清除数, 已清除比例)。
    """
    budget_s = DEFAULT_VIRTUAL_BUDGET if budget_s is None else float(budget_s)
    def tour_len(pts):
        k = len(pts)
        if k == 0:
            return 0.0, []
        cur = np.array([0.0, 0.0])
        left = list(range(k))
        seq = []
        while left:
            j = min(left, key=lambda i: float(np.hypot(*(pts[i] - cur))))
            seq.append(j)
            left.remove(j)
            cur = pts[j]

        def total(order):
            d = float(np.hypot(*(pts[order[0]] - np.array([0.0, 0.0]))))
            for a, b in zip(order, order[1:]):
                d += float(np.hypot(*(pts[b] - pts[a])))
            return d

        best = total(seq)
        improved = True
        while improved:
            improved = False
            for i in range(k - 1):
                for j in range(i + 1, k):
                    cand = seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]
                    d = total(cand)
                    if d < best - 1e-9:
                        seq, best, improved = cand, d, True
        return best, seq

    out = []
    for s in seeds:
        arena = MockArena(seed=s)
        pts = np.array([[x.x, x.y] for x in arena.sources])
        _L, seq = tour_len(pts)
        t = 0.0
        n = 0
        cur = np.array([0.0, 0.0])
        for i in seq:
            dt = float(np.hypot(*(pts[i] - cur))) / v + t_clear
            if t + dt > budget_s:
                break
            t += dt
            cur = pts[i]
            n += 1
        out.append((n, len(pts), n / len(pts)))
    return out


# --------------------------------------------------------------------------
def aggregate(reps):
    ok = [r for r in reps if r.get("clear_ratio") is not None]
    cl = [r["cleared"] for r in ok]
    tot = [r["n_sources"] for r in ok]
    tms = [r["avg_clear_time_s"] for r in ok if r["avg_clear_time_s"]]
    return {
        "cases": len(reps),
        "n_sources_total": int(sum(tot)),
        "n_cleared_total": int(sum(cl)),
        "clear_ratio_total": (sum(cl) / sum(tot)) if sum(tot) else None,
        "clear_ratio_mean": st.mean(r["clear_ratio"] for r in ok) if ok else None,
        "cleared_mean": st.mean(cl) if cl else None,
        "cleared_min": min(cl) if cl else None,
        "cleared_max": max(cl) if cl else None,
        "avg_clear_time_mean_s": st.mean(tms) if tms else None,
        "avg_clear_time_median_s": st.median(tms) if tms else None,
        "virtual_time_mean_s": st.mean(r["virtual_time_s"] for r in reps) if reps else None,
        "runtime_mean_s": st.mean(r["program_runtime_s"] for r in reps) if reps else None,
        "travel_mean_m": st.mean(r["travel_m"] for r in reps) if reps else None,
        "n_measure_mean": st.mean(r["n_measure"] for r in reps) if reps else None,
        "n_scan_rounds_mean": st.mean(r["n_scan_rounds"] for r in reps) if reps else None,
        "n_rejected": int(sum(r["n_rejected"] for r in reps)),
    }


def print_table(rows, cols, title=None):
    if title:
        print(f"\n=== {title} ===")
    w = {}
    for c in cols:
        w[c] = max([len(c)] + [len(f"{r.get(c, '')}") for r in rows])
    print("  ".join(c.rjust(w[c]) for c in cols))
    print("  ".join("-" * w[c] for c in cols))
    for r in rows:
        cells = []
        for c in cols:
            v = r.get(c)
            if v is None:
                s = ""
            elif isinstance(v, float):
                s = f"{v:.4f}" if abs(v) < 10 else f"{v:.1f}"
            else:
                s = str(v)
            cells.append(s.rjust(w[c]))
        print("  ".join(cells))


# --------------------------------------------------------------------------
def plot_case(arena, robot, rep, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.4, 8.4))
    th = np.linspace(0, 2 * math.pi, 720)
    ax.plot(R_ARENA * np.cos(th), R_ARENA * np.sin(th), "k--", lw=1.0,
            label="target area R=1800 m")
    truth = rep.get("truth") or {}
    for s in truth.get("sources", []):
        col = "tab:green" if s["cleared"] else "tab:red"
        ax.plot([s["x_m"]], [s["y_m"]], "o", color=col, ms=8, zorder=5)
        ax.annotate(f"ch{s['channel']}", (s["x_m"], s["y_m"]), fontsize=8,
                    xytext=(4, 4), textcoords="offset points")
    pts = [(a["x"], a["y"]) for a in getattr(arena, "actions", [])
           if a.get("kind") in ("measure", "clear")]
    if pts:
        P = np.array([[0.0, 0.0]] + pts)
        ax.plot(P[:, 0], P[:, 1], "-", color="tab:blue", lw=0.9, alpha=0.7,
                label="robot path")
    sp = np.array(rep["scan_points"]) if rep.get("scan_points") else None
    if sp is not None and len(sp):
        ax.plot(sp[:, 0], sp[:, 1], "s", color="tab:orange", ms=7,
                label="scan points (multi-channel)")
    for ch, rec in robot.recs.items():
        for (x, y), a in zip(rec.pts, rec.svds):
            L = 700.0
            ax.plot([x, x + L * math.cos(math.radians(a))],
                    [y, y + L * math.sin(math.radians(a))],
                    color="tab:purple", lw=0.5, alpha=0.45)
    ax.plot([0], [0], "k*", ms=13, label="start (0,0)")
    ax.set_aspect("equal")
    ax.set_xlim(-1950, 1950)
    ax.set_ylim(-1950, 1950)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"Q3 offline drill  seed={rep.get('seed')}  cleared "
                 f"{rep['cleared']}/{rep['n_sources']}  vtime={rep['virtual_time_s']:.0f}s\n"
                 f"avg clear time = {rep['avg_clear_time_s']:.1f}s  "
                 f"travel = {rep['travel_m']:.0f} m", fontsize=9)
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
def parse_grid(spec):
    out = {}
    for s in spec or []:
        k, v = s.split("=", 1)
        out[k.strip()] = [float(x) if ("." in x or "e" in x.lower()) else int(x)
                          for x in v.split(",") if x.strip() != ""]
    return out


def grid_iter(grid, base_cfg: P3Config):
    keys = list(grid)
    if not keys:
        yield {}, base_cfg
        return
    import itertools
    for combo in itertools.product(*(grid[k] for k in keys)):
        cfg = P3Config(**{**base_cfg.__dict__, **dict(zip(keys, combo))})
        yield dict(zip(keys, combo)), cfg


def main():
    ap = argparse.ArgumentParser(description="问题3 机器狗策略运行入口")
    ap.add_argument("--mode", choices=["mock", "live"], default="mock")
    ap.add_argument("--cases", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--figure", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--tune", action="append", default=None,
                    metavar="NAME=v1,v2", help="参数扫描，如 dist_weight=0.1,0.35,0.7")
    ap.add_argument("--dist-weight", type=float, default=1.5,
                    help="距离项系数 λ（离线演练调参得到 1.5）")
    ap.add_argument("--grid-step", type=float, default=100.0)
    ap.add_argument("--nosignal-gap", type=float, default=1000.0)
    ap.add_argument("--clear-max-radius", type=float, default=600.0)
    ap.add_argument("--enroute-scan-max", type=int, default=2)
    ap.add_argument("--refine-mode", choices=["perp", "exact"], default="perp")
    ap.add_argument("--family-dir", default=DEFAULT_FAMILY_DIR)
    ap.add_argument("--base-map", default=DEFAULT_BASE_CSV)
    ap.add_argument("--url", default="http://127.0.0.1:2026")
    ap.add_argument("--robot-id", default="")
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--budget", type=float, default=DEFAULT_VIRTUAL_BUDGET,
                    help=f"mock 的虚拟时间上限（s），默认 {DEFAULT_VIRTUAL_BUDGET:.0f}，"
                         "与真实模拟器一致")
    ap.add_argument("--policy", choices=sorted(POLICIES), default=DEFAULT_POLICY,
                    help=f"joint=联合航路与检测调度（默认，当前最优）| "
                         "adaptive=沿途定位与动态覆盖 | "
                         "tour=统一滚动航路（绕圈与清除合一，对照）| "
                         "sweep=覆盖扫圈（先绕完一圈再清）| field=期望场贪心")
    args = ap.parse_args()

    # Preserve joint's close-stop behavior; a base P3Config would overwrite
    # its min_move=0 with the legacy 60 m stop-skipping threshold.
    config_class = JointConfig if args.policy == "joint" else P3Config
    base_cfg = config_class(dist_weight=args.dist_weight, grid_step=args.grid_step,
                        nosignal_gap_m=args.nosignal_gap, refine_mode=args.refine_mode,
                        clear_max_radius_m=args.clear_max_radius,
                        enroute_scan_max=args.enroute_scan_max)
    base = load_base(args.family_dir, args.base_map)
    print(f"基准：{'基准图族' if hasattr(base, 'select') else ('单张基准图' if base else '无')}")

    if args.mode == "live":
        if not args.robot_id:
            raise SystemExit("live 模式必须提供 --robot-id（参赛队号）")
        run_live(base_cfg, args.url, args.robot_id, args.out, base=base,
                 verbose=True, timeout=args.timeout, policy=args.policy)
        return

    grid = parse_grid(args.tune)
    seeds = [args.seed + 100 * i for i in range(args.cases)]
    rows = []
    for combo, cfg in grid_iter(grid, base_cfg):
        t0 = time.time()
        reps = [run_mock_case(s, cfg, base=base, budget_s=args.budget,
                              policy=args.policy,
                              outdir=(None if grid else args.out),
                              verbose=args.verbose, figure=args.figure)
                for s in seeds]
        agg = aggregate(reps)
        row = dict(combo)
        row.update(agg)
        row["wall_s"] = round(time.time() - t0, 2)
        rows.append(row)
        if grid:
            print(f"  {combo} -> 清除率 {agg['clear_ratio_total']:.3f}，"
                  f"平均清除 {agg['cleared_mean']:.2f} 个，"
                  f"平均定位清除时间 {agg['avg_clear_time_mean_s']:.1f}s，"
                  f"耗时 {row['wall_s']}s")
        else:
            ob = oracle_bound(seeds, budget_s=args.budget)
            n_ob = sum(o[0] for o in ob)
            n_tot = sum(o[1] for o in ob)
            agg["oracle_cleared_mean"] = st.mean(o[0] for o in ob)
            agg["oracle_ratio_total"] = n_ob / n_tot
            agg["strategy_over_oracle"] = (agg["cleared_mean"]
                                           / max(agg["oracle_cleared_mean"], 1e-9))
            write_json(os.path.join(args.out, "mock_benchmark.json"),
                       {"cfg": cfg.__dict__, "seeds": seeds, "aggregate": agg,
                        "oracle": {"cleared_per_case": [o[0] for o in ob],
                                   "sources_per_case": [o[1] for o in ob],
                                   "note": "上界：预知全部源位置 + 最优航路 + 到点即清除"},
                        "cases": [{k: v for k, v in r.items()
                                   if k not in ("truth", "channels")} for r in reps]})
            with open(os.path.join(args.out, "mock_benchmark.csv"), "w", newline="",
                      encoding="utf-8-sig") as f:
                w = csv.writer(f)
                cols = ["seed", "cleared", "n_sources", "clear_ratio",
                        "avg_clear_time_s", "virtual_time_s", "program_runtime_s",
                        "n_measure", "n_bearings", "n_scan_rounds", "n_refine",
                        "n_clear", "n_clear_fail", "n_sweep_aborted", "n_sweep_miss",
                        "n_probe_issued", "travel_m", "n_rejected"]
                w.writerow(cols)
                for r in reps:
                    w.writerow([r.get(c) for c in cols])

    if grid:
        cols = list(grid) + ["clear_ratio_total", "clear_ratio_mean", "cleared_mean",
                             "avg_clear_time_mean_s", "virtual_time_mean_s",
                             "travel_mean_m", "n_measure_mean", "wall_s"]
        print_table(rows, cols, title="参数扫描结果")
        write_json(os.path.join(args.out, "tune_results.json"),
                   {"grid": grid, "seeds": seeds, "rows": rows})
    else:
        print()
        print(json.dumps(rows[0], ensure_ascii=False, indent=2, default=_json_default))
        print(f"\n结果已写入 {args.out}")


if __name__ == "__main__":
    main()
