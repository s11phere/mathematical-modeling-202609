"""深挖 live 局：重建机器狗轨迹、用方位反演真源位置、算出"最远的源到底离探索点多远"。

    python src/p3_live_deep.py out/p3/live_20260911_151432
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys

import numpy as np


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    d = sys.argv[1]
    prot = load_jsonl(os.path.join(d, "protocol.jsonl"))

    order = []                     # [(path, payload, resp)]
    pending = collections.defaultdict(list)
    for r in prot:
        k = r.get("kind")
        if k == "req":
            pending[r["path"]].append(r["payload"])
        elif k == "resp":
            p = r.get("path")
            if pending[p]:
                order.append((p, pending[p].pop(0), r["resp"]))

    bearings = collections.defaultdict(list)
    measures = []      # (t, x, y, ch, result)
    wall = []
    for (p, pl, rp) in order:
        if p == "/measure":
            t = rp.get("virtual_time_s")
            x, y = pl["position"]["x"], pl["position"]["y"]
            measures.append((t, x, y, pl["channel"], rp.get("measure_result")))
            if rp.get("measure_result") == "direction":
                bearings[pl["channel"]].append((x, y, rp["svd_deg"]))

    # ---------- 1) 用方位做最小二乘反演真源 ----------
    def estimate(bl):
        """min sum (sin(a)*(y-ya) - cos(a)*(x-xa))^2 的线性最小二乘。"""
        A, b = [], []
        for (x, y, a) in bl:
            ra = math.radians(a)
            A.append([-math.sin(ra), math.cos(ra)])
            b.append(-math.sin(ra) * y + math.cos(ra) * x)
        A = np.asarray(A); b = np.asarray(b)
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        res = A @ sol - b
        return sol, float(np.sqrt(np.mean(res ** 2)))   # 残差（米）

    est = {}
    print("=== 由方位反演的真源位置（残差 = 与 ±1° 误差一致的量级）===")
    for ch in sorted(bearings):
        sol, rms = estimate(bearings[ch])
        est[ch] = sol
        print(f"  ch{ch:>2}: ({sol[0]:8.1f}, {sol[1]:8.1f})  |G|={np.hypot(*sol):7.1f} m  "
              f"n={len(bearings[ch])}  拟合残差 {rms:6.1f} m")

    # ---------- 2) 轨迹 + 每个停点到"还没清除的源"的最短距离 ----------
    clr_t = {}
    for (p, pl, rp) in order:
        if p == "/clear" and rp.get("clear_result") == "success":
            clr_t[pl["channel"]] = rp.get("virtual_time_s")

    print("\n=== 停点与剩余源的距离 ===")
    print(f"{'t(s)':>8} {'x':>8} {'y':>8} {'|p|':>6} {'检测结果':>28} "
          f"{'清除进度':>10} {'与最近未清源距离':>18}")
    seen_sig = set()
    for (t, x, y, ch, res) in measures:
        if res == "direction":
            seen_sig.add(ch)
    last_t = None
    for (t, x, y, ch, res) in measures:
        # 只打印"新停点"（位置变化）或方向读数
        if last_t is not None and abs(t - last_t) < 12 and res != "direction":
            continue
        last_t = t
        cleared_now = sum(1 for c, tc in clr_t.items() if tc <= t)
        rem = [c for c in est if c not in clr_t or clr_t[c] > t]
        dmin = min((math.hypot(x - est[c][0], y - est[c][1]) for c in rem), default=None)
        mark = " ★方位" if res == "direction" else ""
        print(f"{t:8.1f} {x:8.1f} {y:8.1f} {math.hypot(x, y):6.0f} "
              f"{res:>28} {cleared_now:>10} "
              f"{(f'{dmin:8.0f} m  (ch{min(rem, key=lambda c: math.hypot(x-est[c][0], y-est[c][1]))})' if dmin is not None else '-'):>18}{mark}")

    # ---------- 3) 时间空洞 ----------
    print("\n=== 虚拟时间推进的空洞（Δt > 90 s 的相邻动作）===")
    ts = [(rp.get("virtual_time_s"), p, pl) for (p, pl, rp) in order]
    ts = [x for x in ts if x[0] is not None]
    for (t0, p0, _), (t1, p1, pl1) in zip(ts, ts[1:]):
        if t1 - t0 > 90:
            print(f"  {t0:8.1f} -> {t1:8.1f}  ({t1-t0:6.1f} s)  {p0} -> {p1} "
                  f"{(pl1.get('position') or {})} ch{pl1.get('channel')}")

    # ---------- 4) 各未清除频道"被检测过的最深位置" ----------
    print("\n=== 从未测到方向的频道：检测点分布 ===")
    for ch in range(1, 21):
        ms = [(t, x, y) for (t, x, y, c, r) in measures if c == ch and r == "no_signal"]
        if not ms or ch in bearings:
            continue
        ds = [math.hypot(x - est[ch][0], y - est[ch][1]) for (t, x, y) in ms] if ch in est else []
        print(f"  ch{ch:>2}: {len(ms)} 次 no_signal，" 
              + (f"离真源最近 {min(ds):.0f} m（应在有效接收半径 1000~1500 m 内）" if ds else "（无方位，无法反演）"))


if __name__ == "__main__":
    main()
