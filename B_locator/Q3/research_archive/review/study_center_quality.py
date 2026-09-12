"""量化"估计的区域中心"的质量，以及排序对它的敏感度。

三个问题：
  ① 区域中心离**真源**多远？相对 r* 是什么量级？真源在不在最小包围圆内？
  ② 随着拿到更多方位，中心会漂移多少（滚动重估的价值）？
  ③ 如果**直接用真源位置**参与排序与逼近（其余逻辑完全不变），能多清几个？
     —— 这把"发现能力"和"中心估计误差"的贡献分开。
"""
from __future__ import annotations

import math
import os
import statistics as st
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _SRC)

import numpy as np  # noqa: E402

from p3_arena import MockArena, V_ROBOT  # noqa: E402
from p3_robot import P3Config, P3Robot, load_base  # noqa: E402


class TruthCenterRobot(P3Robot):
    """只改一处：把"区域中心"换成真源位置（其余策略逐字不变）。

    用于测出"中心估计误差"对清除率的影响上界。
    """

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._truth = {}
        for s in (self.arena.truth() or {}).get("sources", []):
            self._truth[int(s["channel"])] = (float(s["x_m"]), float(s["y_m"]))

    def bounded_region(self, rec):
        br = super().bounded_region(rec)
        if br is None:
            return None
        tc = self._truth.get(int(rec.channel))
        if tc is None:
            return br
        return {"center": tc, "radius": float(br["radius"]), "poly": br.get("poly"),
                "status": br["status"], "n_bearings": br["n_bearings"]}


def run_case(seed, base, oracle_center=False):
    arena = MockArena(seed=seed)
    cls = TruthCenterRobot if oracle_center else P3Robot
    rb = cls(arena, P3Config(), base=base, log=None)

    truth = {int(s["channel"]): (float(s["x_m"]), float(s["y_m"]))
             for s in (arena.truth() or {}).get("sources", [])}
    samples = []          # 每次 /measure 后的 (ch, n_bearings, center, radius)
    orig_measure = rb.measure

    def spy(x, y, ch):
        r = orig_measure(x, y, ch)
        rec = rb.recs[int(ch)]
        br = rb.bounded_region(rec)
        if br is not None and rec.n_bearings >= 2:
            c = br["center"]
            samples.append({"ch": int(ch), "n": rec.n_bearings,
                            "center": (float(c[0]), float(c[1])),
                            "radius": float(br["radius"])})
        return r

    rb.measure = spy
    rep = rb.run()
    rep["seed"] = seed
    rep["_samples"] = samples
    rep["_truth"] = truth
    return rep


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    seeds = [20260913 + 100 * i for i in range(n)]
    base = load_base()

    rows = [run_case(s, base, False) for s in seeds]

    # ---------- ① 中心 vs 真源 ----------
    err, rel, inside, radii = [], [], [], []
    for r in rows:
        for smp in r["_samples"]:
            t = r["_truth"].get(smp["ch"])
            if t is None:
                continue
            d = math.dist(smp["center"], t)
            err.append(d)
            radii.append(smp["radius"])
            if smp["radius"] > 1e-9:
                rel.append(d / smp["radius"])
            inside.append(d <= smp["radius"] + 1e-6)
    print(f"{n} 局，共 {len(err)} 个'已定位区域'样本（每次 /measure 后）\n")
    print("① 估计的区域中心 vs 真源位置")
    print(f"   中心到真源距离：均值 {st.mean(err):.1f} m，中位数 {st.median(err):.1f} m，"
          f"P90 {sorted(err)[int(0.9*len(err))]:.1f} m，最大 {max(err):.1f} m")
    print(f"   最小包围圆半径 r*：均值 {st.mean(radii):.1f} m，中位数 {st.median(radii):.1f} m")
    print(f"   距离 / r* 比值：中位数 {st.median(rel):.2f}，"
          f"P90 {sorted(rel)[int(0.9*len(rel))]:.2f}")
    print(f"   真源落在最小包围圆内的比例：{sum(inside)}/{len(inside)} = "
          f"{sum(inside)/len(inside)*100:.1f}%")
    print(f"   （注意：几何保证是'真源落在**多边形区域**内'，不是'落在最小包围圆内'）")

    # ---------- ② 中心漂移 ----------
    print("\n② 中心随方位数增加漂移多少（同一频道的相邻样本）")
    drift = {}
    for r in rows:
        by_ch = {}
        for smp in r["_samples"]:
            by_ch.setdefault(smp["ch"], []).append(smp)
        for ch, ss in by_ch.items():
            ss.sort(key=lambda s: s["n"])
            for a, b in zip(ss, ss[1:]):
                drift.setdefault((a["n"], b["n"]), []).append(
                    math.dist(a["center"], b["center"]))
    for k in sorted(drift):
        v = drift[k]
        print(f"   {k[0]} -> {k[1]} 条方位：{len(v):>4} 次，"
              f"漂移均值 {st.mean(v):>6.1f} m，最大 {max(v):>7.1f} m")

    # ---------- ③ 用真源位置排序的上界 ----------
    print("\n③ 只把'区域中心'换成真源位置（其余策略完全不变）")
    orc = [run_case(s, base, True) for s in seeds]
    b_cl = sum(r["cleared"] for r in rows)
    o_cl = sum(r["cleared"] for r in orc)
    n_src = sum(r["n_sources"] for r in rows)
    print(f"   baseline : 清除 {b_cl}/{n_src} = {b_cl/n_src:.4f}，"
          f"平均 {st.mean(r['cleared'] for r in rows):.3f} 个/局")
    print(f"   真中心   : 清除 {o_cl}/{n_src} = {o_cl/n_src:.4f}，"
          f"平均 {st.mean(r['cleared'] for r in orc):.3f} 个/局")
    dd = [o["cleared"] - b["cleared"] for o, b in zip(orc, rows)]
    w = sum(1 for x in dd if x > 0)
    l = sum(1 for x in dd if x < 0)
    print(f"   配对差：均值 {st.mean(dd):+.3f} 个/局，"
          f"胜/平/负 {w}/{len(dd)-w-l}/{l}，"
          f"标准误 {(st.stdev(dd)/math.sqrt(len(dd)) if len(dd)>1 else 0):.3f}")


if __name__ == "__main__":
    sys.exit(main())
