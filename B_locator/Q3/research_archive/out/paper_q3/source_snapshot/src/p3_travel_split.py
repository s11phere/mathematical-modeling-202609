"""一局的时间/行程拆解：理想 TSP 下界 vs 实际，环线 vs 支线。"""
from __future__ import annotations
import json
import math
import os
import sys
import statistics as st

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena, R_ARENA, V_ROBOT  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402
from p3_sweep import SweepConfig, SweepRobot  # noqa: E402


def tour_len(pts, start=(0.0, 0.0)):
    k = len(pts)
    if k == 0:
        return 0.0
    P = [np.asarray(p, float) for p in pts]
    S = np.asarray(start, float)
    cur, left, seq = S, list(range(k)), []
    while left:
        j = min(left, key=lambda i: float(np.linalg.norm(P[i] - cur)))
        seq.append(j)
        left.remove(j)
        cur = P[j]

    def tot(o):
        d = float(np.linalg.norm(P[o[0]] - S))
        for a, b in zip(o, o[1:]):
            d += float(np.linalg.norm(P[b] - P[a]))
        return d

    best = tot(seq)
    imp = True
    while imp:
        imp = False
        for i in range(k - 1):
            for j in range(i + 1, k):
                c = seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]
                d = tot(c)
                if d < best - 1e-9:
                    seq, best, imp = c, d, True
    return best


def classify(acts, ring_r=1100.0, tol=120.0):
    """把每段行程归类：去环 / 环上 / 环外支线 / 环内。"""
    out = {"to_ring": 0.0, "on_ring": 0.0, "detour_out": 0.0, "inner": 0.0}
    prev = np.array([0.0, 0.0])
    for a in acts:
        if "x" not in a:
            continue
        p = np.array([a["x"], a["y"]])
        d = float(np.linalg.norm(p - prev))
        r0, r1 = float(np.linalg.norm(prev)), float(np.linalg.norm(p))
        if d > 1.0:
            if r0 < 200.0 and r1 > ring_r - tol:
                out["to_ring"] += d
            elif abs(r0 - ring_r) < tol and abs(r1 - ring_r) < tol:
                out["on_ring"] += d
            elif r1 > r0:
                out["detour_out"] += d
            else:
                out["inner"] += d
        prev = p
    return out


def main(cases=30, seed0=20260913, policy="sweep", cfg_over=None):
    base = load_base()
    cls, cfgcls = (SweepRobot, SweepConfig) if policy == "sweep" else (P3Robot, P3Config)
    cfg = cfgcls(**{**cfgcls().__dict__, **(cfg_over or {})})
    rows = []
    for i in range(cases):
        s = seed0 + 100 * i
        a = MockArena(seed=s)
        rb = cls(a, cfg, base=base, log=None)
        rep = rb.run()
        pts = [(x["x_m"], x["y_m"]) for x in a.truth()["sources"]]
        orl = tour_len(pts)
        cl = classify(a.actions)
        rows.append({"seed": s, "cleared": rep["cleared"], "n": rep["n_sources"],
                     "T": rep["virtual_time_s"], "travel": rep["travel_m"],
                     "oracle": orl, **cl})
    print(f"policy={policy} cfg_over={cfg_over}")
    keys = ["to_ring", "on_ring", "detour_out", "inner"]
    print(f"{'seed':>10}{'清除':>8}{'T/s':>8}{'行程':>8}{'理想TSP':>9}{'比值':>7}"
          + "".join(f"{k:>12}" for k in keys))
    for r in rows:
        print(f"{r['seed']:>10}{r['cleared']:>4}/{r['n']:<3}{r['T']:>8.0f}"
              f"{r['travel']:>8.0f}{r['oracle']:>9.0f}{r['travel']/max(r['oracle'],1):>7.2f}"
              + "".join(f"{r[k]:>12.0f}" for k in keys))
    m = lambda k: st.mean(r[k] for r in rows)
    print("-" * 90)
    print(f"{'均值':>10}{'':>8}{m('T'):>8.0f}{m('travel'):>8.0f}{m('oracle'):>9.0f}"
          f"{m('travel')/m('oracle'):>7.2f}" + "".join(f"{m(k):>12.0f}" for k in keys))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--policy", default="sweep")
    ap.add_argument("--cfg", default="")
    a = ap.parse_args()
    main(a.cases, policy=a.policy, cfg_over=(json.loads(a.cfg) if a.cfg else None))
