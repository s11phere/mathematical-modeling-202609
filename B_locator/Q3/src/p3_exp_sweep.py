"""对比"期望场贪心"（现状）与"覆盖扫圈"（新策略）。

场景
----
A. 第 2 局在线记录的真源（14 个，全部清完过）—— 直接检验"能不能更快清完"
B. 第 1 局在线记录的真源（10 个，含 3 个 r>1600 m 外圈源）
C. 外圈环带 12 源（对外圈最不利的几何）
D. 常规随机（seed 20260913+100i）
E. 独立随机（seed 777000+37i）—— 防止过拟合到某一批种子

用法：
    python src/p3_exp_sweep.py [--cases 30]
"""
from __future__ import annotations

import argparse
import math
import os
import statistics as st
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from p3_arena import MockArena, MockSource  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402
from p3_sweep import SweepConfig, SweepRobot, coverage_report  # noqa: E402

# 两局在线演练反算出的真源（见 review/live-practice-20260911.md）
LIVE2 = [(1, 693, -1157), (2, 722, 1401), (4, 288, 1723), (6, 622, 86),
         (8, 1066, 1008), (10, 1060, -550), (11, -386, 628), (14, 1378, 265),
         (15, 56, 734), (16, -722, -719), (17, 279, 945), (18, 1746, -247),
         (19, -509, 1384), (20, 498, 769)]
LIVE1 = [(2, 937, -782), (5, 363, 418), (6, -939, -1491), (9, 1652, -112),
         (10, 1606, -590), (11, -591, -82), (13, 18, -197), (14, 470, -1292),
         (18, 1024, 1242), (20, -316, 241)]


def arena_from(sources, r_recv=1400.0, seed=0, budget=360000.0):
    return MockArena(seed=seed, budget_s=budget,
                     sources=[MockSource(c, x, y, r_recv) for (c, x, y) in sources])


def outer_annulus(seed=0, n=12, r_lo=1300.0, r_hi=1800.0, budget=360000.0):
    rng = np.random.default_rng(seed)
    chans = rng.choice(np.arange(1, 21), size=n, replace=False)
    out = []
    for ch in chans:
        r = math.sqrt(rng.uniform(r_lo ** 2, r_hi ** 2))
        a = rng.uniform(0, 2 * math.pi)
        out.append(MockSource(int(ch), r * math.cos(a), r * math.sin(a),
                              float(rng.uniform(1000.0, 1500.0))))
    return MockArena(seed=seed, sources=out, budget_s=budget)


POLICIES = {
    "期望场贪心(现状)": (P3Robot, P3Config()),
    "覆盖扫圈(新)": (SweepRobot, SweepConfig()),
}


def run_one(cls, cfg, arena, base, tag=""):
    t0 = time.time()
    rb = cls(arena, cfg, base=base, log=None)
    rep = rb.run()
    rep["_wall"] = time.time() - t0
    rep["_policy"] = tag
    if isinstance(rb, SweepRobot):
        cov, mdist = rb.coverage_now()
        rep["coverage"] = cov
        rep["max_uncov_m"] = mdist
        rep["scanned_all"] = bool(mdist <= rb.cfg.cover_radius_m)
    return rep


def table(title, rows, cases):
    print(f"\n########## {title}（{cases} 局）##########")
    hdr = (f"{'策略':<18}{'清除率':>8}{'平均清除':>9}{'平均定位清除时间':>18}"
           f"{'虚拟时间':>10}{'检测':>7}{'行程/m':>9}{'空转占比':>9}{'实跑/s':>8}")
    print(hdr)
    print("-" * len(hdr))
    for name, reps in rows:
        cl = sum(r["cleared"] for r in reps)
        tot = sum(r["n_sources"] for r in reps)
        tm = [r["avg_clear_time_s"] for r in reps if r["avg_clear_time_s"]]
        vt = st.mean(r["virtual_time_s"] for r in reps)
        # "空转占比" = (总虚拟时间 - 最后一个源被清除的时刻) / 总虚拟时间
        idle = []
        for r in reps:
            last = (r["avg_clear_time_s"] or 0) * r["cleared"]
            idle.append((r["virtual_time_s"] - last) / max(r["virtual_time_s"], 1e-9))
        print(f"{name:<18}{cl/tot:>8.3f}{st.mean(r['cleared'] for r in reps):>9.2f}"
              f"{(st.mean(tm) if tm else 0):>18.1f}{vt:>10.0f}"
              f"{st.mean(r['n_measure'] for r in reps):>7.0f}"
              f"{st.mean(r.get('travel_m', 0) or r['mock_stats'].get('travel_m', 0) for r in reps):>9.0f}"
              f"{st.mean(idle):>9.1%}{st.mean(r['_wall'] for r in reps):>8.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=30)
    args = ap.parse_args()
    base = load_base()
    print(f"基准图：{'家族' if base is not None and hasattr(base, 'select') else base}")

    for title, mk in (("场景 A：第 2 局在线真源（14 源，全部清完过）",
                       lambda: arena_from(LIVE2, seed=11)),
                      ("场景 B：第 1 局在线真源（10 源，3 个 r>1600）",
                       lambda: arena_from(LIVE1, seed=12))):
        rows = []
        for name, (cls, cfg) in POLICIES.items():
            rows.append((name, [run_one(cls, cfg, mk(), base, name)]))
        table(title, rows, 1)

    rows = []
    for name, (cls, cfg) in POLICIES.items():
        rows.append((name, [run_one(cls, cfg, outer_annulus(seed=100 + s), base, name)
                            for s in range(3)]))
    table("场景 C：12 源全在外圈 r∈[1300,1800]（最坏几何）", rows, 3)

    for title, seeds in (("场景 D：常规随机 seed 20260913+100i",
                          [20260913 + 100 * i for i in range(args.cases)]),
                         ("场景 E：独立随机 seed 777000+37i",
                          [777000 + 37 * i for i in range(args.cases)])):
        rows = []
        for name, (cls, cfg) in POLICIES.items():
            rows.append((name, [run_one(cls, cfg, MockArena(seed=s), base, name)
                                for s in seeds]))
        table(title, rows, len(seeds))

    print("\n--- 扫圈的完备性口径（原点 + 目标圆圈）---")
    for rings in ((1400.0, 8), (1300.0, 8), (1500.0, 8), (1600.0, 10)):
        from p3_sweep import lattice_candidates
        cand = lattice_candidates((rings,))
        m, u, c = coverage_report([(0.0, 0.0)] + cand, r_inner=0.0)
        mi, ui, ci = coverage_report(cand, r_inner=1000.0)
        print(f"  单圈 r={rings[0]:.0f} n={rings[1]:.0f}: 全域最大未覆盖 {m:6.0f} m；"
              f"环带 r>1000 最大未覆盖 {mi:6.0f} m")


if __name__ == "__main__":
    main()
