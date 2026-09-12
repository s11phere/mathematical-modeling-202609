"""问题 3 改进用的批量对照台（不进入正式交付，只服务于调参与回归）。

用法示例::

    python src/p3_bench.py --cases 30                       # 默认对照集
    python src/p3_bench.py --cases 30 --set onlap           # 指定对照集
    python src/p3_bench.py --cases 10 --only A,onlap        # 只跑其中几项

输出：一行一配置的汇总表（清除率 / 平均定位清除时间 / 虚拟时间 / 检测 / 行程 /
折返指标），并可选写出 JSON 供后续比对。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys
import time
from dataclasses import replace

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))

# Windows 控制台默认 GBK：中文与表格符号混排时容易抛 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena, MockSource, R_ARENA, V_ROBOT  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402
from p3_sweep import SweepConfig, SweepRobot  # noqa: E402

LIVE1 = [(2, 937, -782), (5, 363, 418), (6, -939, -1491), (9, 1652, -112),
         (10, 1606, -590), (11, -591, -82), (13, 18, -197), (14, 470, -1292),
         (18, 1024, 1242), (20, -316, 241)]
LIVE2 = [(1, 693, -1157), (2, 722, 1401), (4, 288, 1723), (6, 622, 86),
         (8, 1066, 1008), (10, 1060, -550), (11, -386, 628), (14, 1378, 265),
         (15, 56, 734), (16, -722, -719), (17, 279, 945), (18, 1746, -247),
         (19, -509, 1384), (20, 498, 769)]


def arena_from(sources, r_recv=1400.0, seed=0, budget=360000.0):
    return MockArena(seed=seed, budget_s=budget,
                     sources=[MockSource(c, x, y, r_recv) for (c, x, y) in sources])


def outer_annulus(seed=0, n=12, r_lo=1300.0, r_hi=1800.0, budget=360000.0):
    rng = np.random.default_rng(seed)
    chans = rng.choice(np.arange(1, 21), size=n, replace=False)
    out = []
    for ch in chans:
        r = math.sqrt(rng.uniform(r_lo ** 2, r_hi ** 2))
        a = rng.uniform(0, 2 * math.pi)
        out.append(MockSource(int(ch), r * math.cos(a), r * math.sin(a),
                              float(rng.uniform(1000.0, 1500.0))))
    return MockArena(seed=seed, sources=out, budget_s=budget)


def center_cluster(seed=0, n=12, budget=360000.0):
    out = []
    rng = np.random.default_rng(seed)
    for c in range(1, n + 1):
        r = rng.uniform(0, 260.0)
        a = rng.uniform(0, 2 * math.pi)
        out.append(MockSource(c, r * math.cos(a), r * math.sin(a),
                              float(rng.uniform(1000.0, 1500.0))))
    return MockArena(seed=seed, sources=out, budget_s=budget)


# --------------------------------------------------------------------------
def path_metrics(acts, robot=None):
    """路径形态指标：折返（相邻两段夹角 > 120°）次数与折返累计距离。

    用户关心的"大量折返 / 绕远路"需要一个可量化的代理指标：把动作序列看成折线，
    统计"转弯角 > 120° 且折返段长度 > 150 m"的段数（记为 ``u_turns``）以及这些段
    的总长度（``u_m``）。纯绕圈 + 顺路清除的理想路径此值应接近 0。
    """
    pts = [(0.0, 0.0)] + [(a["x"], a["y"]) for a in acts
                          if a.get("kind") in ("measure", "clear")
                          and "x" in a and "y" in a]
    # 去掉原地重复点
    P = []
    for p in pts:
        if not P or math.dist(P[-1], p) > 1.0:
            P.append(p)
    u_turns, u_m, max_u = 0, 0.0, 0.0
    for i in range(1, len(P) - 1):
        a = np.asarray(P[i - 1], float)
        b = np.asarray(P[i], float)
        c = np.asarray(P[i + 1], float)
        v1, v2 = b - a, c - b
        n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        if n1 < 30.0 or n2 < 30.0:
            continue
        cosang = float((v1 / n1) @ (v2 / n2))
        ang = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
        if ang > 120.0:
            u_turns += 1
            u_m += n2
            max_u = max(max_u, n2)
    return {"u_turns": u_turns, "u_m": u_m, "u_max_m": max_u, "n_seg": len(P) - 1}


def run_one(cls, cfg, arena, base, want_path=False):
    rb = cls(arena, cfg, base=base, log=None)
    t0 = time.time()
    rep = rb.run()
    rep["_wall"] = time.time() - t0
    st_ = getattr(arena, "stats", {}) or {}
    rep["travel_m"] = float(st_.get("travel_m", 0.0))
    if want_path:
        rep.update(path_metrics(getattr(arena, "actions", [])))
        rep["_actions"] = [(a["x"], a["y"], a.get("kind"), a.get("virtual_time_s"))
                           for a in getattr(arena, "actions", [])
                           if "x" in a and "y" in a]
    return rep


def summarize(reps):
    cl = sum(r["cleared"] for r in reps)
    tot = sum(r["n_sources"] for r in reps)
    tm = [r["avg_clear_time_s"] for r in reps if r["avg_clear_time_s"]]
    idle = []
    for r in reps:
        last = (r["avg_clear_time_s"] or 0) * r["cleared"]
        idle.append((r["virtual_time_s"] - last) / max(r["virtual_time_s"], 1e-9))
    return {
        "clear_ratio": cl / tot if tot else 0.0,
        "cleared_mean": st.mean(r["cleared"] for r in reps),
        "full_clear_cases": sum(1 for r in reps if r["cleared"] == r["n_sources"]),
        "cases": len(reps),
        "avg_clear_time_s": st.mean(tm) if tm else 0.0,
        "vtime_s": st.mean(r["virtual_time_s"] for r in reps),
        "n_measure": st.mean(r["n_measure"] for r in reps),
        "travel_m": st.mean(r["travel_m"] for r in reps),
        "idle": st.mean(idle),
        "u_turns": st.mean(r.get("u_turns", 0) for r in reps),
        "u_m": st.mean(r.get("u_m", 0.0) for r in reps),
        "wall_s": st.mean(r["_wall"] for r in reps),
        "n_rejected": sum(r["n_rejected"] for r in reps),
    }


def fmt_row(name, s):
    return (f"{name:<26}{s['clear_ratio']:>8.3f}{s['cleared_mean']:>8.2f}"
            f"{s['full_clear_cases']:>6}/{s['cases']:<3}"
            f"{s['avg_clear_time_s']:>9.1f}{s['vtime_s']:>9.0f}"
            f"{s['n_measure']:>7.0f}{s['travel_m']:>9.0f}"
            f"{s['idle']:>8.1%}{s['u_turns']:>7.1f}{s['u_m']:>8.0f}"
            f"{s['wall_s']:>7.2f}")


HDR = (f"{'配置':<26}{'清除率':>8}{'平均清除':>8}{'全清':>9}"
       f"{'定位清除/s':>9}{'虚拟/s':>9}{'检测':>7}{'行程/m':>9}"
       f"{'空转':>8}{'折返':>7}{'折返/m':>8}{'实跑':>7}")


# --------------------------------------------------------------------------
def variant_sets(names=None, cfg_over=None):
    """候选配置。键为名字，值为 ``(robot_cls, cfg, extra_kwargs)``。"""
    from dataclasses import replace as _rep
    from p3_tour import TourConfig, TourRobot
    over = cfg_over or {}
    tc = _rep(TourConfig(), **over) if over else TourConfig()
    tag = "E_统一航路" + ("" if not over else "(" + ",".join(
        f"{k}={v}" for k, v in over.items() if k in ("cover_rings",)) + ")")
    A = ("A_基线(扫圈)", SweepRobot, SweepConfig(), {})
    B = ("B_边绕边清", SweepRobot,
         SweepConfig(onlap_clear=True), {})
    C = ("C_边绕边清+开场定点", SweepRobot,
         SweepConfig(onlap_clear=True, initial_locate=True), {})
    D = ("D_期望场贪心", P3Robot, P3Config(), {})
    E = (tag, TourRobot, tc, {})
    sets = {"base": [A], "onlap": [A, B, C, D], "all": [A, D, E],
            "tour": [E], "cmp": [A, D, E]}
    if names:
        keys = [n.strip() for n in names.split(",") if n.strip()]
        out = []
        for k in keys:
            for item in sets.get(k, []):
                out.append(item)
        return out
    return sets["all"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--step", type=int, default=100)
    ap.add_argument("--scenario", default="random",
                    choices=["random", "annulus", "live1", "live2", "center"])
    ap.add_argument("--set", default="all")
    ap.add_argument("--only", default="")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--cfg", default="", help='TourConfig 覆盖（JSON），如 {"cover_rings":[[950,9]]}')
    args = ap.parse_args()

    base = load_base()
    seeds = [args.seed + args.step * i for i in range(args.cases)]

    def mk(seed):
        if args.scenario == "random":
            return MockArena(seed=seed)
        if args.scenario == "annulus":
            return outer_annulus(seed=seed)
        if args.scenario == "center":
            return center_cluster(seed=seed)
        if args.scenario == "live1":
            return arena_from(LIVE1, seed=seed)
        return arena_from(LIVE2, seed=seed)

    rows = variant_sets(args.set, cfg_over=(json.loads(args.cfg) if args.cfg else None))
    if args.only:
        keep = {k.strip() for k in args.only.split(",") if k.strip()}
        rows = [r for r in rows if r[0].split("_")[0] in keep or r[0] in keep]

    print(f"场景 {args.scenario}，{args.cases} 局（seed {seeds[0]}..{seeds[-1]}）")
    print(HDR)
    print("-" * len(HDR))
    store = {}
    for name, cls, cfg, kw in rows:
        reps = [run_one(cls, cfg, mk(s), base, want_path=True) for s in seeds]
        s = summarize(reps)
        store[name] = {**s, "per_case": [
            {k: v for k, v in r.items() if not k.startswith("_") and k != "truth"
             and k != "channels" and k != "mock_stats"} for r in reps]}
        print(fmt_row(name, s), flush=True)
    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n-> {args.json_out}")


if __name__ == "__main__":
    main()
