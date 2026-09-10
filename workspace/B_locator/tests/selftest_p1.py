"""B 题数据与算法自检：生成算例 → 求解 → 断言不变量。

不变量：
  I1 真值必须落在定位区域内（否则生成器或求解器有错）
  I2 定位区域为凸多边形（叉积同号）
  I3 直径 ≥ 任一顶点对距离，且等于其中最大者
  I4 直径圆覆盖判定与"最大顶点距 ≤ D/2"一致
  I5 全部算例的直径量级合理（0 < D < 200 m）
"""
import json, math, os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, os.path.join(ROOT, "src"))

from p1_intersection import run_case_csv, analyse, _cross2  # noqa: E402


def main():
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "b_testdata.py"),
                    "--out", DATA, "--seed", "20260901"], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, os.path.join(ROOT, "src", "p1_intersection.py"), DATA],
                   check=True, stdout=subprocess.DEVNULL)

    fails = []
    n = 0
    for fn in sorted(os.listdir(DATA)):
        if not (fn.startswith("p1_case") and fn.endswith(".csv")):
            continue
        n += 1
        res = run_case_csv(os.path.join(DATA, fn),
                           os.path.join(DATA, fn.replace(".csv", ".truth.json")))
        if res["status"] != "bounded":
            fails.append((fn, "I2 非有界: " + res["status"])); continue
        if not res.get("truth_inside_region"):
            fails.append((fn, "I1 真值不在定位区域内"))
        P = np.array(res["vertices"])
        cr = [_cross2(P[(i + 1) % len(P)] - P[i], P[(i + 2) % len(P)] - P[(i + 1) % len(P)])
              for i in range(len(P))]
        if not (all(c > -1e-9 for c in cr) or all(c < 1e-9 for c in cr)):
            fails.append((fn, "I2 顶点非凸"))
        D = res["diameter_m"]          # 已按 4 位小数落盘
        dd = [float(np.linalg.norm(P[i] - P[j]))
              for i in range(len(P)) for j in range(i + 1, len(P))]
        if abs(D - max(dd)) > 1e-3:
            fails.append((fn, "I3 直径与暴力枚举不一致 D=%.4f brute=%.4f" % (D, max(dd))))
        # 内部全精度直径也必须等于暴力枚举值
        from p1_intersection import diameter as _diam
        Dfull, _ = _diam(P)
        if abs(Dfull - max(dd)) > 1e-9:
            fails.append((fn, "I3b 内部直径与暴力枚举不一致"))
        if res["diameter_circle_covers"] != (res["max_vertex_dist_m"] <= D / 2 + 1e-9):
            fails.append((fn, "I4 覆盖判定不一致"))
        if not (0 < D < 200):
            fails.append((fn, "I5 直径不合理 %.3f" % D))

    print("检查算例数: %d" % n)
    if fails:
        for f, why in fails:
            print("  FAIL %s : %s" % (f, why))
        return 1
    print("全部不变量通过 (I1–I5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
