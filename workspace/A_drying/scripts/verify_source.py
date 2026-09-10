# -*- coding: utf-8 -*-
"""
Verification of ``src/mol_solver.py`` by a manufactured steady-state problem.

With a uniform volumetric heat source Q0 [W m^-3], constant k, a convective
surface (h, T_inf) and symmetry at the centre, the steady solution is

    T(r) = T_inf + Q0 R/(2h) + Q0 (R^2 - r^2)/(4k)
    T(0) - T(R) = Q0 R^2/(4k)

This exercises the cylindrical diffusion operator and the surface boundary
condition simultaneously, and lets the observed order of spatial accuracy be
measured directly.
"""
import sys
import time
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, Props  # noqa: E402

Q0 = 1.0e5           # W m^-3
K = 0.36             # W m^-1 K^-1
H = 25.0             # W m^-2 K^-1
TINF = 350.0
R = 0.02
RHO = 820.0
CP = 2600.0


def exact(r):
    r = np.asarray(r, float)
    return TINF + Q0 * R / (2 * H) + Q0 * (R ** 2 - r ** 2) / (4 * K)


def main():
    print("=== steady conduction with a uniform source ===")
    print(f"Q0={Q0:g} k={K} h={H} Tinf={TINF} R={R}")
    print(f"exact: T(0)={exact(0.0):.6f}  T(R)={exact(R):.6f}  "
          f"drop={float(exact(0.0)-exact(R)):.6f} K")
    for N in (10, 20, 40, 80):
        # build a problem with the source added through the boundary callable
        props = Props(rho=lambda C, T: np.full_like(T, RHO),
                      cp=lambda C, T: np.full_like(T, CP),
                      k=lambda C, T: np.full_like(T, K),
                      D=lambda C, T: np.full_like(T, 1e-12),
                      h=H, h_m=0.0, Lw=0.0,
                      Tamb=lambda t: TINF, Camb=lambda t: 0.0,
                      rho_d0=1.0, C_sat=1.0)
        s = MolSolver(N=N, R0=R)
        # add the volumetric source by monkey-patching rhs
        orig = s.rhs

        def rhs_with_source(t, y, props_, t_end, _s=s, _orig=orig):
            d = _orig(t, y, props_, t_end)
            d[: _s.N] += Q0 / (RHO * CP)
            return d

        s.rhs = rhs_with_source
        t0 = time.time()
        res = s.run(props, 4.0e6, TINF, 0.0, sample_dt=None,
                    rtol=1e-10, atol=1e-12, method="Radau", max_step=1.0e5)
        Tn = res.T[-1]
        rr = R * s.xi_c
        e = float(np.max(np.abs(Tn - exact(rr))))
        c = float(Tn[0] - Tn[-1])
        print(f"  N={N:3d}  max|T-exact|={e:.4e} K   T(0)-T(R)={c:.6f} K "
              f"(exact {float(exact(0.0)-exact(R)):.6f})   ({time.time()-t0:.1f}s)")
        if N > 10:
            pass


if __name__ == "__main__":
    main()
