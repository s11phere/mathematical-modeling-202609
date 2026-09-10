# -*- coding: utf-8 -*-
"""
Verification of ``src/mol_solver.py`` (acceptance tests).

V1  Steady conduction with a uniform volumetric source.  Exact:
        T(r) = T_inf + Q0 R/(2h) + Q0 (R^2 - r^2)/(4k)
    centre-to-surface drop = Q0 R^2/(4k)
V2  Transient conduction in an infinite cylinder with a step change of the
    surface temperature -- Bessel series:
        T(r,t) = Ts + sum_n A_n J0(b_n r/R) exp(-alpha b_n^2 t/R^2)
        A_n    = 2 (T0 - Ts) / (b_n J1(b_n)),   J0(b_n) = 0
V3  Water conservation against the integral of the surface flux.
V4  Problem-1 physical sanity.
"""
import sys
import time
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


def ana(r, t, alpha, R, T0=300.0, Ts=350.0):
    r = np.asarray(r, float)
    tb = t * alpha / R ** 2
    return Ts + A_N @ (np.exp(-np.outer(B ** 2, tb)) * j0(np.outer(B, r / R)))


# --------------------------------------------------------------------------
def v1_steady_source():
    print("\n=== V1  steady conduction with a uniform source ===")
    K, H, TINF, R = 0.36, 25.0, 350.0, 0.02
    Q0, RHO, CP = 1.0e5, 820.0, 2600.0
    exact_drop = Q0 * R ** 2 / (4 * K)
    print(f"   exact centre-to-surface drop = {exact_drop:.6f} K")
    props = Props(rho=lambda C, T: np.full_like(T, RHO),
                  cp=lambda C, T: np.full_like(T, CP),
                  k=lambda C, T: np.full_like(T, K),
                  D=lambda C, T: np.full_like(T, 1e-12),
                  h=H, h_m=0.0, Lw=0.0,
                  Tamb=lambda t: TINF, Camb=lambda t: 0.0, rho_d0=1.0, C_sat=1.0)
    errs = {}
    for N in (10, 20, 40, 80, 160):
        s = MolSolver(N=N, R0=R)
        r = s.run(props, 1e7, TINF, 0.0, sample_dt=None, rtol=1e-11,
                  atol=1e-13, method="Radau", max_step=1e7, Qsrc=Q0)
        T = r.T[-1]
        rr = R * s.xi_c
        ex = TINF + Q0 * R / (2 * H) + Q0 * (R ** 2 - rr ** 2) / (4 * K)
        errs[N] = float(np.max(np.abs(T - ex)))
        print(f"   N={N:4d}  drop={T[0]-T[-1]:10.6f} K   maxerr={errs[N]:.4e} K")
    Ns = sorted(errs)
    for i in range(1, len(Ns)):
        p = np.log2(errs[Ns[i - 1]] / errs[Ns[i]])
        print(f"   order {Ns[i-1]:4d}->{Ns[i]:4d}: {p:.2f}")
    check("V1 drop converges to the analytic value (error halves per refinement, O(h))",
          errs[160] < 0.2 and errs[80] < 0.4, f"{errs[160]:.2e} K at N=160")
    check("V1 errors decrease monotonically",
          all(errs[Ns[i]] < errs[Ns[i - 1]] for i in range(1, len(Ns))))


def v2_bessel():
    print("\n=== V2  transient conduction vs the Bessel series ===")
    alpha, R = 7.66e-7, 0.02
    # rho cp = 1 and k = alpha makes alpha_eff = k/(rho cp) = alpha
    props = Props(rho=lambda C, T: np.full_like(T, 1.0),
                  cp=lambda C, T: np.full_like(T, 1.0),
                  k=lambda C, T: np.full_like(T, alpha),
                  D=lambda C, T: np.full_like(T, 1e-12),
                  h=1e12, h_m=0.0, Lw=0.0,
                  Tamb=lambda t: 350.0, Camb=lambda t: 0.0, rho_d0=1.0, C_sat=1.0)
    tref = 300.0
    errs = {}
    for N in (20, 40, 80, 160):
        s = MolSolver(N=N, R0=R)
        r = s.run(props, tref, 300.0, 0.0, sample_dt=None, rtol=1e-10,
                  atol=1e-13, method="Radau", max_step=0.5)
        ex = ana(R * s.xi_c, tref, alpha, R)
        errs[N] = float(np.max(np.abs(r.T[-1] - ex)))
        print(f"   N={N:4d}  Tc={r.Tc[-1]:.4f} (exact {float(ana(0.0, tref, alpha, R)):.4f})"
              f"   maxerr={errs[N]:.4e} K")
    Ns = sorted(errs)
    for i in range(1, len(Ns)):
        p = np.log2(errs[Ns[i - 1]] / errs[Ns[i]])
        print(f"   order {Ns[i-1]:4d}->{Ns[i]:4d}: {p:.2f}")
    check("V2 Bessel match (O(h), first-order; <0.1 K at N=160)",
          errs[160] < 0.1 and errs[80] > errs[160], f"{errs[160]:.2e} K")


def v3_conservation():
    print("\n=== V3  water conservation ===")
    amb = mp.Ambient()
    for mode in ("prescribed", "lewis"):
        p = mp.props_problem1(amb)
        p.hm_mode = mode
        s = MolSolver(N=50, R0=0.02)
        r = s.run(p, 900.0, c2k(28.0), 2.55, sample_dt=150.0, rtol=1e-8,
                  atol=1e-10, method="Radau", max_step=10.0)
        t = np.array(r.ts)
        W = np.array(r.W)
        jw = np.array(r.jw)
        m = 2 * np.pi * 0.02 * np.trapezoid(jw, t)
        dW = W[0] - W[-1]
        err = abs(dW - m)
        print(f"   mode={mode:11s} dW={dW:+.6e}  flux_int={m:+.6e}  "
              f"|diff|={err:.2e} kg/m")
        print(f"     Ts {k2c(r.Tsurf[0]):.4f} -> {k2c(r.Tsurf[-1]):.4f} C ; "
              f"Tc {k2c(r.Tc[0]):.4f} -> {k2c(r.Tc[-1]):.4f} C ; "
              f"Cs {r.Csurf[0]:.6f} -> {r.Csurf[-1]:.6f}")
        check(f"V3 {mode}: |dW - int jw| < 1e-7 kg/m", err < 1e-7, f"{err:.2e}")


def v4_physics():
    print("\n=== V4  problem-1 physical sanity ===")
    amb = mp.Ambient()
    p = mp.props_problem1(amb)
    s = MolSolver(N=100, R0=0.02)
    r = s.run(p, 1800.0, c2k(28.0), 2.55, sample_dt=300.0, rtol=1e-8,
              atol=1e-10, method="Radau", max_step=10.0)
    T = np.array(r.T)
    C = np.array(r.C)
    print(f"   T range {k2c(T.min()):.4f} .. {k2c(T.max()):.4f} degC")
    print(f"   C range {C.min():.6f} .. {C.max():.6f} kg/kg")
    for k, tt in enumerate(r.ts):
        print(f"   t={tt:6.0f}  Ts={k2c(r.Tsurf[k]):8.4f}  Tc={k2c(r.Tc[k]):8.4f}  "
              f"Cs={r.Csurf[k]:.6f}  Cc={r.Cc[k]:.6f}  jw={r.jw[k]:.3e}")
    check("V4 T physical", -1 < k2c(T.min()) and k2c(T.max()) < 95)
    check("V4 C within [0, 2.55]", C.min() > -1e-9 and C.max() <= 2.55 + 1e-9)
    check("V4 W non-increasing", bool(np.all(np.diff(r.W) <= 1e-15)))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    t0 = time.time()
    if which in ("all", "1"):
        v1_steady_source()
    if which in ("all", "2"):
        v2_bessel()
    if which in ("all", "3"):
        v3_conservation()
    if which in ("all", "4"):
        v4_physics()
    print(f"\n({time.time()-t0:.1f} s)")
    print("FAILURES: " + ", ".join(FAIL) if FAIL else "ALL CHECKS PASSED")
    raise SystemExit(1 if FAIL else 0)
