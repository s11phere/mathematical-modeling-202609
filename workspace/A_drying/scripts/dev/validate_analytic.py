# -*- coding: utf-8 -*-
"""
Verification of ``final_solver`` against an analytical solution.

A transient heat-conduction problem in an infinite cylinder with a step change
of the surface temperature has the classical Bessel-series solution

    T(r,t) = Ts + sum_n A_n J0(beta_n r/R) exp(-alpha beta_n^2 t/R^2),
    A_n    = 2 (T0 - Ts) / (beta_n J1(beta_n)),

where beta_n are the positive zeros of J0.  It is used here to measure the
observed order of accuracy in space and in time.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.special import j0, j1

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from final_solver import FinalSolver, Props, c2k, k2c  # noqa: E402


def bessel_zeros(n):
    zs, x, prev = [], 1e-8, j0(1e-8)
    while len(zs) < n:
        x2 = x + 0.05
        cur = j0(x2)
        if prev * cur < 0:
            zs.append(brentq(j0, x, x2, xtol=1e-14, rtol=1e-15))
        prev, x = cur, x2
    return np.array(zs[:n])


BETA = bessel_zeros(300)
A_N = None


def analytic(r, t, alpha, R, T0, Ts):
    global A_N
    if A_N is None:
        A_N = 2.0 * (T0 - Ts) / (BETA * j1(BETA))
    r = np.asarray(r, float)
    tb = t * alpha / R ** 2
    return Ts + A_N @ (np.exp(-np.outer(BETA ** 2, tb)) * j0(np.outer(BETA, r / R)))


def props_const(alpha, h):
    return Props(
        rho=lambda C, T: np.full_like(T, 1.0),
        cp=lambda C, T: np.full_like(T, alpha),     # rho cp dT/dt = alpha Lap T
        k=lambda C, T: np.full_like(T, alpha),
        D=lambda C, T: np.full_like(T, 1e-12),
        h=h, h_m=0.0, Lw=0.0,
        Tamb=lambda t: 350.0, Camb=lambda t: 0.0, rho_d0=1.0, C_sat=1.0,
    )


def main():
    alpha, R, T0, Ts = 7.66e-7, 0.02, 300.0, 350.0
    tref = 300.0
    ex_c = float(analytic(np.array([0.0]), tref, alpha, R, T0, Ts)[0])
    ex_h = float(analytic(np.array([0.01]), tref, alpha, R, T0, Ts)[0])
    print(f"exact at t={tref}s: centre={ex_c:.6f} K  r=0.01m={ex_h:.6f} K")

    print("\nspace convergence (dt = 0.25 s):")
    errs = {}
    for N in (25, 50, 100, 200):
        s = FinalSolver(N=N, R0=R)
        r = s.run(props_const(alpha, 1e12), tref, T0, 0.0, dt=0.25,
                  max_iter=30, tol=1e-13)
        rr = R * s.grid.xi_c
        # compare against the exact solution at the cell centres
        ex = analytic(rr, tref, alpha, R, T0, Ts)
        errs[N] = float(np.max(np.abs(r.T[-1] - ex)))
    Ns = sorted(errs)
    for i, N in enumerate(Ns):
        if i == 0:
            print(f"   N={N:4d}  max|T-exact|={errs[N]:.4e} K")
        else:
            p = np.log2(errs[Ns[i - 1]] / errs[N])
            print(f"   N={N:4d}  max|T-exact|={errs[N]:.4e} K   order={p:.2f}")

    print("\ntime convergence (N = 200):")
    et = {}
    s0 = FinalSolver(N=200, R0=R)
    rr = R * s0.grid.xi_c
    ex = analytic(rr, tref, alpha, R, T0, Ts)
    for dt in (4.0, 2.0, 1.0, 0.5, 0.25):
        s = FinalSolver(N=200, R0=R)
        r = s.run(props_const(alpha, 1e12), tref, T0, 0.0, dt=dt,
                  max_iter=30, tol=1e-13)
        et[dt] = float(np.max(np.abs(r.T[-1] - ex)))
    dts = sorted(et, reverse=True)
    for i, dt in enumerate(dts):
        if i == 0:
            print(f"   dt={dt:5.2f}  max|T-exact|={et[dt]:.4e} K")
        else:
            q = np.log2(et[dts[i - 1]] / et[dt])
            print(f"   dt={dt:5.2f}  max|T-exact|={et[dt]:.4e} K   order={q:.2f}")


if __name__ == "__main__":
    main()
