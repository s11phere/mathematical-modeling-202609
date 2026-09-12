# -*- coding: utf-8 -*-
"""B 题问题一自检：不变量 I1–I8，并验证交付文件可由代码逐字节复现。

运行（在扁平的 Q1/ 目录下）：python p1_selftest.py
全部通过返回 0，任一失败返回 1。

    I1 每组算例的真值都落在定位区域内
    I2 定位区域为逆时针凸多边形
    I3 直径与暴力枚举、旋转卡壳三者一致（<= 1e-9 m）
    I4 analyse() 的覆盖判定与全精度判据一致
    I5 直径量级合理（0 < D < 200 m）
    I6 两套独立区域实现（顶点枚举 / 半平面裁剪）顶点数相同、逐点偏差 < 1e-6 m
    I7 算例文件可由固定种子逐字节复现
    I8 p1_summary.json 中的四组随机扫描统计（理想构型 / 实际构型）可由固定种子复现
"""
from __future__ import annotations
import csv
import json
import os
import tempfile

import numpy as np

import p1_intersection as P
import p1_experiments as E

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, ok, detail=""):
    print("[%s] %s%s" % ("OK  " if ok else "FAIL", name, ("  — " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def load_case(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    return ([(float(r["x_m"]), float(r["y_m"])) for r in rows],
            [float(r["svd_deg"]) for r in rows])


CASES = os.path.join(HERE, "cases")          # 算例统一放在 cases/ 子目录


def case_files():
    return sorted(f for f in os.listdir(CASES)
                  if f.startswith("p1_case") and f.endswith(".csv"))


def main():
    files = case_files()
    check("算例文件非空", len(files) > 0, "共 %d 组" % len(files))

    for fn in files:
        name = fn[:-4]
        csv_path = os.path.join(CASES, fn)
        truth_path = os.path.join(CASES, name + ".truth.json")
        pts, svds = load_case(csv_path)
        res = P.run_case_csv(csv_path, truth_path)
        full = E.solve_full(pts, svds)
        V, st = P.region_by_vertices(pts, svds)

        check("%s I1 真值在区域内" % name, bool(res.get("truth_inside_region")) is True)
        check("%s 有界" % name, res["status"] == "bounded", res["status"])

        cr = [P._cross2(V[(i + 1) % len(V)] - V[i], V[(i + 2) % len(V)] - V[(i + 1) % len(V)])
              for i in range(len(V))]
        check("%s I2 顶点为逆时针凸序" % name, all(c > 0 for c in cr),
              "叉积最小 %.3e" % min(cr))

        D, _ = P.diameter(V)
        Db, _ = P._diameter_brute(V)
        Dc, _ = P.rotating_calipers(V)
        check("%s I3 直径三算法一致" % name,
              abs(D - Db) <= 1e-9 and abs(D - Dc) <= 1e-9,
              "直径=%.9f 暴力=%.9f 卡壳=%.9f" % (D, Db, Dc))

        check("%s I4 覆盖判定一致" % name,
              bool(res["diameter_circle_covers"]) == bool(full["covers"]),
              "analyse=%s 全精度=%s" % (res["diameter_circle_covers"], full["covers"]))

        check("%s I5 直径量级合理" % name, 0.0 < D < 200.0, "D=%.4f m" % D)

        Pc, stc = P.region_by_clipping(pts, svds)
        Hc = P.convex_hull(Pc) if len(Pc) >= 3 else Pc
        dev = (max(min(float(np.linalg.norm(a - b)) for b in Hc) for a in V)
               if len(Hc) >= 3 else float("inf"))
        check("%s I6 两套区域实现一致" % name,
              stc == "polygon" and len(Hc) == len(V) and dev < 1e-6,
              "顶点数 %d/%d，最大偏差 %.3e m" % (len(V), len(Hc), dev))

    # I7 算例可逐字节复现
    with tempfile.TemporaryDirectory() as tmp:
        E.gen_cases(tmp, E.DEFAULT_SEED, len(files))   # 生成到临时目录（无 cases/ 子目录）
        same = []
        for fn in files:
            a = open(os.path.join(tmp, fn), "rb").read()
            b = open(os.path.join(CASES, fn), "rb").read()
            same.append(a == b)
            tf = fn[:-4] + ".truth.json"
            same.append(open(os.path.join(tmp, tf), "rb").read()
                        == open(os.path.join(CASES, tf), "rb").read())
        check("I7 算例逐字节可复现", all(same),
              "%d/%d 个文件一致" % (sum(same), len(same)))

    # I8 运行结果（两组扫描 + 逐例比值/覆盖）可复现
    summary = json.load(open(os.path.join(HERE, "p1_summary.json"), encoding="utf-8"))
    s1 = E.sweep_two_point()
    s2 = E.sweep_well_conditioned()
    old1, old2 = summary["sweeps"]["two_point"], summary["sweeps"]["well_conditioned"]
    check("I8a 两测点扫描复现",
          (s1["n_bounded"], s1["n_fail"]) == (old1["n_bounded"], old1["n_fail"])
          and abs(s1["worst_ratio"] - old1["worst_ratio"]) <= 1e-12,
          "bounded=%d fail=%d worst=%.6f" % (s1["n_bounded"], s1["n_fail"], s1["worst_ratio"]))
    check("I8b 3~6 测点扫描复现",
          (s2["n_bounded"], s2["n_fail"]) == (old2["n_bounded"], old2["n_fail"])
          and abs(s2["worst_ratio"] - old2["worst_ratio"]) <= 1e-12,
          "bounded=%d fail=%d worst=%.6f" % (s2["n_bounded"], s2["n_fail"], s2["worst_ratio"]))
    s1e = E.sweep_two_point(with_error=True)
    s2e = E.sweep_well_conditioned(with_error=True)
    old1e, old2e = summary["sweeps"]["two_point_err"], summary["sweeps"]["well_conditioned_err"]
    check("I8d 两测点扫描（含 ±1° 测向误差）复现",
          (s1e["n_bounded"], s1e["n_fail"]) == (old1e["n_bounded"], old1e["n_fail"])
          and abs(s1e["worst_ratio"] - old1e["worst_ratio"]) <= 1e-12,
          "bounded=%d fail=%d worst=%.6f" % (s1e["n_bounded"], s1e["n_fail"],
                                             s1e["worst_ratio"]))
    check("I8e 3~6 测点扫描（含 ±1° 测向误差）复现",
          (s2e["n_bounded"], s2e["n_fail"]) == (old2e["n_bounded"], old2e["n_fail"])
          and abs(s2e["worst_ratio"] - old2e["worst_ratio"]) <= 1e-12,
          "bounded=%d fail=%d worst=%.6f" % (s2e["n_bounded"], s2e["n_fail"],
                                             s2e["worst_ratio"]))
    bad = []
    for rec in summary["per_case"]:
        csv_path = os.path.join(CASES, rec["case"])
        pts, svds = load_case(csv_path)
        full = E.solve_full(pts, svds)
        if abs(round(full["ratio"], 6) - rec["ratio"]) > 1e-12 or full["covers"] != rec["coverage"]:
            bad.append(rec["label"])
    check("I8c 汇总表的逐例比值/覆盖可复现", not bad, "不一致：" + (",".join(bad) or "无"))

    print()
    if FAILS:
        print("自检失败 %d 项：%s" % (len(FAILS), ", ".join(FAILS)))
        return 1
    print("自检全部通过（I1–I8）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
