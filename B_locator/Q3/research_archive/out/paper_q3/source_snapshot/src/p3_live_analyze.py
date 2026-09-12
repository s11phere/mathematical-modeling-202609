"""分析一次 live 运行（protocol.jsonl + robot_events.jsonl + summary.json）与离线演练的差异。

用法：
    python src/p3_live_analyze.py out/p3/live_20260911_151432
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys

NEAR_R = 5.0


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else None
    if not d:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "p3")
        cands = sorted([p for p in os.listdir(base) if p.startswith("live_")])
        d = os.path.join(base, cands[-1])
    print(f"=== 分析目录 {d} ===")
    prot = load_jsonl(os.path.join(d, "protocol.jsonl"))
    ev = load_jsonl(os.path.join(d, "robot_events.jsonl"))
    summ = json.load(open(os.path.join(d, "summary.json"), encoding="utf-8"))

    # 请求（req）带 payload；响应（resp）不带 request_id，
    # 按"同一 path 的最近一条尚未配对的请求"配对（本程序严格串行发送）。
    order = []
    pending = collections.defaultdict(list)
    resp_by_rid = {}
    for r in prot:
        k = r.get("kind")
        if k == "req":
            order.append(r)
            rid = r["payload"]["request_id"]
            pending[r["path"]].append(rid)
            resp_by_rid.setdefault(rid, None)
        elif k == "resp":
            path = r.get("path")
            if path in pending and pending[path]:
                rid = pending[path].pop(0)
                resp_by_rid[rid] = r["resp"]

    # 每条频道的检测历史
    meas = collections.defaultdict(list)   # ch -> [(rid,x,y,vtime,result,svd)]
    clears = []
    n_retry = 0
    seen_rid = set()
    for r in order:
        rid = r["payload"]["request_id"]
        if rid in seen_rid:
            n_retry += 1
        seen_rid.add(rid)
        p = r["path"]
        pl = r["payload"]
        rp = resp_by_rid.get(rid)
        if rp is None:
            continue
        if p == "/measure":
            ch = pl["channel"]
            x, y = pl["position"]["x"], pl["position"]["y"]
            meas[ch].append((rid, x, y, rp.get("virtual_time_s"),
                             rp.get("measure_result"), rp.get("svd_deg")))
        elif p == "/clear":
            ch = pl["channel"]
            x, y = pl["position"]["x"], pl["position"]["y"]
            clears.append((rid, ch, x, y, rp.get("virtual_time_s"),
                           rp.get("clear_result")))

    print(f"\n--- 协议层 ---")
    print(f"请求总数 {len(order)}（其中重试复用同一 request_id {n_retry} 次）")
    print(f"/measure {(sum(len(v) for v in meas.values()))} 次，/clear {len(clears)} 次")
    res_cnt = collections.Counter(m[4] for v in meas.values() for m in v)
    print(f"检测结果分布：{dict(res_cnt)}")
    cl_cnt = collections.Counter(c[5] for c in clears)
    print(f"清除结果分布：{dict(cl_cnt)}")
    tmax = max([m[3] for v in meas.values() for m in v if m[3] is not None] + [0])
    print(f"最后一条 /measure 的虚拟时刻：{tmax:.1f} s")

    print(f"\n--- 逐频道台账（20 个频道全列） ---")
    hdr = f"{'ch':>3} {'#meas':>5} {'#dir':>4} {'#no':>4} {'#near':>5} {'#clrOK':>6} {'#clrF':>5} {'首次方向t':>9} {'最后测t':>8}"
    print(hdr)
    tot_dir = 0
    for ch in range(1, 21):
        ms = meas.get(ch, [])
        nd = sum(1 for m in ms if m[4] == "direction")
        nn = sum(1 for m in ms if m[4] == "no_signal")
        nr = sum(1 for m in ms if m[4] == "near")
        ok = sum(1 for c in clears if c[1] == ch and c[5] == "success")
        fa = sum(1 for c in clears if c[1] == ch and c[5] != "success")
        tdir = next((m[3] for m in ms if m[4] == "direction"), None)
        tlast = ms[-1][3] if ms else None
        tot_dir += nd
        print(f"{ch:>3} {len(ms):>5} {nd:>4} {nn:>4} {nr:>5} {ok:>6} {fa:>5} "
              f"{(f'{tdir:.1f}' if tdir is not None else '-'):>9} "
              f"{(f'{tlast:.1f}' if tlast is not None else '-'):>8}")
    print(f"方向读数合计 {tot_dir}")

    print(f"\n--- 有方向的频道的第二次读数几何（交会角） ---")
    for ch in range(1, 21):
        ms = [m for m in meas.get(ch, []) if m[4] == "direction"]
        if len(ms) < 2:
            continue
        # 前两条方位
        (_, x1, y1, t1, _, a1), (_, x2, y2, t2, _, a2) = ms[0], ms[1]
        base = math.hypot(x2 - x1, y2 - y1)
        dang = abs((a1 - a2 + 90) % 180 - 90)
        # 粗略交会距离：用两条射线的交点
        import numpy as np
        def inter(x1, y1, a1, x2, y2, a2):
            d1 = np.array([math.cos(math.radians(a1)), math.sin(math.radians(a1))])
            d2 = np.array([math.cos(math.radians(a2)), math.sin(math.radians(a2))])
            A = np.array([d1, -d2]).T
            if abs(np.linalg.det(A)) < 1e-12:
                return None
            t = np.linalg.solve(A, np.array([x2 - x1, y2 - y1]))
            return np.array([x1, y1]) + t[0] * d1
        P = inter(x1, y1, a1, x2, y2, a2)
        dist = None if P is None else float(np.hypot(P[0], P[1]))
        print(f"ch{ch:>2}: 基线 {base:7.1f} m  夹角 {dang:6.2f}°  "
              f"交会点距原点 {('%.0f' % dist) if dist else 'inf':>7}  "
              f"t1={t1:.0f}s t2={t2:.0f}s  Δt={t2-t1:.0f}s")

    print(f"\n--- 清除时间线 ---")
    for (rid, ch, x, y, t, r) in clears:
        print(f"  t={t:8.1f}s  ch{ch:>2}  ({x:8.1f},{y:8.1f})  {r}")

    print(f"\n--- summary ---")
    for k in ("cleared", "n_sources", "virtual_time_s", "avg_clear_time_s",
              "program_runtime_s", "remaining_budget_s", "n_measure", "n_bearings",
              "n_clear", "n_clear_fail", "n_scan_rounds", "n_replans",
              "n_midphase_targets", "n_rejected"):
        print(f"  {k:>22} = {summ.get(k)}")

    print(f"\n--- 决策轨迹（robot_events） ---")
    for e in ev:
        print(f"  t={e['t']:8.1f}s  {e['msg']}")


if __name__ == "__main__":
    main()
