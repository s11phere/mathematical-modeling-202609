"""B 题问题 4：运行入口（离线演练 / 真实模拟器 / 几何自检）。

    # 1) 几何自检：三角形格网的覆盖与"定向盲区"（不跑模拟器）
    python src/p4_run.py --geometry

    # 2) 离线演练（定向 + 全向混合；正式测试只有 3 次机会，调参必须在这里做）
    python src/p4_run.py --mode mock --cases 10 --scenario directed --verbose
    python src/p4_run.py --mode mock --cases 30 --scenario omni      # 全向对照
    python src/p4_run.py --mode mock --cases 10 --scenario directed --out out/p4 --figure

    # 3) 真实模拟器（先在模拟器里登录、开始"问题4 演练测试"，等接口就绪）
    python src/p4_run.py --mode live --robot-id <参赛队号> --url http://127.0.0.1:2026

统计口径与题目表 1 一致：
* 被清除干扰源个数的比例 = 被清除个数 / 干扰源总数；
* 平均定位清除时间 = 定位清除总时间 / 被清除干扰源个数
  （总时间含移动、频道切换、检测、光学精确定位与清除，取最后一个源被清除的时刻）；
* 完整退出每源时间 = /exit 时的虚拟时间 / 被清除源数（本轮优化主指标）；
* 程序运行时间 = 程序自身跑完的墙钟时间。
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

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from p3_arena import (  # noqa: E402
    ArenaError, HttpArena, MockArena, MockSource, R_ARENA, R_CLEAR, R_RECV_MAX,
    R_RECV_MIN, V_ROBOT,
)
from p3_robot import P3Robot  # noqa: E402
from p4_arena_ext import SCENARIOS, directed_case, make_arena  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402

OUT_DEFAULT = os.path.normpath(os.path.join(_ROOT, "out", "p4"))
DEFAULT_VIRTUAL_BUDGET = 360000.0     # 与真实模拟器一致（虚拟世界限时 100 小时）
LIVE_REAL_BUDGET = 1200.0             # 现实时间预算（/enter 返回）

# 当前最优策略与档位：compact = 21 站紧凑布局 + 后验估计 + 信息排路；
# strict = 100% 档（离线配对：混合源 5933 s、全定向 6491 s，360 局 4668 源全部清除并认证）。
# 速度档 fast99/98/95/90 以牺牲清除率为代价换时间（贴边朝外场景 fast98 及以下清除率 0%），
# 正式测试**不要**当默认用；见 review/p4-compact-design.md。
DEFAULT_POLICY = 'compact'
DEFAULT_TIER = 'strict'


# --------------------------------------------------------------------------
# 场景（定义搬到了 p4_arena_ext，自检/诊断共用同一套）
# --------------------------------------------------------------------------
def make_robot(arena, cfg=None, log=None):
    from p4_search import P4SearchConfig, P4SearchRobot
    from p4_compact import P4CompactConfig, P4CompactRobot, compact_config
    if cfg is None:
        cfg=compact_config('strict')
    if isinstance(cfg,P4CompactConfig):
        return P4CompactRobot(arena,cfg,log=log)
    if isinstance(cfg,P4SearchConfig):
        return P4SearchRobot(arena,cfg,log=log)
    return P4GridRobot(arena, cfg or P4Config(), base=None, log=log)


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


def run_mock_case(seed, cfg, scenario="directed", outdir=None, verbose=False,
                  figure=False, budget_s=None, n_sources=None,directed_frac=.5):
    arena = make_arena(scenario, seed, n_sources=n_sources,
                       budget=(DEFAULT_VIRTUAL_BUDGET if budget_s is None
                               else budget_s),directed_frac=directed_frac)
    rb = make_robot(arena, cfg, log=(lambda m: print("   " + m)) if verbose else None)
    rep = rb.run()
    rep['exit_per_cleared_s']=(rep['virtual_time_s']/rep['cleared'] if rep['cleared'] else None)
    rep["seed"] = seed
    rep["scenario"] = scenario
    rep["n_directed"] = sum(1 for s in arena.sources if s.cone_half < 180.0)
    rep["stations_total"] = len(rb.stations)
    rep["stations_visited"] = len(rb.visited_stations)
    rep["stations"] = [[round(x, 1), round(y, 1)] for (x, y) in rb.stations]
    if outdir:
        d = os.path.join(outdir, f"case_{scenario}_{seed}")
        write_json(os.path.join(d, "summary.json"), rep)
        with open(os.path.join(d, "actions.jsonl"), "w", encoding="utf-8") as f:
            for a in arena.actions:
                f.write(json.dumps(a, ensure_ascii=False, default=_json_default) + "\n")
        write_json(os.path.join(d, "robot_events.json"), rb.events)
        if figure:
            try:
                rep["figure"] = plot_case(arena, rb, rep, os.path.join(d, "p4_case.png"))
            except Exception as e:
                rep["figure_error"] = repr(e)
    return rep


def plot_case(arena, robot, rep, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.6, 8.6))
    th = np.linspace(0, 2 * math.pi, 720)
    ax.plot(R_ARENA * np.cos(th), R_ARENA * np.sin(th), "k--", lw=1.0,
            label="target area R=1800 m")
    for s in rep.get("truth", {}).get("sources", []):
        col = "tab:green" if s["cleared"] else "tab:red"
        ax.plot([s["x_m"]], [s["y_m"]], "o", color=col, ms=8, zorder=6)
        ax.annotate(f"ch{s['channel']}", (s["x_m"], s["y_m"]), fontsize=8,
                    xytext=(4, 4), textcoords="offset points")
    # 格网站位
    st = np.asarray(rep.get("stations", []), float).reshape(-1, 2)
    if st.size:
        ax.plot(st[:, 0], st[:, 1], "^", color="tab:orange", ms=6, alpha=0.75,
                label="triangle lattice stations")
    pts = [(a["x"], a["y"]) for a in getattr(arena, "actions", [])
           if a.get("kind") in ("measure", "clear")]
    if pts:
        P = np.array([[0.0, 0.0]] + pts)
        ax.plot(P[:, 0], P[:, 1], "-", color="tab:blue", lw=0.9, alpha=0.75,
                label="robot path")
    for ch, rec in robot.recs.items():
        for (x, y), a in zip(rec.pts, rec.svds):
            L = 900.0
            ax.plot([x, x + L * math.cos(math.radians(a))],
                    [y, y + L * math.sin(math.radians(a))],
                    color="tab:purple", lw=0.5, alpha=0.4)
    ax.plot([0], [0], "k*", ms=13, label="start (0,0)")
    ax.set_aspect("equal")
    ax.set_xlim(-1950, 1950)
    ax.set_ylim(-1950, 1950)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"Q4 drill seed={rep.get('seed')} scenario={rep.get('scenario')}\n"
                 f"cleared {rep['cleared']}/{rep['n_sources']}  "
                 f"vtime={rep['virtual_time_s']:.0f}s  "
                 f"avg clear={rep['avg_clear_time_s']:.1f}s  "
                 f"travel={rep['travel_m']:.0f} m", fontsize=9)
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
def aggregate(reps):
    cl = [r["cleared"] for r in reps]
    tot = [r["n_sources"] for r in reps]
    tms = [r["avg_clear_time_s"] for r in reps if r["avg_clear_time_s"]]
    return {
        "cases": len(reps),
        "n_sources_total": int(sum(tot)),
        "n_cleared_total": int(sum(cl)),
        "clear_ratio_total": (sum(cl) / sum(tot)) if sum(tot) else None,
        "full_clear_cases": sum(1 for r in reps if r["cleared"] == r["n_sources"]),
        "certified_complete_cases": sum(r.get('completion_certified') is True for r in reps),
        "cleared_mean": st.mean(cl) if cl else None,
        "avg_clear_time_mean_s": st.mean(tms) if tms else None,
        "avg_clear_time_median_s": st.median(tms) if tms else None,
        "virtual_time_mean_s": st.mean(r["virtual_time_s"] for r in reps),
        "exit_per_cleared_mean_s": st.mean(r['virtual_time_s']/r['cleared'] for r in reps if r['cleared']) if any(cl) else None,
        "runtime_mean_s": st.mean(r["program_runtime_s"] for r in reps),
        "travel_mean_m": st.mean(r["travel_m"] for r in reps),
        "n_measure_mean": st.mean(r["n_measure"] for r in reps),
        "stations_mean": st.mean(r["stations_visited"] for r in reps),
        "n_rejected": int(sum(r["n_rejected"] for r in reps)),
        "n_clear_fail": int(sum(r["n_clear_fail"] for r in reps)),
    }


def print_table(rows, cols, title=None):
    if title:
        print(f"\n=== {title} ===")
    w = {c: max([len(c)] + [len(f"{r.get(c, '')}") for r in rows]) for c in cols}
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
def geometry_report(args):
    """几何自检：三角形格网的覆盖半径 + 定向盲区（不跑模拟器）。"""
    if getattr(args,'policy','compact')=='compact':
        from p4_compact import compact_config
        from p4_layout_v2 import adaptive_complete
        rb=make_robot(_DummyArena(),compact_config(args.tier))
        points=[(0.,0.)]+rb.stations
        complete,refinement=adaptive_complete(points,detail=True)
        result={'policy':'compact','tier':args.tier,'stations':len(points),
                'continuous_arbitrary_orientation_coverage':complete,
                'refinement':refinement}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return result
    if getattr(args,'policy','grid')=='joint':
        from p4_search import P4SearchRobot,tier_config
        from p4_certificate import DirectionalCertificate
        cfg=tier_config(args.tier)
        rb=P4SearchRobot(_DummyArena(),cfg)
        cert=DirectionalCertificate(20,48)
        points=[(0.,0.)]+rb.stations
        complete=cert.continuous_complete(points)
        result={'policy':'joint','tier':args.tier,'stations':len(points),
                'continuous_arbitrary_orientation_coverage':complete}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return result
    from p4_grid import cov_stats, dir_cov_stats, eval_grid
    cfg = P4Config()
    rb = P4GridRobot(_DummyArena(), cfg)
    stations = [(0.0, 0.0)] + list(rb.stations)
    gx, gy = eval_grid(20.0)
    c, cu = cov_stats(stations, gx, gy)
    dw, db, hd = dir_cov_stats(stations, gx, gy, n_dir=16)
    print(f"三角形格网 a={cfg.grid_a:.0f} m + 外环 "
          f"{[f'r{r:.0f}×{n}' for r, n in (cfg.outer_rings or ())]}"
          f"：站位 {len(stations)} 个（含原点）")
    print(f"  覆盖半径（到最近站位）最大 {c:.0f} m，未覆盖占比 {cu:.2%}"
          f"  [判据 ≤ {R_RECV_MIN:.0f} m ⇒ 全向源必被听到]")
    print(f"  最坏朝向下最近可听站位 {dw:.0f} m，定向盲区 {db:.2%}，"
            f"半平面硬伤 {hd:.2%}  [离散位置/方向采样，不是连续覆盖证明]")
    print("\n站位分布（按半径）：")
    ring = {}
    for (x, y) in stations:
        r = math.hypot(x, y)
        k = 0 if r < 1 else int(round(r / cfg.grid_a))
        ring.setdefault(k, []).append(r)
    for k in sorted(ring):
        rs = ring[k]
        print(f"  第 {k} 层：{len(rs):>3} 个，半径 {min(rs):>7.0f}–{max(rs):>7.0f} m"
              + ("（原点）" if k == 0 else ""))
    return {"n_stations": len(stations), "cov_max_m": c, "cov_unc": cu,
            "dir_worst_m": dw, "dir_blind": db, "halfplane_hard": hd}


class _DummyArena:
    """只为构造站位列表用的假 arena（不调用任何接口）。"""
    pos = (0.0, 0.0)
    channel = 1
    virtual_time_s = 0.0

    def remaining_budget_s(self):
        return 1e9

    def budget_kind(self):
        return "virtual"


def main():
    ap = argparse.ArgumentParser(description="问题4 联合航路与清除率配置")
    ap.add_argument('--policy',choices=['compact','joint','grid'],default=DEFAULT_POLICY,
                    help=f'compact=紧凑布局与信息排路（默认，当前最优）| joint=上一版 | grid=旧策略')
    ap.add_argument('--tier',choices=['strict','fast99','fast98','fast95','fast90'],default=DEFAULT_TIER,
                    help='strict=全清档（默认，360 局全部清除并认证）；fast* 用清除率换时间，'
                         '速度档名称是离线标定目标，非逐局清除率保证，正式测试勿用')
    ap.add_argument("--mode", choices=["mock", "live"], default="mock")
    ap.add_argument("--cases", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="directed", choices=list(SCENARIOS))
    ap.add_argument("--directed-frac", type=float, default=0.5)
    ap.add_argument("--n-sources", type=int, default=0, help="0 = 随机 10–16 个")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--figure", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--budget", type=float, default=DEFAULT_VIRTUAL_BUDGET)
    ap.add_argument("--grid-a", type=float, default=P4Config.grid_a)
    ap.add_argument("--outer-rings", default=None,
                    help="外侧补漏环，格式 r1:n1,r2:n2；默认取 P4Config 的值，"
                         "留空字符串表示不加外环")
    ap.add_argument("--spiral-w", type=float, default=0.35)
    ap.add_argument("--plan-tour", default="0",
                    help="仅 grid：0 = 逐站贪心走完旧模型判定的有用站位；"
                         "1 = 最小覆盖集 + 半径偏置 TSP（快 ~10%%，有 ~0.4%% 漏源风险）")
    ap.add_argument("--replan-every", type=int, default=0,
                    help="每走这么多站重排一次航线（0 = 不重排）")
    ap.add_argument("--geometry", action="store_true", help="只做几何自检")
    ap.add_argument("--url", default="http://127.0.0.1:2026")
    ap.add_argument("--robot-id", default="")
    ap.add_argument("--timeout", type=float, default=5.0)
    args = ap.parse_args()

    if args.outer_rings is None:
        rings = tuple(P4Config.outer_rings)
    else:
        rings = []
        for spec in (args.outer_rings or "").split(","):
            spec = spec.strip()
            if spec:
                r, n = spec.split(":")
                rings.append((float(r), int(n)))
        rings = tuple(rings)
    cfg = P4Config(grid_a=args.grid_a, outer_rings=rings,
                   spiral_radius_w=args.spiral_w,
                   plan_tour=bool(int(args.plan_tour)),
                   replan_every=int(args.replan_every))
    if args.policy=='joint':
        from p4_search import tier_config
        cfg=tier_config(args.tier)
    elif args.policy=='compact':
        from p4_compact import compact_config
        cfg=compact_config(args.tier)

    if args.geometry:
        geometry_report(args)
        return

    if args.mode == "live":
        if not args.robot_id:
            raise SystemExit("live 模式必须提供 --robot-id（参赛队号）")
        d = os.path.join(args.out, time.strftime("live_%Y%m%d_%H%M%S"))
        arena = HttpArena(base_url=args.url, robot_id=args.robot_id,
                          timeout=args.timeout,
                          log_path=os.path.join(d, "protocol.jsonl"))
        rb = make_robot(arena, cfg, log=print)
        print(f"连接模拟器 {args.url}（队号 {args.robot_id}）；"
              f"若接口尚未开放会自动等待重试…")
        try:
            rep = rb.run()
            rep['exit_per_cleared_s']=(rep['virtual_time_s']/rep['cleared'] if rep['cleared'] else None)
        except ArenaError as e:
            print(f"\n[失败] {e}")
            print("请确认：① 模拟器已在线登录；② 已开始『问题4 演练测试/正式测试』；"
                  "③ 5 秒倒计时结束、界面提示机器狗接口已就绪；④ 端口一致。")
            write_json(os.path.join(d, "error.json"), {"error": repr(e), "url": args.url})
            raise SystemExit(2)
        rep["url"] = args.url
        rep["scenario"] = "live"
        write_json(os.path.join(d, "summary.json"), rep)
        print(json.dumps({k: v for k, v in rep.items()
                          if k not in ("truth", "mock_stats", "channels", "stations")},
                         ensure_ascii=False, indent=2, default=_json_default))
        print(f"\n结果已写入 {d}")
        return

    seeds = [args.seed + 100 * i for i in range(args.cases)]
    reps = []
    t0 = time.time()
    for s in seeds:
        rep = run_mock_case(s, cfg, scenario=args.scenario, outdir=args.out,
                            verbose=args.verbose, figure=args.figure,
                            budget_s=args.budget,
                            n_sources=(args.n_sources or None),directed_frac=args.directed_frac)
        reps.append(rep)
        exit_avg=(f"{rep['exit_per_cleared_s']:.1f}" if rep['exit_per_cleared_s'] is not None else '—')
        print(f"  seed={s} 清除 {rep['cleared']}/{rep['n_sources']}"
              f"（定向 {rep['n_directed']}）｜定位清除 {rep['avg_clear_time_s']:.1f} s"
              f"｜完整退出 {rep['virtual_time_s']:.0f} s"
              f"（每源 {exit_avg} s）｜检测 {rep['n_measure']}"
              f"｜站位 {rep['stations_visited']}/{rep['stations_total']}"
              f"｜行程 {rep['travel_m']:.0f} m", flush=True)
    agg = aggregate(reps)
    agg["wall_s"] = round(time.time() - t0, 2)
    print()
    print(json.dumps(agg, ensure_ascii=False, indent=2, default=_json_default))
    write_json(os.path.join(args.out, f"benchmark_{args.scenario}.json"),
               {"cfg": cfg.__dict__, "seeds": seeds, "scenario": args.scenario,
                "aggregate": agg,
                "cases": [{k: v for k, v in r.items()
                           if k not in ("truth", "channels", "stations")} for r in reps]})
    with open(os.path.join(args.out, f"benchmark_{args.scenario}.csv"), "w",
              newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        cols = ["seed", "n_sources", "n_directed", "cleared", "clear_ratio",
                "avg_clear_time_s", "virtual_time_s", "exit_per_cleared_s", "program_runtime_s",
                "n_measure", "stations_visited", "n_locate", "n_clear",
                "n_clear_fail", "travel_m", "n_rejected"]
        w.writerow(cols)
        for r in reps:
            w.writerow([r.get(c) for c in cols])
    print(f"\n结果已写入 {args.out}")


if __name__ == "__main__":
    main()
