"""在 `p3_paths` 的 6 组本地场景上对比两套配置（默认 vs 关掉某机制）。"""
from __future__ import annotations

import argparse
import math
import os
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

import p3_paths  # noqa: E402
from p3_robot import load_base  # noqa: E402
from p3_tour import TourConfig, TourRobot  # noqa: E402


def metrics(acts):
    pts = [(0.0, 0.0)] + [(a["x"], a["y"]) for a in acts if "x" in a]
    P = []
    for p in pts:
        if not P or math.dist(P[-1], p) > 1.0:
            P.append(p)
    un, um = 0, 0.0
    for i in range(1, len(P) - 1):
        v1 = np.asarray(P[i], float) - np.asarray(P[i - 1], float)
        v2 = np.asarray(P[i + 1], float) - np.asarray(P[i], float)
        n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        if n1 < 30 or n2 < 30:
            continue
        ang = math.degrees(math.acos(max(-1, min(1, float((v1 / n1) @ (v2 / n2))))))
        if ang > 120.0:
            un += 1
            um += n2
    return un, um


VARIANTS = {
    "默认": {},
    "关 offroute": dict(offroute_clear=False),
    "关入口优选": dict(entry_select=False),
    "两个都关": dict(offroute_clear=False, entry_select=False),
    "关 risk/sector": dict(risk_locate=False, sector_clear_m=0.0),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default="")
    a = ap.parse_args()
    base = load_base()
    keys = [k.strip() for k in a.keys.split(",") if k.strip()] or list(VARIANTS)
    hdr = (f"{'场景':<16}{'配置':<22}{'清除':>8}{'虚拟/s':>9}{'行程/m':>9}"
           f"{'检测':>6}{'折返':>6}{'折返/m':>8}")
    print(hdr)
    print("-" * len(hdr))
    for i, (tag, note, _aren0, _cfg0) in enumerate(p3_paths.scenarios()):
        for name in keys:
            cfg = replace(TourConfig(), **VARIANTS[name])
            # 每次重建场景（arena 是一次性对象，不能重复 /enter）
            aren = p3_paths.scenarios()[i][2]
            rb = TourRobot(aren, cfg, base=base, log=None)
            rep = rb.run()
            un, um = metrics(getattr(aren, "actions", []))
            print(f"{tag:<16}{name:<22}"
                  f"{rep['cleared']:>4}/{rep['n_sources']:<3}{rep['virtual_time_s']:>9.0f}"
                  f"{rep['travel_m']:>9.0f}{rep['n_measure']:>6}{un:>6}{um:>8.0f}",
                  flush=True)


if __name__ == "__main__":
    main()
