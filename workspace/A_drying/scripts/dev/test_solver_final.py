# -*- coding: utf-8 -*-
"""
Verification of ``src/solver.py``.

V1  transient heat conduction in an infinite cylinder with a step change of the
    surface temperature, against the Bessel-series solution:

        T(r,t) = Ts + sum_n A_n J0(b_n r/R) exp(-alpha b_n^2 t/R^2)
        A_n    = 2 (T0 - Ts) / (b_n J1(b_n)),   J0(b_n) = 0

V2  water conservation: dW/dt against the exact integral of the surface flux.
V3  problem-1 physical sanity.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.special import j0, j1

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solver import Solver, Props, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402

FAIL = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def bessel_zeros(n):
    zs, x, prev = [], 1e-8, j0(1e-8)
    while len(zs) < n and x < 1e5:
        x2 = x + 0.05
        cur = j0(x2)
        if prev * cur < 0:
            zs.append(brentq(j0, x, x2, xtol=1e-14, rtol=1e-15))
        prev, x = cur, x2
    return np.array(zs[:n])


BETA = bessel_zeros(400)
A_N = 2.0 * (300.0 - 350.0) / (BETA * j1(BETA))


def analytic(r, t, alpha, R, T0=300.0, Ts=350.0):
    r = np.asarray(r, float)
    tb = t * alpha / R ** 2
    return Ts + A_N @ (np.exp(-np.outer(BETA ** 2, tb)) * j0(np.outer(BETA, r / R)))


def props_cond(alpha, h):
    return Props(rho=lambda C, T: np.full_like(T, 1.0),
                 cp=lambda C, T: np.full_like(T, alpha),
                 k=lambda C, T: np.full_like(T, alpha),
                 D=lambda C, T: np.full_like(T, 1e-12),
                 h=h, h_m=0.0, Lw=0.0,
                 Tamb=lambda t: 350.0, Camb=lambda t: 0.0,
                 rho_d0=1.0, C_sat=1.0)


def v1():
    print("=== V1  transient conduction vs Bessel series ===")
    alpha, R, tref = 7.66e-7, 0.02, 300.0
    errs = {}
    for N in (25, 50, 100, 200):
        s = Solver(N=N, R0=R)
        r = s.run(props_cond(alpha, 1e5), tref, 300.0, 0.0, dt=0.25,
                  max_iter=30, tol=1e-13)
        rr = R * s.xi_c
        ex = analytic(rr, tref, alpha, R)
        errs[N] = float(np.max(np.abs(r.T[-1] - ex)))
    Ns = sorted(errs)
    for i, N in enumerate(Ns):
        if i == 0:
            print(f"   N={N:4d}  max|T-exact|={errs[N]:.4e} K")
        else:
            p = np.log2(errs[Ns[i - 1]] / errs[N])
            print(f"   N={N:4d}  max|T-exact|={errs[N]:.4e} K   order={p:.2f}")
    check("V1a converged (<5e-3 K at N=200)", errs[200] < 5e-3, f"{errs[200]:.2e} K")
    p = np.log2(errs[50] / errs[100])
    check("V1b spatial order >= 1.8", p >= 1.8, f"order={p:.2f}")

    et = {}
    for dt in (4.0, 2.0, 1.0, 0.5):
        s = Solver(N=200, R0=R)
        r = s.run(props_cond(alpha, 1e5), tref, 300.0, 0.0, dt=dt,
                  max_iter=30, tol=1e-13)
        ex = analytic(R * s.xi_c, tref, alpha, R)
        et[dt] = float(np.max(np.abs(r.T[-1] - ex)))
    dts = sorted(et, reverse=True)
    for i, dt in enumerate(dts):
        if i == 0:
            print(f"   dt={dt:5.2f}  max|T-exact|={et[dt]:.4e} K")
        else:
            q = np.log2(et[dts[i - 1]] / et[dt])
            print(f"   dt={dt:5.2f}  max|T-exact|={et[dt]:.4e} K   order={q:.2f}")


def v2():
    print("\n=== V2  water conservation ===")
    amb = mp.Ambient()
    for mode in ("prescribed", "lewis"):
        p = mp.props_problem1(amb)
        p.hm_mode = mode
        s = Solver(N=50, R0=0.02)
        r = s.run(p, 1800.0, c2k(28.0), 2.55, dt=10.0, max_iter=60, tol=1e-12)
        t = np.array(r.ts)
        W = np.array(r.W)
        jw = np.array(r.jw)
        m = 2 * np.pi * 0.02 * np.trapezoid(jw, t)
        dW = W[0] - W[-1]
        rel = abs(dW - m) / max(abs(dW), 1e-30)
        print(f"   mode={mode:11s} dW={dW:.6e} flux_int={m:.6e} rel={rel:.3e}")
        print(f"     Ts {k2c(r.Tsurf[0]):.4f} -> {k2c(r.Tsurf[-1]):.4f} C ; "
              f"Tc {k2c(r.Tc[0]):.4f} -> {k2c(r.Tc[-1]):.4f} C")
        print(f"     Cc {r.Cc[0]:.6f} -> {r.Cc[-1]:.6f} ; "
              f"Cs {r.Csurf[0]:.6f} -> {r.Csurf[-1]:.6f} ; "
              f"jw {r.jw[0]:.4e} -> {r.jw[-1]:.4e}")
        check(f"V2 water balance {mode} (rel < 1e-4)", rel < 1e-4, f"{rel:.2e}")


def v3():
    print("\n=== V3  physical sanity ===")
    amb = mp.Ambient()
    p = mp.props_problem1(amb)
    s = Solver(N=100, R0=0.02)
    r = s.run(p, 1800.0, c2k(28.0), 2.55, dt=5.0, sample_dt=300.0, max_iter=60, tol=1e-12)
    T = np.array(r.T)
    C = np.array(r.C)
    print(f"   T: {k2c(T.min()):.3f} .. {k2c(T.max()):.3f} degC")
    print(f"   C: {C.min():.6f} .. {C.max():.6f} kg/kg")
    print(f"   core T {k2c(T[0,0]):.4f} -> {k2c(T[-1,0]):.4f} degC")
    print(f"   surface T {k2c(T[0,-1]):.4f} -> {k2c(T[-1,-1]):.4f} degC")
    check("T physical", -1 < k2c(T.min()) and k2c(T.max()) < 90)
    check("C in [0, 2.55]", C.min() > -1e-9 and C.max() <= 2.55 + 1e-9)
    check("W non-increasing", bool(np.all(np.diff(r.W) <= 1e-18)))


if __name__ == "__main__":
    v1()
    v2()
    v3()
    print("\n" + "=" * 70)
    print("FAILURES: " + ", ".join(FAIL) if FAIL else "ALL CHECKS PASSED")
    raise SystemExit(1 if FAIL else 0)
