# -*- coding: utf-8 -*-
"""
Decisive test: does the discrete cylindrical divergence match the exact
continuum divergence of the same flux field?

For T(r) = A + B (r/R)^2 we have exactly

    (1/r) d/dr ( r k dT/dr ) = 4 k B / R^2        (constant)

so applying the discrete operator to that field, with the surface and centre
terms handled as the code does, must return 4kB/R^2 in every cell.
"""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, Props  # noqa: E402

K, RHO, CP = 0.36, 820.0, 2600.0
R = 0.02
props = Props(rho=lambda C, T: np.full_like(T, RHO),
              cp=lambda C, T: np.full_like(T, CP),
              k=lambda C, T: np.full_like(T, K),
              D=lambda C, T: np.full_like(T, 1e-12),
              h=1e30, h_m=0.0, Lw=0.0,
              Tamb=lambda t: 0.0, Camb=lambda t: 0.0, rho_d0=1.0, C_sat=1.0)

A, B = 300.0, 100.0
exact_div = 4.0 * K * B / R ** 2

for N in (8, 16, 32):
    s = MolSolver(N=N, R0=R)
    r = R * s.xi_c
    T = A + B * (r / R) ** 2
    # apply the discrete operator manually, mirroring rhs()
    hr = R / N
    inv_h = N / R
    kk = np.full(N, K)
    dT = np.zeros(N)
    for i in range(N):
        Vw = s.Vw[i]
        if i > 0:
            kf = 0.5 * (kk[i - 1] + kk[i])
            dT[i] += s.Fa[i] * kf * inv_h * (T[i - 1] - T[i]) / Vw
        if i < N - 1:
            kf = 0.5 * (kk[i] + kk[i + 1])
            dT[i] -= s.Fa[i + 1] * kf * inv_h * (T[i] - T[i + 1]) / Vw
    # interior cells only (exclude the surface cell, where the code adds film)
    print(f"N={N:3d}  exact divergence = {exact_div:.6e} W/m^3")
    print(f"        discrete (cells 0..N-2): "
          f"{np.array2string(dT[:N-1], precision=4)}")
    rel = np.max(np.abs(dT[:N-1] - exact_div)) / exact_div
    print(f"        max relative error = {rel:.3e}")
    # also check the cell-volume-weighted sum (conservativeness)
    tot = float(np.sum(s.Vw * dT))
    print(f"        sum(Vw*div) = {tot:.6e}  (interior only, no boundary flux)")
