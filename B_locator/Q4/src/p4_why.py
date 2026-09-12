"""把两轮的关键差异逐项拆开：配置、航路排法、站数、指标。

    python src/p4_why.py --cases 20
"""
from __future__ import annotations

import argparse
import os
import statistics as S
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from p4_arena_ext import directed_case  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402


class DynNN(P4GridRobot):
    """上一轮的排法：每步在"还有收益的站"里取最近（动态最近邻）。"""

    def next_scan_station(self, flip=None):
        cover = self.unheard_mask()
        if not cover.any():
            return None
        w = float(self.cfg.skeleton_radius_w)
        pos = np.asarray(self.pos, float)
        best, best_key = None, None
        for si, (x, y) in enumerate(self.stations):
            if si in self.visited_stations:
                continue
            if self.station_gain(si, cover) <= self.cfg.station_min_gain:
                continue
            key = float(np.hypot(x - pos[0], y - pos[1])) + w * float(np.hypot(x, y))
            if best_key is None or key < best_key:
                best, best_key = si, key
        return best


def metrics(cls, cfg, cases, seed, frac):
    tot = cl = full = 0
    vt, tv, stn = [], [], []
    t0 = time.time()
    per = []
    for i in range(cases):
        arena, _ = directed_case(seed + 100 * i, directed_frac=frac)
        rb = cls(arena, cfg)
        rep = rb.run()
        tot += rep["n_sources"]
        cl += rep["cleared"]
        vt.append(rep["virtual_time_s"])
        tv.append(rep["travel_m"])
        stn.append(len(rb.visited_stations))
        if rep["cleared"] == rep["n_sources"]:
            full += 1
        per.append((seed + 100 * i, rep["n_sources"], rep["cleared"],
                    rep["avg_clear_time_s"], rep["virtual_time_s"]))
    return {"ratio": cl / tot, "full": full, "cases": cases,
            "avg_clear": S.mean(vt) / (cl / cases),
            "vtime": S.mean(vt), "travel": S.mean(tv),
            "stations": S.mean(stn), "wall": time.time() - t0, "per": per}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260914)
    a = ap.parse_args()

    print(f"混合场景（定向占比 0.5），{a.cases} 局，seed {a.seed}+100i\n")
    print(f"{'配置':<40}{'清除率':>8}{'全清':>7}{'平均定位清除':>13}"
          f"{'虚拟':>8}{'行程':>9}{'站次':>7}")
    print("-" * 92)
    rows = [
        ("上一轮：动态最近邻 + 外环12 + gain=90",
         DynNN, P4Config(station_min_gain=90.0, outer_rings=((1850.0, 12),))),
        ("本轮：基准航线 + 外环12 + gain=250",
         P4GridRobot, P4Config()),
        ("对照：基准航线 + 外环12 + gain=90",
         P4GridRobot, P4Config(station_min_gain=90.0)),
        ("对照：基准航线 + 外环18 + gain=250（旧 CLI 默认）",
         P4GridRobot, P4Config(outer_rings=((1850.0, 18),), station_min_gain=250.0)),
    ]
    out = {}
    for (lbl, cls, cfg) in rows:
        r = metrics(cls, cfg, a.cases, a.seed, 0.5)
        out[lbl] = r
        print(f"{lbl:<40}{r['ratio']:>8.4f}{f'{r[chr(102)+chr(117)+chr(108)+chr(108)]}/{r[chr(99)+chr(97)+chr(115)+chr(101)+chr(115)]}':>7}"
              f"{r['avg_clear']:>13.0f}{r['vtime']:>8.0f}{r['travel']:>9.0f}"
              f"{r['stations']:>7.1f}", flush=True)

    print("\n逐局对比（虚拟时刻 / 平均定位清除，仅列差异 > 150 s 的局）：")
    k1 = "上一轮：动态最近邻 + 外环12 + gain=90"
    k2 = "本轮：基准航线 + 外环12 + gain=250"
    p1 = {x[0]: x for x in out[k1]["per"]}
    p2 = {x[0]: x for x in out[k2]["per"]}
    n_better = n_worse = 0
    for s in sorted(p1):
        d = p2[s][3] - p1[s][3]
        if abs(d) <= 150:
            continue
        tag = "本轮更慢" if d > 0 else "本轮更快"
        n_worse += d > 0
        n_better += d < 0
        print(f"  seed {s}  源 {p1[s][1]:2d}  上轮 {p1[s][3]:5.0f} s -> "
              f"本轮 {p2[s][3]:5.0f} s  ({d:+.0f} s)  {tag}")
    print(f"\n  本轮更快的局 {n_better} 个，更慢的局 {n_worse} 个")


if __name__ == "__main__":
    main()
