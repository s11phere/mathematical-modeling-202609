# -*- coding: utf-8 -*-
"""
Verification suite for ``src/drying_solver.py`` (see docs/VALIDATION.md).

V1  transient analytical solution: constant-property heat conduction in a
    cylinder with a step change of the surface temperature, compared with the
    Bessel-series solution.  Yields observed orders of accuracy in space (p)
    and time (q).
V2  spatial convergence of the full nonlinear problem (N = 50..1600).
V3  temporal convergence of the full nonlinear problem (dt = 32..1 s).
V4  conservation audit: global water balance against the exact integral of the
    surface flux, and the steady-state analytical solution of problem 1.
V5  physical sanity checks (bounds, monotonicity, mesh independence of W).

Run:  python tests/test_solver.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.special import j0, j1

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drying_solver import DryerSolver1D, Props, c2k, k2c  # noqa: E402

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}{(' -- ' + detail) if detail else ''}")
    if not ok:
        FAIL.append(name)


def order(e1: float, e2: float, r: float) -> float:
    """Observed order between two errors with refinement ratio r."""
    if e2 <= 0 or e1 <= 0:
        return float("nan")
    return float(np.log(e1 / e2) / np.log(r))


# ---------------------------------------------------------------------------
# V1  transient analytical solution
# ---------------------------------------------------------------------------
def analytic_step_cylinder(r, t, alpha, R, T0, Ts, nterms=400):
    """T(r,t) for u_t = alpha*grad^2 u, u(r,0)=T0, u(R,t)=Ts, u bounded at 0.

    u = Ts + sum_n A_n J0(beta_n r/R) exp(-alpha beta_n^2 t / R^2),
    A_n = 2 (T0 - Ts) / (beta_n J1(beta_n)).
    """
    r = np.asarray(r, dtype=float)
    beta = np.array([float(z) for z in _bessel_zeros(nterms)])
    A = 2.0 * (T0 - Ts) / (beta * j1(beta))
    tb = t * alpha / R ** 2
    # (nterms, npoints)
    vals = np.exp(-np.outer(beta ** 2, tb)) * j0(np.outer(beta, r / R))
    return Ts + A @ vals


def _bessel_zeros(n: int) -> np.ndarray:
    """First n positive zeros of J0 via bisection on a fine bracketing grid."""
    from scipy.optimize import brentq

    zeros = []
    # J0 is oscillatory; bracket by scanning
    x = 1e-6
    prev = j0(x)
    step = 0.05
    while len(zeros) < n:
        x2 = x + step
        cur = j0(x2)
        if prev == 0.0:
            zeros.append(x)
        elif prev * cur < 0:
            zeros.append(brentq(j0, x, x2, xtol=1e-14, rtol=1e-15))
        prev, x = cur, x2
        if x > 1e5:
            break
    return np.array(zeros[:n])


def v1_transient_analytic():
    print("\n=== V1  transient analytical solution (Bessel series) ===")
    alpha = 7.66e-7
    R = 0.02
    T0, Ts = 301.0, 350.0

    def props_const() -> Props:
        return Props(
            rho=lambda C, T: np.full_like(T, 1.0),
            cp=lambda C, T: np.full_like(T, alpha),   # rho*cp*dT/dt = alpha*Lap(T)
            k=lambda C, T: np.full_like(T, alpha),
            D=lambda C, T: np.full_like(T, 1e-12),
            h=1e12,          # effectively Dirichlet surface
            h_m=0.0,
            Lw=0.0,
            Tamb=lambda t: Ts,
            Camb=lambda t: 0.0,
            rho_d0=1.0,
        )

    tref = 300.0
    exact_c = float(analytic_step_cylinder(np.array([0.0]), tref, alpha, R, T0, Ts)[0])
    exact_5 = float(analytic_step_cylinder(np.array([0.01]), tref, alpha, R, T0, Ts)[0])

    errs = {}
    for N in (50, 100, 200, 400, 800):
        s = DryerSolver1D(N=N, R0=R)
        ts, Ts_, Cs_, Rs_, diag = s.run(
            props_const(), t_end=tref, T_init=T0, C_init=0.0, dt=0.25, max_iter=40, tol=1e-12
        )
        Tc = Ts_[-1][0]
        s2 = DryerSolver1D(N=N, R0=R)
        T_out, C_out, mask = s2.sample_profiles(ts[-1:], Ts_[-1:], Cs_[-1:], Rs_[-1:], [0.01])
        errs[N] = (abs(Tc - exact_c), abs(float(T_out[0, 0]) - exact_5))
    print("   N        err(centre)      err(r=0.01)   p(centre)  p(r=0.01)")
    Ns = sorted(errs)
    for i, N in enumerate(Ns):
        ec, eh = errs[N]
        if i == 0:
            print(f"  {N:5d}   {ec:.3e}     {eh:.3e}      -          -")
        else:
            p1 = order(errs[Ns[i - 1]][0], ec, Ns[i] / Ns[i - 1])
            p2 = order(errs[Ns[i - 1]][1], eh, Ns[i] / Ns[i - 1])
            print(f"  {N:5d}   {ec:.3e}     {eh:.3e}     {p1:5.2f}      {p2:5.2f}")
    finest = errs[Ns[-1]][1]
    check("V1a transient annual solution converged (<1e-3 K at N=800)", finest < 1e-3,
          f"err(r=0.01)={finest:.3e} K")
    slopes = [order(errs[Ns[i - 1]][1], errs[Ns[i]][1], Ns[i] / Ns[i - 1]) for i in range(1, len(Ns))]
    check("V1b spatial order >= 1.8 on the finest 3 refinements",
          float(np.min(slopes[-3:])) >= 1.8, f"slopes={['%.2f' % s for s in slopes]}")

    # temporal order at fixed N
    print("   dt       err(centre)    q")
    e_t = {}
    for dt in (4.0, 2.0, 1.0, 0.5, 0.25):
        s = DryerSolver1D(N=200, R0=R)
        ts, Ts_, Cs_, Rs_, diag = s.run(
            props_const(), t_end=tref, T_init=T0, C_init=0.0, dt=dt, max_iter=40, tol=1e-12
        )
        e_t[dt] = abs(Ts_[-1][0] - exact_c)
    dts = sorted(e_t, reverse=True)
    for i, dt in enumerate(dts):
        if i == 0:
            print(f"  {dt:5.2f}   {e_t[dt]:.3e}      -")
        else:
            q = order(e_t[dts[i - 1]], e_t[dt], dts[i - 1] / dt)
            print(f"  {dt:5.2f}   {e_t[dt]:.3e}    {q:5.2f}")
    qs = [order(e_t[dts[i - 1]], e_t[dts[i]], dts[i - 1] / dts[i]) for i in range(1, len(dts))]
    check("V1c temporal order >= 0.9 (backward Euler)",
          float(np.min(qs[-3:])) >= 0.9, f"orders={['%.2f' % s for s in qs]}")


# ---------------------------------------------------------------------------
# problem-1 property set (appendix 2), used by V2-V5
# ---------------------------------------------------------------------------
RHO_DRY_P1 = None


def props_problem1(eps_rad: float = 0.0):
    c0 = 7e-9 / np.exp(-0.89 * 2.55)          # D = 7e-9 e^{-0.89 C}
    rho_solid = 820.0
    rho_d = rho_solid / (1.0 + 2.55)
    return Props(
        rho=lambda C, T: np.full_like(C, rho_solid),
        cp=lambda C, T: np.full_like(C, 2600.0),
        k=lambda C, T: np.full_like(C, 0.36),
        D=lambda C, T: c0 * np.exp(-0.89 * C),
        h=25.0,
        h_m=8e-7,
        Lw=2.26e6,
        Tamb=lambda t: 301.15,          # 28 degC
        Camb=lambda t: 0.01963,
        rho_d0=rho_d,
        eps_rad=eps_rad,
        T_rad=(lambda t: 301.15) if eps_rad else None,
    ), rho_d


def v2_spatial_and_v4_conservation():
    print("\n=== V2  spatial convergence (full nonlinear problem 1) ===")
    props, rho_d = props_problem1()
    t_end = 1800.0
    ref = None
    errs = {}
    for N in (50, 100, 200, 400, 800, 1600):
        s = DryerSolver1D(N=N, R0=0.02)
        ts, Ts_, Cs_, Rs_, diag = s.run(
            props, t_end=t_end, T_init=c2k(28.0), C_init=2.55, dt=1.0, max_iter=60, tol=1e-11
        )
        prof = np.concatenate(([Ts_[-1][0]], Ts_[-1][:N], [Ts_[-1][N]]))
        profC = np.concatenate(([Cs_[-1][0]], Cs_[-1][:N], [Cs_[-1][N]]))
        if N == 1600:
            ref = (prof, profC)
        errs[N] = (prof, profC)

    print("   N      max|dT| vs N=1600    max|dC| vs N=1600    p(T)   p(C)")
    Ns = sorted(errs)
    eT, eC = {}, {}
    for N in Ns:
        T, C = errs[N]
        eT[N] = float(np.max(np.abs(T - ref[0])))
        eC[N] = float(np.max(np.abs(C - ref[1])))
    for i, N in enumerate(Ns):
        if i == 0:
            print(f"  {N:5d}     {eT[N]:.3e}          {eC[N]:.3e}          -      -")
        else:
            pT = order(eT[Ns[i - 1]], eT[N], Ns[i] / Ns[i - 1])
            pC = order(eC[Ns[i - 1]], eC[N], Ns[i] / Ns[i - 1])
            print(f"  {N:5d}     {eT[N]:.3e}          {eC[N]:.3e}        {pT:5.2f}  {pC:5.2f}")
    check("V2a temperature spatial order >= 1.8", order(eT[400], eT[800], 2.0) >= 1.8,
          f"p={order(eT[400], eT[800], 2.0):.2f}")
    check("V2b moisture spatial order >= 1.8", order(eC[400], eC[800], 2.0) >= 1.8,
          f"p={order(eC[400], eC[800], 2.0):.2f}")

    print("\n=== V4  water-conservation audit ===")
    for N in (100, 200, 400):
        s = DryerSolver1D(N=N, R0=0.02)
        ts, Ts_, Cs_, Rs_, diag = s.run(
            props, t_end=t_end, T_init=c2k(28.0), C_init=2.55, dt=5.0, max_iter=60, tol=1e-11
        )
        t = np.array(diag.t)
        W = np.array(diag.W)
        jw = np.array(diag.jw)
        # water that left through the lateral surface per unit length
        m_out = 2.0 * np.pi * 0.02 * np.trapz(jw, t)
        res = (W[0] - W[-1]) - m_out
        rel = abs(res) / abs(W[0] - W[-1])
        print(f"  N={N:4d}  W0-W1={W[0]-W[-1]:.6e}  flux_int={m_out:.6e}  rel.res={rel:.3e}")
        check(f"V4a water balance N={N} (rel < 1e-5)", rel < 1e-5, f"rel={rel:.2e}")


def v5_physics():
    print("\n=== V5  physical sanity checks ===")
    props, rho_d = props_problem1()
    s = DryerSolver1D(N=400, R0=0.02)
    ts, Ts_, Cs_, Rs_, diag = s.run(
        props, t_end=1800.0, T_init=c2k(28.0), C_init=2.55, dt=1.0, max_iter=60, tol=1e-11
    )
    allC = np.array([np.concatenate(([p[0]], p[: s.N], [p[s.N]])) for p in Cs_])
    allT = np.array([np.concatenate(([p[0]], p[: s.N], [p[s.N]])) for p in Ts_])
    check("V5a moisture is bounded in [0, 2.55]", allC.min() >= -1e-9 and allC.max() <= 2.55 + 1e-9,
          f"range=[{allC.min():.6f},{allC.max():.6f}]")
    check("V5b temperature remains between 28 C and Tamb", allT.min() >= c2k(28.0) - 1e-6,
          f"Tmin={float(k2c(allT.min())):.4f} C")
    check("V5c moisture decreases monotonically at the surface",
          bool(np.all(np.diff(np.array(diag.Cs)) <= 1e-12)),
          f"Cs: {diag.Cs[0]:.5f} -> {diag.Cs[-1]:.5f}")
    W = np.array(diag.W)
    check("V5d total water decreases monotonically", bool(np.all(np.diff(W) <= 1e-15)))
    # mesh independence of W at the final time
    Ws = []
    for N in (100, 200, 400, 800):
        s2 = DryerSolver1D(N=N, R0=0.02)
        _, _, _, _, d2 = s2.run(props, t_end=1800.0, T_init=c2k(28.0), C_init=2.55,
                                dt=10.0, max_iter=60, tol=1e-11)
        Ws.append(d2.W[-1])
    spread = (max(Ws) - min(Ws)) / np.mean(Ws)
    check("V5e total water mesh independent (rel < 1e-4)", spread < 1e-4, f"spread={spread:.2e}")


def main() -> int:
    v1_transient_analytic()
    v2_spatial_and_v4_conservation()
    v5_physics()
    print("\n" + "=" * 70)
    if FAIL:
        print(f"FAILURES ({len(FAIL)}): " + ", ".join(FAIL))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
