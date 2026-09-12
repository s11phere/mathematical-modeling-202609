"""问题 3 诊断：一局跑完后拆解时间去向、未清除原因、路径折返。

    python src/p3_diag3.py --cases 30 --policy sweep
    python src/p3_diag3.py --cases 30 --policy sweep --cfg '{"onlap_clear": true}'
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
import os

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena, R_ARENA, V_ROBOT, T_CLEAR_FAIL, T_CLEAR_OK  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402
from p3_sweep import SweepConfig, SweepRobot  # noqa: E402


def make(policy, cfg_over=None):
    """按名字造策略类与配置。"""
    over = cfg_over or {}
    if policy == "tour":
        from p3_tour import TourConfig, TourRobot
        cls = TourRobot
        base_cfg = TourConfig()
    elif policy == "sweep":
        cls, base_cfg = SweepRobot, SweepConfig()
    else:
        cls, base_cfg = P3Robot, P3Config()
    cfg = type(base_cfg)(**{**base_cfg.__dict__, **over})
    return cls, cfg


def one(seed, policy, cfg, base, verbose=False):
    arena = MockArena(seed=seed)
    cls, _ = make(policy)
    rb = cls(arena, cfg, base=base, log=(lambda m: print("   " + m)) if verbose else None)
    rep = rb.run()
    acts = arena.actions
    # ---- 时间去向 ----
    tt = {"move": 0.0, "measure": 0.0, "clear_ok": 0.0, "clear_fail": 0.0, "switch": 0.0}
    for a in acts:
        if a.get("kind") == "measure":
            tt["move"] += a["dist_m"] / V_ROBOT
            tt["measure"] += 5.0
            tt["switch"] += a.get("switch_s", 0.0)
        elif a.get("kind") == "clear":
            tt["move"] += a["dist_m"] / V_ROBOT
            if a.get("clear_result") == "success":
                tt["clear_ok"] += T_CLEAR_OK
            else:
                tt["clear_fail"] += T_CLEAR_FAIL
    T = max(rep["virtual_time_s"], 1e-9)
    last_clear = (rep["avg_clear_time_s"] or 0.0) * rep["cleared"]
    # ---- 未清除原因 ----
    truth = arena.truth()
    miss = []
    for s in truth["sources"]:
        ch = s["channel"]
        if s["cleared"]:
            continue
        rec = rb.recs[ch]
        br = rb.bounded_region(rec)
        miss.append({
            "ch": ch, "x": round(s["x_m"]), "y": round(s["y_m"]),
            "r": round(math.hypot(s["x_m"], s["y_m"])),
            "r_recv": round(s["r_recv_m"]),
            "n_bear": rec.n_bearings,
            "status": rb.region(rec).get("status"),
            "r_star": (round(br["radius"]) if br else None),
            "n_meas": len(rec.meas_pts),
            "near": rec.near_hits,
        })
    # ---- 折返 ----
    pts = [(0.0, 0.0)] + [(a["x"], a["y"]) for a in acts if "x" in a]
    P = []
    for p in pts:
        if not P or math.dist(P[-1], p) > 1.0:
            P.append(p)
    turns = []
    for i in range(1, len(P) - 1):
        v1 = np.asarray(P[i], float) - np.asarray(P[i - 1], float)
        v2 = np.asarray(P[i + 1], float) - np.asarray(P[i], float)
        n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        if n1 < 30 or n2 < 30:
            continue
        ang = math.degrees(math.acos(max(-1, min(1, float((v1 / n1) @ (v2 / n2))))))
        if ang > 120.0:
            turns.append((round(ang), round(n2), (round(P[i][0]), round(P[i][1]))))
    return {
        "seed": seed, "cleared": rep["cleared"], "n": rep["n_sources"],
        "T": rep["virtual_time_s"], "T/N": rep["virtual_time_s"] / max(rep["cleared"], 1),
        "avg": rep["avg_clear_time_s"] or 0.0, "last_clear": last_clear,
        "idle_frac": (T - last_clear) / T,
        "travel": rep["travel_m"], "n_meas": rep["n_measure"],
        "tt": {k: round(v, 1) for k, v in tt.items()},
        "tf": {k: round(v / T, 3) for k, v in tt.items()},
        "miss": miss, "turns": turns,
        "n_clear": rep["n_clear"], "n_fail": rep["n_clear_fail"],
        "u_m": sum(t[1] for t in turns), "u_n": len(turns),
        "u_max": max([t[1] for t in turns], default=0),
        "scan_points": rep["scan_points"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--policy", default="sweep")
    ap.add_argument("--cfg", default="")
    ap.add_argument("--verbose-seed", type=int, default=0)
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()
    base = load_base()
    over = json.loads(args.cfg) if args.cfg else {}
    _cls, cfg = make(args.policy, over)

    seeds = [args.seed + 100 * i for i in range(args.cases)]
    rows = [one(s, args.policy, cfg, base,
                verbose=(args.verbose_seed and s == args.verbose_seed)) for s in seeds]

    print(f"\n=== {args.policy} {over}：{args.cases} 局 ===")
    print(f"清除率 {sum(r['cleared'] for r in rows)}/{sum(r['n'] for r in rows)}"
          f" = {sum(r['cleared'] for r in rows)/sum(r['n'] for r in rows):.4f}")
    print(f"总虚拟时间 {st.mean(r['T'] for r in rows):.0f} s；"
          f"T/N {st.mean(r['T/N'] for r in rows):.1f} s；"
          f"到最后一清 {st.mean(r['last_clear'] for r in rows):.1f} s；"
          f"空转占比 {st.mean(r['idle_frac'] for r in rows):.1%}")
    print(f"行程 {st.mean(r['travel'] for r in rows):.0f} m；检测 {st.mean(r['n_meas'] for r in rows):.1f} 次；"
          f"清除尝试 {st.mean(r['n_clear'] for r in rows):.1f}（失败 {st.mean(r['n_fail'] for r in rows):.2f}）")
    agg = {}
    for r in rows:
        for k, v in r["tt"].items():
            agg[k] = agg.get(k, 0.0) + v
    tot = sum(agg.values())
    print("时间去向：" + "  ".join(f"{k}={v:.0f}s({v/tot:.1%})" for k, v in
                                  sorted(agg.items(), key=lambda kv: -kv[1])))
    print(f"折返段（转角>120°）：{st.mean(r['u_n'] for r in rows):.1f} 段/局，"
          f"折返长度 {st.mean(r['u_m'] for r in rows):.0f} m/局，"
          f"最长一段 {st.mean(r['u_max'] for r in rows):.0f} m")

    print("\n每局明细：")
    hdr = f"{'seed':>10}{'清除':>7}{'T/s':>8}{'T/N':>7}{'末清/s':>8}{'空转':>7}{'行程':>8}{'检测':>6}{'折返':>6}{'折返/m':>8}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['seed']:>10}{r['cleared']:>4}/{r['n']:<3}{r['T']:>8.0f}{r['T/N']:>7.0f}"
              f"{r['last_clear']:>8.0f}{r['idle_frac']:>7.1%}{r['travel']:>8.0f}"
              f"{r['n_meas']:>6}{r['u_n']:>6}{r['u_m']:>8.0f}")

    bad = [r for r in rows if r["miss"]]
    if bad:
        print(f"\n未清除明细（{len(bad)} 局）：")
        for r in bad:
            print(f"  seed {r['seed']}: " + "; ".join(
                f"ch{m['ch']}@r={m['r']} r_recv={m['r_recv']} 方位{m['n_bear']}条 "
                f"状态{m['status']} r*={m['r_star']} 检测{m['n_meas']}次" for m in r["miss"]))
    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n-> {args.json_out}")


if __name__ == "__main__":
    main()
