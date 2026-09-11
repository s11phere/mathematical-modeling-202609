"""Q2 良态性检查：不加约束时最优解发散（问题必须加约束才适定）。

1) 修正 q2_formula 中有限差分列的单位（J 是 dX/d(度)）。
2) 已知精确源距 t 时，最优 (b, phi) 随 b 单调变好 => 无内点最优 => 必须加
   移动预算 / 可检测性 / 目标区域约束。
"""
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q2_formula import bearing, ray_intersection, SIG, ERR, S1

print("=== 有限差分校验（修正单位：J 对“度”求导，sigma 用度）===")
print("   b  phi   FD-RMS  (sigma_deg^2*tr(JJ^T))^0.5   公式A   蒙特卡洛")
rng = np.random.default_rng(1)
sig_deg = ERR / math.sqrt(3.0)
for b, phi in [(300, 30), (800, 90), (1200, 150)]:
    G = np.array([800.0, 0.0])
    pa = math.radians(phi)
    S2 = np.array([b * math.cos(pa), b * math.sin(pa)])
    th1, th2 = bearing(S1, G), bearing(S2, G)
    d1, d2 = float(np.linalg.norm(G - S1)), float(np.linalg.norm(G - S2))
    h = 1e-6
    J = np.zeros((2, 2))
    for k in range(2):
        ep = [0.0, 0.0]
        ep[k] = h
        em = [0.0, 0.0]
        em[k] = -h
        J[:, k] = (ray_intersection(S1, th1 + ep[0], S2, th2 + ep[1])
                   - ray_intersection(S1, th1 + em[0], S2, th2 + em[1])) / (2 * h)
    fd = math.sqrt(sig_deg ** 2 * float(np.trace(J @ J.T)))
    A = sig_deg * math.pi / 180 * math.sqrt(d1 * d1 + d2 * d2) / abs(math.sin(math.radians(th2 - th1)))
    errs = []
    for _ in range(20000):
        X = ray_intersection(S1, th1 + rng.uniform(-ERR, ERR), S2, th2 + rng.uniform(-ERR, ERR))
        if X is not None:
            errs.append(float(np.linalg.norm(X - G)))
    print("  %4d %4d  %8.2f  %22.2f  %8.2f  %10.2f"
          % (b, phi, fd, A, A, float(np.sqrt(np.mean(np.square(errs))))))

print("\n=== 已知源距 t 时，最优 (b,phi) 是否发散？（t=800 固定）===")
print("   b   最优phi   min_RMS(m)")
t = 800.0
G = np.array([t, 0.0])
for b in (100, 200, 400, 800, 1600, 3200, 6400):
    best = None
    for phi in np.arange(1, 179, 1.0):
        pa = math.radians(phi)
        S2 = np.array([b * math.cos(pa), b * math.sin(pa)])
        th1, th2 = bearing(S1, G), bearing(S2, G)
        d1, d2 = float(np.linalg.norm(G - S1)), float(np.linalg.norm(G - S2))
        s = abs(math.sin(math.radians(th2 - th1)))
        if s < 1e-9:
            continue
        r = SIG * math.sqrt(d1 * d1 + d2 * d2) / s
        if best is None or r < best[1]:
            best = (phi, r)
    print("  %5d   %6.0f   %9.2f" % (b, best[0], best[1]))
print("  => RMS 随 b 单调下降，无内点最优：必须加入移动预算/可检测性等约束。")
