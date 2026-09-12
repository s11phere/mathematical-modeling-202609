"""复现 live 局 t≈1669 s 之后的决策场：为什么 E_norm=0、选点为什么在两个 x 符号间跳。

用与 live 相同的检测记录（从 protocol.jsonl 提取）重建 P3Robot 台账，然后打印
build_field / choose_scan_point 的中间量。
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from p3_robot import P3Config, P3Robot, load_base  # noqa: E402


def load_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def pair(prot):
    pending = collections.defaultdict(list)
    out = []
    for r in prot:
        k = r.get("kind")
        if k == "req":
            pending[r["path"]].append(r["payload"])
        elif k == "resp":
            p = r.get("path")
            if pending[p]:
                out.append((p, pending[p].pop(0), r["resp"]))
    return out


class FakeArena:
    """只记录状态，不做物理；用于喂给 P3Robot 复现决策。"""

    def __init__(self, base):
        self.base = base
        self.pos = (0.0, 0.0)
        self.channel = 1
        self.vtime = 0.0
        self.stats = {}
        self.actions = []

    @property
    def virtual_time_s(self):
        return self.vtime

    def remaining_budget_s(self):
        return 1200.0 - 0.0        # live 里由墙钟决定，这里给足

    def budget_kind(self):
        return "real"

    def truth(self):
        return None


def main():
    d = sys.argv[1]
    order = pair(load_jsonl(os.path.join(d, "protocol.jsonl")))
    base = load_base()
    cfg = P3Config()
    rb = P3Robot(FakeArena(base), cfg, base=base, log=None)

    # 重放 live 的检测/清除记录
    n_until = float(sys.argv[2]) if len(sys.argv) > 2 else 1669.4
    for (p, pl, rp) in order:
        t = rp.get("virtual_time_s")
        if t is None or t > n_until:
            continue
        rb.arena.vtime = float(t)
        rb.arena.pos = (pl["position"]["x"], pl["position"]["y"]) if "position" in pl else rb.arena.pos
        if p == "/measure":
            ch = pl["channel"]
            rec = rb.recs[int(ch)]
            rec.meas_pts.append((pl["position"]["x"], pl["position"]["y"]))
            rec.meas_log.append((pl["position"]["x"], pl["position"]["y"], t,
                                 rp.get("measure_result")))
            if rp.get("measure_result") == "direction":
                rb.add_bearing(ch, pl["position"]["x"], pl["position"]["y"], rp["svd_deg"])
                rb.scan_points.append((pl["position"]["x"], pl["position"]["y"]))
            elif rp.get("measure_result") == "near":
                rec.near_hits += 1
            else:
                rec.no_signal += 1
        elif p == "/clear":
            if rp.get("clear_result") == "success":
                rb.recs[int(pl["channel"])].cleared = True

    print(f"=== 重放到 t={n_until}s ===")
    print("频道台账：")
    for ch, rec in rb.recs.items():
        if rec.n_bearings or rec.cleared or rec.meas_pts:
            print(f"  ch{ch:>2} bearing={rec.n_bearings} cleared={rec.cleared} "
                  f"meas={len(rec.meas_pts)} nosig={rec.no_signal} "
                  f"last_bounded={rec.last_bounded}")
    print(f"scan_points({len(rb.scan_points)}) = {[(round(x), round(y)) for x, y in rb.scan_points]}")
    print(f"当前位置 {rb.arena.pos}")

    needed = rb.needed_channels()
    print(f"\nneeded_channels() = {needed}")
    f, n = rb.build_field()
    print(f"build_field: n_terms = {n}, terms = "
          f"{[(t[2] if len(t) > 2 else None) for t in f.terms]}")
    E, cov, nt = f.aggregate()
    print(f"aggregate: E_mean 的取值集合 = {sorted(set(np.round(E, 3).tolist()))[:8]}")
    sel, _ = rb.choose_scan_point()
    print(f"choose_scan_point -> {sel['kind']} {tuple(round(v) for v in sel['xy'])} "
          f"E={sel['E_mean_m']:.1f} score={sel['score']:.4f} dist={sel['dist_m']:.0f}")
    chans = rb.channels_to_measure(pos=sel["xy"], subset=needed)
    print(f"该点上的 channels_to_measure = {chans}")
    print(f"  （needed 里的频道在该点被 nosignal_gap={cfg.nosignal_gap_m} 过滤掉的数量 "
          f"= {len(needed) - len(chans)}）")


if __name__ == "__main__":
    main()
