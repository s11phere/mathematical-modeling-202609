"""问题 2 的精度公式：推导校验 + 最优第二检测点。

线性化（delta method）：设 e1,e2 = 检测点处的示向度误差（标准差异独立），
约束为 n_i^T (X - S_i) = 0，n_i = (-sin t_i, cos t_i)。
转动 t_i 角度 e_i 后一阶项为 (dn_i/dt)^T (X-S_i) e_i = -u_i^T (d_i u_i) e_i = -d_i e_i，
其中 u_i 是 S_i->X 的单位向量、d_i = |S_i X|。于是
      delta X = -N^{-1} D e,   N = [n_1^T; n_2^T],  D = diag(d_1,d_2)
      tr Cov  = sigma^2 (d_1^2 + d_2^2) / sin^2(theta_2 - theta_1)
=>    RMS = sigma_theta * sqrt(d_1^2 + d_2^2) / |sin(theta2 - theta1)|          (A)
其中 theta2-theta1 就是两条示向度读数之差。
本脚本用 (1) 有限差分 Jacobian  (2) 蒙特卡洛 两种方式校验 (A)，
并与常见的错误公式 sigma*d2/|sin phi| (phi = S1 处视视角) 对比。
"""
import math, sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# region_from_bearings 的规范实现已并入 Q1（B_locator/Q1/p1_intersection.py），
# 原先依赖的 review/p1_fixed.py 已移除；这里改为直接引用 Q1 的实现。
_Q1_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "..", "Q1"))
if os.path.isdir(_Q1_DIR) and _Q1_DIR not in sys.path:
    sys.path.insert(0, _Q1_DIR)
from p1_intersection import region_from_bearings

S1 = np.array([0.0, 0.0])
G = np.array([800.0, 0.0])
ERR = 1.0
SIG = ERR / math.sqrt(3.0) * math.pi / 180.0     # uniform[-1,1] 的标准差(rad)


def bearing(p, q):
    return math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 360.0


def ray_intersection(apex_a, tha_deg, apex_b, thb_deg):
    ta, tb = math.radians(tha_deg), math.radians(thb_deg)
    A = np.array([[math.sin(ta), -math.cos(ta)], [math.sin(tb), -math.cos(tb)]])
    rhs = np.array([math.sin(ta) * apex_a[0] - math.cos(ta) * apex_a[1],
                    math.sin(tb) * apex_b[0] - math.cos(tb) * apex_b[1]])
    if abs(np.linalg.det(A)) < 1e-14:
        return None
    return np.linalg.solve(A, rhs)


def check(b, phi):
    pa = math.radians(phi)
    S2 = np.array([b * math.cos(pa), b * math.sin(pa)])
    th1, th2 = bearing(S1, G), bearing(S2, G)
    d1, d2 = float(np.linalg.norm(G - S1)), float(np.linalg.norm(G - S2))
    delta = th2 - th1
    # (1) finite-difference Jacobian of the ray-intersection wrt (e1,e2)
    h = 1e-6
    X0 = ray_intersection(S1, th1, S2, th2)
    J = np.zeros((2, 2))
    for k in range(2):
        ep = [0.0, 0.0]
        ep[k] = h
        Xp = ray_intersection(S1, th1 + ep[0], S2, th2 + ep[1])
        em = [0.0, 0.0]
        em[k] = -h
        Xm = ray_intersection(S1, th1 + em[0], S2, th2 + em[1])
        J[:, k] = (Xp - Xm) / (2 * h)
    rms_fd = math.sqrt(SIG * SIG * float(np.trace(J @ J.T))) / math.pi * 180.0 \
        * (math.pi / 180.0)   # careful below
    # J is dX/d(e in rad); sigma in rad -> RMS in metres:
    rms_fd = math.sqrt(SIG * SIG * float(np.trace(J @ J.T)))
    # (2) closed form (A)
    formA = SIG * math.sqrt(d1 * d1 + d2 * d2) / abs(math.sin(math.radians(delta)))
    # (3) the naive formula sigma*d2/|sin(phi_look)|
    formB = SIG * d2 / abs(math.sin(pa))
    # (4) Monte Carlo
    rng = np.random.default_rng(7)
    errs = []
    for _ in range(20000):
        e1 = rng.uniform(-ERR, ERR)
        e2 = rng.uniform(-ERR, ERR)
        X = ray_intersection(S1, th1 + e1, S2, th2 + e2)
        if X is not None:
            errs.append(float(np.linalg.norm(X - G)))
    rms_mc = float(np.sqrt(np.mean(np.square(errs))))
    return d1, d2, delta, rms_fd, formA, formB, rms_mc


def main():
    print("=== 精度公式校验 (S1=(0,0), G=(800,0)) ===")
    print("   b  phi   d2    th2-th1   有限差分RMS  公式A(d1^2+d2^2/sin^2dth)  "
          "旧公式(sig*d2/sin phi)  蒙特卡洛RMS")
    for b, phi in [(300, 30), (500, 60), (800, 90), (1000, 120), (1200, 150), (600, 20)]:
        d1, d2, delta, fd, A, B, mc = check(b, phi)
        print("  %4d %4d %6.0f %8.2f  %12.2f  %20.2f  %18.2f  %12.2f"
              % (b, phi, d2, ((delta + 180) % 360) - 180, fd, A, B, mc))

    print("\n=== 用公式(A)做最优设计：固定基线 b，扫描视视角 phi ===")
    print("  目标：最小化最坏情况 RMS = sigma*sqrt(d1^2+d2^2)/|sin(theta2-theta1)|")
    print("        d1 未知，取区间 [300,1500] 内最坏（这里取 d1 使指标最大者）")
    print("   b   phi*   max_d1   worst_RMS(m)   (对照：phi* 处的 d2)")
    for b in (200, 400, 600, 800, 1000, 1200):
        best = None
        for phi in np.arange(2, 179, 1.0):
            pa = math.radians(phi)
            S2 = np.array([b * math.cos(pa), b * math.sin(pa)])
            worst = 0.0
            wd1 = None
            for d1 in np.linspace(300, 1500, 25):
                Gt = np.array([d1, 0.0])
                th1, th2 = bearing(S1, Gt), bearing(S2, Gt)
                d2 = float(np.linalg.norm(Gt - S2))
                dth = math.radians(th2 - th1)
                if abs(math.sin(dth)) < 1e-6:
                    worst = math.inf
                    wd1 = d1
                    break
                r = SIG * math.sqrt(d1 * d1 + d2 * d2) / abs(math.sin(dth))
                if r > worst:
                    worst, wd1 = r, d1
            if best is None or worst < best[1]:
                best = (phi, worst, wd1)
        phi, worst, wd1 = best
        print("  %4d  %5.0f  %6.0f  %12.2f" % (b, phi, wd1, worst))

    print("\n=== 该设计规则与“交会角 gamma≈90 度”的关系 ===")
    print("   b   最优 phi*   b*cos(phi*)  =>  源到 S1 的估计距离 t_hat=b*cos(phi*)")
    for b in (200, 400, 600, 800, 1000, 1200):
        best = None
        for phi in np.arange(2, 179, 1.0):
            pa = math.radians(phi)
            S2 = np.array([b * math.cos(pa), b * math.sin(pa)])
            worst = 0.0
            for d1 in np.linspace(300, 1500, 25):
                Gt = np.array([d1, 0.0])
                th1, th2 = bearing(S1, Gt), bearing(S2, Gt)
                d2 = float(np.linalg.norm(Gt - S2))
                dth = math.radians(th2 - th1)
                if abs(math.sin(dth)) < 1e-6:
                    worst = math.inf
                    break
                r = SIG * math.sqrt(d1 * d1 + d2 * d2) / abs(math.sin(dth))
                worst = max(worst, r)
            if best is None or worst < best[1]:
                best = (phi, worst)
        phi = best[0]
        print("  %4d   %6.0f     %8.0f" % (b, phi, b * math.cos(math.radians(phi))))

    print("\n=== 有界性/良态性约束的量化 ===")
    print("  两示向度读数之差 dth 与最坏 RMS 的关系（d1=800, b=600）：")
    b = 600.0
    for phi in (0, 1, 2, 3, 5, 10, 20, 40, 60, 90, 130):
        pa = math.radians(phi)
        S2 = np.array([b * math.cos(pa), b * math.sin(pa)])
        th1, th2 = bearing(S1, G), bearing(S2, G)
        dth = ((th2 - th1 + 180) % 360) - 180
        d2 = float(np.linalg.norm(G - S2))
        if abs(math.sin(math.radians(dth))) < 1e-9:
            r = math.inf
        else:
            r = SIG * math.sqrt(800 ** 2 + d2 ** 2) / abs(math.sin(math.radians(dth)))
        print("   phi=%4d  |dth|=%7.2f deg  d2=%7.1f  RMS=%s"
              % (phi, abs(dth), d2, "inf" if not math.isfinite(r) else "%.2f m" % r))


if __name__ == "__main__":
    main()
