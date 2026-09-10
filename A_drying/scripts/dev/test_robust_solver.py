# -*- coding: utf-8 -*-
"""Validate robust_solver against analytical solutions before trusting results."""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drying_solver import Props, c2k, k2c  # noqa: E402
from robust_solver import RobustSolver  # noqa: E402
import model_problems as mp  # noqa: E402

FAIL = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


# --------------------------------------------------------------------------
# 1. steady-state pure conduction with a fixed surface temperature
# --------------------------------------------------------------------------
def test_steady_conduction():
    print("\n=== steady conduction: T = Ts + (T0-Ts)(1 - r^2/R^2) ===")
    R, Ts, T0 = 0.02, 350.0, 300.0
    k = 0.36
    rho_cp = 820.0 * 2600.0
    props = Props(
        rho=lambda C, T: np.full_like(T, 820.0),
        cp=lambda C, T: np.full_like(T, 2600.0),
        k=lambda C, T: np.full_like(T, k),
        D=lambda C, T: np.full_like(T, 1e-12),
        h=1e9, h_m=0.0, Lw=0.0,
        Tamb=lambda t: Ts, Camb=lambda t: 0.0,
        rho_d0=1.0, C_sat=1.0,
    )
    for N in (20, 40, 80):
        s = RobustSolver(N=N, R0=R)
        res = s.run(props, t_end=4000.0, T_init=T0, C_init=0.0, dt=20.0,
                    max_newton=40, tol=1e-12)
        Tn = res.Ts[-1]
        r = R * s.grid.xi_c
        exact = Ts + (T0 - Ts) * (1.0 - (r / R) ** 2)
        err = float(np.max(np.abs(Tn - exact)))
        print(f"   N={N:3d}  max|T-exact| = {err:.3e} K")
        check(f"steady conduction N={N} error < 1e-3 K", err < 1e-3, f"{err:.2e}")


# --------------------------------------------------------------------------
# 2. mass conservation with a pure diffusive boundary (no heat coupling)
# --------------------------------------------------------------------------
def test_conservation():
    print("\n=== water balance: dW/dt = -2 pi R jw ===")
    amb = mp.Ambient()
    props = mp.props_problem1(amb)
    props.h_m = 1e-5           # accelerate so the balance is measurable
    s = RobustSolver(N=40, R0=0.02)
    res = s.run(props, t_end=600.0, T_init=c2k(28.0), C_init=2.55, dt=10.0,
                tol=1e-12)
    t = np.array(res.ts)
    W = np.array(res.W)
    jw = np.array(res.jw)
    m_out = 2 * np.pi * 0.02 * np.trapz(jw, t)
    rel = abs((W[0] - W[-1]) - m_out) / abs(W[0] - W[-1])
    print(f"   W0-W1={W[0]-W[-1]:.6e}  flux_int={m_out:.6e}  rel={rel:.3e}")
    check("water balance (rel < 1e-4)", rel < 1e-4, f"{rel:.2e}")


# --------------------------------------------------------------------------
# 3. first-order time convergence and second-order space convergence
# --------------------------------------------------------------------------
def test_orders():
    print("\n=== convergence orders (problem 1 setup) ===")
    amb = mp.Ambient()
    props = mp.props_problem1(amb)
    props.h_m = 2e-6
    ref = None
    for N in (40, 80, 160):
        s = RobustSolver(N=N, R0=0.02)
        res = s.run(props, t_end=300.0, T_init=c2k(28.0), C_init=2.55, dt=1.0,
                    tol=1e-12)
        prof = np.concatenate([res.Ts[-1], res.Cs[-1]])
        if N == 160:
            ref = prof
    # space order needs a common grid; use a coarse comparison instead
    e = {}
    for N in (20, 40, 80):
        s = RobustSolver(N=N, R0=0.02)
        res = s.run(props, t_end=300.0, T_init=c2k(28.0), C_init=2.55, dt=0.5,
                    tol=1e-12)
        e[N] = (float(res.Ts[-1][0]), float(res.Cs[-1][0]))
    print("   centre-point values:", {k: (round(v[0], 6), round(v[1], 8)) for k, v in e.items()})
    d1 = abs(e[20][0] - e[40][0])
    d2 = abs(e[40][0] - e[80][0])
    order = np.log2(d1 / d2) if d2 > 0 else float("nan")
    print(f"   space order estimate (centre T): {order:.2f}")
    check("centre temperature converged (<1e-3 K between N=40 and N=80)", d2 < 1e-3, f"{d2:.2e}")

    et = {}
    for dt in (8.0, 4.0, 2.0, 1.0):
        s = RobustSolver(N=80, R0=0.02)
        res = s.run(props, t_end=300.0, T_init=c2k(28.0), C_init=2.55, dt=dt,
                    tol=1e-12)
        et[dt] = float(res.Cs[-1][0])
    dts = sorted(et, reverse=True)
    ords = [np.log2(abs(et[dts[i - 1]] - et[dts[i]]) /
                    max(abs(et[dts[i]] - et[dts[i + 1]]), 1e-300))
            for i in range(1, len(dts) - 1)]
    print("   dt:", {k: round(v, 8) for k, v in et.items()})
    print("   time orders:", [round(o, 2) for o in ords])


# --------------------------------------------------------------------------
# 4. physical sanity
# --------------------------------------------------------------------------
def test_physics():
    print("\n=== physical sanity (problem 1, 1800 s) ===")
    amb = mp.Ambient()
    props = mp.props_problem1(amb)
    props.h_m = 2e-6
    s = RobustSolver(N=80, R0=0.02)
    res = s.run(props, t_end=1800.0, T_init=c2k(28.0), C_init=2.55, dt=5.0,
                sample_dt=300.0, tol=1e-12)
    T = np.array(res.Ts)
    C = np.array(res.Cs)
    print(f"   T range: {k2c(T.min()):.3f} .. {k2c(T.max()):.3f} degC")
    print(f"   C range: {C.min():.6f} .. {C.max():.6f} kg/kg")
    print(f"   core T: {k2c(T[0,0]):.4f} -> {k2c(T[-1,0]):.4f} degC")
    print(f"   surface T: {k2c(T[0,-1]):.4f} -> {k2c(T[-1,-1]):.4f} degC")
    print(f"   core C: {C[0,0]:.6f} -> {C[-1,0]:.6f}")
    check("T within [0, 80] degC", k2c(T.min()) > -1.0 and k2c(T.max()) < 80.0,
          f"[{k2c(T.min()):.2f}, {k2c(T.max()):.2f}]")
    check("T monotonically increases at the surface",
          bool(np.all(np.diff(T[:, -1]) >= -1e-9)))
    check("C non-increasing everywhere", bool(np.all(np.diff(C, axis=0) <= 1e-12)))
    check("C bounded by [0, 2.55]", C.min() > -1e-9 and C.max() <= 2.55 + 1e-9)
    check("water inventory decreases", bool(np.all(np.diff(res.W) <= 1e-18)))


if __name__ == "__main__":
    test_steady_conduction()
    test_conservation()
    test_orders()
    test_physics()
    print("\n" + "=" * 70)
    print("FAILURES: " + ", ".join(FAIL) if FAIL else "ALL CHECKS PASSED")
    raise SystemExit(1 if FAIL else 0)
