"""TourRobot 单局详细剖析：停点序列 / 检测分类 / 段长与折返。

    python src/p3_tour_diag.py --seed 20260913
    python src/p3_tour_diag.py --cases 12 --summary
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import statistics as st
import sys
from dataclasses import replace

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena  # noqa: E402
from p3_robot import load_base  # noqa: E402
from p3_tour import TourConfig, TourRobot  # noqa: E402


def run_one(seed, cfg, base, verbose=False, scenario="random"):
    from p3_bench import LIVE1, LIVE2, arena_from, outer_annulus, center_cluster
    if scenario == "random":
        a = MockArena(seed=seed)
    elif scenario == "annulus":
        a = outer_annulus(seed=seed)
    elif scenario == "center":
        a = center_cluster(seed=seed)
    elif scenario == "live1":
        a = arena_from(LIVE1, seed=seed)
    elif scenario.startswith("paths"):
        # 复刻 `p3_paths.py` 的场景（A/C/D/E/F），便于对照路径图
        import p3_paths
        tag = {"pathsA": "A_默认种子", "pathsC": "C_live复刻",
               "pathsD": "D_外圈环带", "pathsE": "E_中心密集",
               "pathsF": "F_无信息陷阱"}[scenario]
        scen = {t: (no, ar, cf) for (t, no, ar, cf) in p3_paths.scenarios()}
        _no, a, _cfg = scen[tag]
    else:
        a = arena_from(LIVE2, seed=seed)
    rb = TourRobot(a, cfg, base=base, log=(print if verbose else None))
    kinds = collections.Counter()
    orig = rb.chans_at

    def patched(x, y, ch=None, cover_duty=False):
        out = orig(x, y, ch, cover_duty=cover_duty)
        for c in out:
            rec = rb.recs[c]
            if ch is not None and c == int(ch):
                kinds["target"] += 1
            elif rec.n_bearings == 0:
                kinds["unheard"] += 1
            elif rec.n_bearings == 1:
                kinds["one_bearing"] += 1
            else:
                kinds["multi"] += 1
        return out
    rb.chans_at = patched
    rep = rb.run()
    return a, rb, rep, kinds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--cases", type=int, default=0)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--cfg", default="")
    ap.add_argument("--scenario", default="random")
    a = ap.parse_args()
    base = load_base()
    over = json.loads(a.cfg) if a.cfg else {}
    cfg = replace(TourConfig(), **over) if over else TourConfig()

    if a.summary and a.cases:
        rows = []
        for i in range(a.cases):
            s = a.seed + 100 * i
            aren, rb, rep, kinds = run_one(s, cfg, base, scenario=a.scenario)
            rows.append((s, rep, kinds, rb))
        print(f"{a.cases} 局：清除率 "
              f"{sum(r[1]['cleared'] for r in rows)}/{sum(r[1]['n_sources'] for r in rows)}"
              f" = {sum(r[1]['cleared'] for r in rows)/sum(r[1]['n_sources'] for r in rows):.4f}；"
              f"T={st.mean(r[1]['virtual_time_s'] for r in rows):.0f}s；"
              f"T/N={st.mean(r[1]['virtual_time_s']/max(r[1]['cleared'],1) for r in rows):.1f}s；"
              f"检测={st.mean(r[1]['n_measure'] for r in rows):.0f}；"
              f"行程={st.mean(r[1]['travel_m'] for r in rows):.0f}m")
        agg = collections.Counter()
        for _s, _r, k, _rb in rows:
            agg.update(k)
        tot = sum(agg.values())
        print("检测分类：" + "  ".join(f"{k}={v}({v/tot:.0%})"
                                       for k, v in agg.most_common()))
        stopagg = collections.Counter()
        for _s, _r, _k, rb in rows:
            for e in rb.tour_log:
                stopagg[e["kind"] + ("*" if e.get("n_chans", 0) else "")] += 1
        print("停点类型：", dict(stopagg))
        for s, rep, _k, rb in rows:
            print(f"  seed {s}: 清 {rep['cleared']}/{rep['n_sources']} "
                  f"T={rep['virtual_time_s']:.0f} 行程={rep['travel_m']:.0f} "
                  f"检测={rep['n_measure']} 停点={len(rb.tour_log)} "
                  f"覆盖={rep.get('coverage')} 证明={rep.get('complete_proof')}")
        return

    aren, rb, rep, kinds = run_one(a.seed, cfg, base, scenario=a.scenario)
    print(f"seed {a.seed}: 清除 {rep['cleared']}/{rep['n_sources']} "
          f"T={rep['virtual_time_s']:.0f}s 行程={rep['travel_m']:.0f}m "
          f"检测={rep['n_measure']} 折返={sum(1 for _ in [])}")
    print("检测分类：", dict(kinds))
    for s in aren.truth()["sources"]:
        print(f"  真源 ch{s['channel']:>2} ({s['x_m']:>7.0f},{s['y_m']:>7.0f}) "
              f"r={math.hypot(s['x_m'], s['y_m']):>6.0f} r_recv={s['r_recv_m']:>5.0f} "
              f"{'已清' if s['cleared'] else '未清'}")
    prev = (0.0, 0.0)
    tprev = 0.0
    tot_seg = 0.0
    print(f"{'stop':>5}{'t/s':>8}{'Δt':>6}{'kind':>8}{'ch':>4}{'x':>8}{'y':>8}"
          f"{'r':>7}{'段长':>7}{'转角':>6}{'n':>4}")
    dirv = None
    for e in rb.tour_log:
        d = math.dist(prev, e["xy"])
        tot_seg += d
        turn = ""
        if d > 30:
            v = (np.asarray(e["xy"], float) - np.asarray(prev, float)) / d
            if dirv is not None:
                turn = f"{math.degrees(math.acos(max(-1,min(1,float(v@dirv))))):>6.0f}"
            dirv = v
        print(f"{e['stop']:>5}{e['t']:>8.0f}{e['t']-tprev:>6.0f}{e['kind']:>8}"
              f"{str(e['ch']):>4}{e['xy'][0]:>8.0f}{e['xy'][1]:>8.0f}"
              f"{math.hypot(*e['xy']):>7.0f}{d:>7.0f}{turn:>6}{e['n_chans']:>4}")
        prev = tuple(e["xy"])
        tprev = e["t"]
    print(f"站间总长 {tot_seg:.0f} m；总行程 {rep['travel_m']:.0f} m")


if __name__ == "__main__":
    main()
