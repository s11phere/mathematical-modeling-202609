"""四种航路排法的完整对照（含"绕圈 + 动态就近"的混合）。

A tsp          几何最短（全局 NN + 2-opt + cheapest-insertion 多起点取优）
B spiral       问题 3 式绕圈（环内角向单调、环间就近衔接、方向交替）
C spiral+动态  绕圈定"去哪一环"，环内每步取最近（问题 3 的 pick_stop 思路）
D 动态最近邻   每步在所有有用站里取最近

    python src/p4_route_ab.py --cases 30
"""
from __future__ import annotations

import argparse
import os
import statistics as S
import sys

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
from p4_why import DynNN  # noqa: E402


class SpiralDyn(P4GridRobot):
    """绕圈 + 动态就近：航线仍是螺旋（决定"当前在哪一环"），
    但每一步在**当前环内**取离自己最近的站（问题 3 `pick_stop` 的"就近 + 单调"折中）。"""

    def next_scan_station(self, flip=None):
        if not self.unheard():
            return None

        def usable(si):
            return (si not in self.visited_stations
                    and self.station_gain(si, self.unheard_mask())
                    > self.cfg.station_min_gain)

        while self._queue and not usable(self._queue[0]):
            self._queue.pop(0)
        if not self._queue:
            return None
        # 当前环 = 队首所在环；只在这一环里就近选（环扫完才进下一环）
        band = max(150.0, float(self.cfg.grid_a) * float(self.cfg.ring_band_frac))
        ring0 = int(round(float(np.hypot(*self.stations[self._queue[0]])) / band))
        pos = np.asarray(self.pos, float)
        cand = [si for si in self._queue
                if int(round(float(np.hypot(*self.stations[si])) / band)) == ring0
                and usable(si)]
        pool = cand or [si for si in self._queue if usable(si)]
        return min(pool, key=lambda si: float(np.hypot(
            *(np.asarray(self.stations[si], float) - pos))))


def run(cls, mode, cases, seed, frac, gain=90.0):
    cfg = P4Config(route_mode=mode, station_min_gain=gain)
    tot = cl = full = 0
    vt, tv, mx, nj, stn = [], [], [], [], []
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
        st = rb.stations
        order = []
        for e in rb.events:
            m = e["msg"]
            if m.startswith("站位 ") and "｜待测" in m:
                order.append(int(m.split("站位 ")[1].split("/")[0]))
        cur = np.asarray((0.0, 0.0))
        mm = 0.0
        nb = 0
        for si in order:
            q = np.asarray(st[si], float)
            d = float(np.hypot(*(q - cur)))
            mm = max(mm, d)
            nb += d > 1300
            cur = q
        mx.append(mm)
        nj.append(nb)
    return {"ratio": cl / tot, "full": full, "cases": cases,
            "avg": S.mean(vt) / (cl / cases), "vtime": S.mean(vt),
            "travel": S.mean(tv), "jump": S.mean(mx), "njump": S.mean(nj),
            "stn": S.mean(stn)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--scenario", default="mixed",
                    choices=["mixed", "only", "edge", "omni"])
    a = ap.parse_args()
    frac = {"mixed": 0.5, "only": 1.0, "edge": 0.5, "omni": 0.0}[a.scenario]
    print(f"场景 {a.scenario}，{a.cases} 局（seed {a.seed}+100i）")
    hdr = (f"{'航路':<20}{'清除率':>8}{'全清':>8}{'平均定位清除':>12}"
           f"{'虚拟':>8}{'行程':>9}{'站间单跳':>10}{'长跳/局':>9}{'站次':>7}")
    print(hdr)
    print("-" * len(hdr))
    rows = [("A tsp", P4GridRobot, "tsp"),
            ("B spiral", P4GridRobot, "spiral"),
            ("C spiral+动态就近", SpiralDyn, "spiral"),
            ("D 动态最近邻", DynNN, "spiral")]
    for (lbl, cls, mode) in rows:
        r = run(cls, mode, a.cases, a.seed, frac)
        full = f"{r['full']}/{r['cases']}"
        print(f"{lbl:<20}{r['ratio']:>8.4f}{full:>8}{r['avg']:>12.0f}"
              f"{r['vtime']:>8.0f}{r['travel']:>9.0f}{r['jump']:>10.0f}"
              f"{r['njump']:>9.2f}{r['stn']:>7.1f}", flush=True)
