"""校验 live 局的两件事：
1) 用问题1的交会区域（±1°楔的交集）反算每个频道真源所在的可行域，
   检查"成功清除点"是否落在该域附近（<=20 m）—— 若是，说明协议与几何都自洽；
2) 用交会区域给出每个频道的源位估计（比最小二乘更稳健），
   并据此判断"未测到方向的频道"是否真的存在（源总数 = 清除数 还是更多）。
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p1_intersection import analyse  # noqa: E402


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
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


def main():
    d = sys.argv[1]
    order = pair(load_jsonl(os.path.join(d, "protocol.jsonl")))
    bearings = collections.defaultdict(list)
    clears = collections.defaultdict(list)
    for (p, pl, rp) in order:
        if p == "/measure" and rp.get("measure_result") == "direction":
            bearings[pl["channel"]].append((pl["position"]["x"], pl["position"]["y"],
                                            rp["svd_deg"]))
        elif p == "/clear":
            clears[pl["channel"]].append((pl["position"]["x"], pl["position"]["y"],
                                          rp.get("clear_result")))

    print("=== 交会区域（±1°楔交集） vs 成功清除点 ===")
    print(f"{'ch':>3} {'#方位':>5} {'区域状态':>10} {'直径(m)':>9} {'最小包围圆r*(m)':>15} "
          f"{'区域中心':>20} {'清除点':>20} {'清除点到区域距离(m)':>18}")
    def dist_point_poly(p, P):
        P = np.asarray(P, float)
        p = np.asarray(p, float)
        n = len(P)
        inside = False
        for i in range(n):
            a, b = P[i], P[(i + 1) % n]
            if (a[1] > p[1]) != (b[1] > p[1]):
                xx = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if xx > p[0]:
                    inside = not inside
        if inside:
            return 0.0
        best = 1e18
        for i in range(n):
            a, b = P[i], P[(i + 1) % n]
            ab = b - a
            L2 = float(ab @ ab)
            t = 0.0 if L2 < 1e-12 else float(np.clip((p - a) @ ab / L2, 0, 1))
            best = min(best, float(np.linalg.norm(p - (a + t * ab))))
        return best

    ok_all = True
    for ch in sorted(bearings):
        pts = [(x, y) for (x, y, a) in bearings[ch]]
        svds = [a for (x, y, a) in bearings[ch]]
        reg = analyse(pts, svds, 1.0)
        st = reg.get("status")
        D = reg.get("diameter_m")
        rstar = reg.get("min_enclosing_radius_m")
        cen = reg.get("min_enclosing_center")
        poly = reg.get("vertices")
        cl = [(x, y, r) for (x, y, r) in clears.get(ch, []) if r == "success"]
        if cl and poly:
            x, y, _ = cl[0]
            dd = dist_point_poly((x, y), poly)
            ok = dd <= 20.0 + 1e-6
            ok_all = ok_all and ok
        else:
            dd, ok = None, None
        print(f"{ch:>3} {len(pts):>5} {str(st):>10} "
              f"{(f'{D:.1f}' if D is not None else '-'):>9} "
              f"{(f'{rstar:.1f}' if rstar is not None else '-'):>15} "
              f"{(f'({cen[0]:.0f},{cen[1]:.0f})' if cen else '-'):>20} "
              f"{(f'({cl[0][0]:.0f},{cl[0][1]:.0f})' if cl else '-'):>20} "
              f"{(f'{dd:.2f}' if dd is not None else '-'):>18}"
              f"{'' if ok in (None, True) else '   <-- 清除点在区域外!'}")
    print(f"\n所有成功清除点都落在交会区域内（允许 20 m 清除半径）：{ok_all}")

    print("\n=== 未测到任何方向的频道（若有，说明这些频道仍有未清除源）===")
    never = [ch for ch in range(1, 21) if ch not in bearings]
    print(f"  {never}")


if __name__ == "__main__":
    main()
