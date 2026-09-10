# -*- coding: utf-8 -*-
"""
Verification of ``src/mol_solver.py``.

V1  transient heat conduction in an infinite cylinder with a step change of the
    surface temperature, against the Bessel-series solution.
V2  water conservation against the exact integral of the surface flux.
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

from mol_solver import MolSolver, Props, c2k, k2c  # noqa: E402
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


B = bessel_zeros(400)
A_N = 2.0 * (300.0 - 350.0) / (B * j1(B))


def ana(r, t, alpha=7.66e-7, R=0.02):
    r = np.asarray(r, float)
    return 350.0 + A_N @ (np.exp(-np.outer(B ** 2, t * alpha / R ** 2))
                          * j0(np.outer(B, r / R)))


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
    for h in (1e5,):
        print(f" h = {h:g} W m^-2 K^-1")
        for N in (20, 40, 80):
            s = MolSolver(N=N, R0=R)
            r = s.run(props_cond(alpha, h), tref, 300.0, 0.0, sample_dt=None,
                      rtol=1e-9, atol=1e-11, method='Radau', max_step=2.0)
            rr = R * s.xi_c
            ex = ana(rr, tref, alpha, R)
            e = float(np.max(np.abs(r.T[-1] - ex)))
            print(f"   N={N:4d}  max|T-exact|={e:.4e} K")


def v2():
    print("\n=== V2  water conservation (problem 1) ===")
    amb = mp.Ambient()
    for mode in ("prescribed", "lewis"):
        p = mp.props_problem1(amb)
        p.hm_mode = mode
        s = MolSolver(N=50, R0=0.02)
        r = s.run(p, 1800.0, c2k(28.0), 2.55, sample_dt=60.0, rtol=1e-8,
                  atol=1e-10, method='Radau', max_step=10.0)
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
        check(f"V2 water balance {mode} (rel < 1e-3)", rel < 1e-3, f"{rel:.2e}")


def v3():
    print("\n=== V3  physical sanity (problem 1) ===")
    amb = mp.Ambient()
    p = mp.props_problem1(amb)
    s = MolSolver(N=100, R0=0.02)
    r = s.run(p, 1800.0, c2k(28.0), 2.55, sample_dt=300.0, rtol=1e-8,
                  atol=1e-10, method='Radau', max_step=10.0)
    T = np.array(r.T)
    C = np.array(r.C)
    print(f"   T: {k2c(T.min()):.3f} .. {k2c(T.max()):.3f} degC")
    print(f"   C: {C.min():.6f} .. {C.max():.6f} kg/kg")
    for k, tt in enumerate(r.ts):
        print(f"   t={tt:7.0f}s Ts={k2c(T[k,-1]):8.4f}C Tc={k2c(T[k,0]):8.4f}C "
              f"Cs={r.Csurf[k]:.6f} Cc={r.Cc[k]:.6f} jw={r.jw[k]:.3e}")
    check("T physical", -1 < k2c(T.min()) and k2c(T.max()) < 95)
    check("C in [0, 2.55]", C.min() > -1e-6 and C.max() <= 2.55 + 1e-3)
    check("W non-increasing", bool(np.all(np.diff(r.W) <= 1e-12)))


if __name__ == "__main__":
    v1()
    v2()
    v3()
    print("\n" + "=" * 70)
    print("FAILURES: " + ", ".join(FAIL) if FAIL else "ALL CHECKS PASSED")
    raise SystemExit(1 if FAIL else 0)
