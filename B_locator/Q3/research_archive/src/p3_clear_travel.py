"""把一局的"站内行程"进一步拆开：清除过程中的逼近/精定位/试探各走了多少米。"""
from __future__ import annotations

import argparse
import math
import os
import statistics as st
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from p3_arena import MockArena, V_ROBOT  # noqa: E402
from p3_robot import load_base  # noqa: E402
from p3_tour import TourConfig, TourRobot  # noqa: E402


def run_one(seed, cfg, base):
    a = MockArena(seed=seed)
    rb = TourRobot(a, cfg, base=base, log=None)
    acc = {"visit_measure": 0.0, "clear_measure": 0.0, "clear_probe": 0.0,
           "clear_ok": 0.0, "other": 0.0}
    state = {"phase": "visit"}
    orig_m, orig_c = rb.measure, rb.do_clear
    orig_ct = rb.clear_target

    def meas(x, y, ch):
        d = math.dist(rb.pos, (float(x), float(y)))
        if state["phase"] == "clear":
            acc["clear_measure"] += d
        else:
            acc["visit_measure"] += d
        return orig_m(x, y, ch)

    def clr(x, y, ch):
        d = math.dist(rb.pos, (float(x), float(y)))
        acc["clear_probe"] += d
        r = orig_c(x, y, ch)
        if r:
            acc["clear_ok"] += 5.0
        return r

    def ct(ch, rec):
        state["phase"] = "clear"
        try:
            return orig_ct(ch, rec)
        finally:
            state["phase"] = "visit"

    rb.measure, rb.do_clear, rb.clear_target = meas, clr, ct
    rep = rb.run()
    return rep, acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260913)
    a = ap.parse_args()
    base = load_base()
    tot = {}
    for i in range(a.cases):
        s = a.seed + 100 * i
        rep, acc = run_one(s, TourConfig(), base)
        for k, v in acc.items():
            tot[k] = tot.get(k, 0.0) + v
        print(f"seed {s}: 总行程 {rep['travel_m']:>7.0f}  "
              f"访问测量 {acc['visit_measure']:>7.0f}  清除逼近 {acc['clear_measure']:>7.0f}  "
              f"试探移动 {acc['clear_probe']:>7.0f}  清除耗时 {acc['clear_ok']:>5.0f}s")
    print("\n均值：")
    for k, v in sorted(tot.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<16}{v/a.cases:>9.0f}")


if __name__ == "__main__":
    main()
