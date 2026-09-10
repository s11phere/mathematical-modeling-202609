# -*- coding: utf-8 -*-
"""Inspect the Newton steps and Jacobian for the steady-conduction check."""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from final_solver import FinalSolver, Props, c2k, k2c  # noqa: E402
from scipy.linalg import solve_banded  # noqa: E402

R, Ts, T0 = 0.02, 350.0, 300.0
p = Props(rho=lambda C, T: np.full_like(T, 820.0),
          cp=lambda C, T: np.full_like(T, 2600.0),
          k=lambda C, T: np.full_like(T, 0.36),
          D=lambda C, T: np.full_like(T, 1e-12),
          h=1e8, h_m=0.0, Lw=0.0,
          Tamb=lambda t: Ts, Camb=lambda t: 0.0, rho_d0=1.0, C_sat=1.0)

N = 10
s = FinalSolver(N=N, R0=R)
dt = 1.0e6
T = np.full(N, T0)
C = np.full(N, 0.0)
U = np.concatenate([T, C])
n = 2 * N
kl = ku = 2
scaleT = max(float(np.max(np.abs(T))), 1.0)
scaleC = 1e-3

for it in range(1, 7):
    f0 = s.residual(p, dt, R, T, C, U, Ts, 0.0)
    print(f"it{it}: |F|inf={np.max(np.abs(f0)):.3e}  Tsurf={k2c(U[N-1]):.4f} "
          f"Tcore={k2c(U[0]):.4f}")
    ab = np.zeros((kl + ku + 1, n))
    for j in range(n):
        h = 1e-7 * max(abs(U[j]), 1.0)
        Up = U.copy()
        Up[j] += h
        col = (s.residual(p, dt, R, T, C, Up, Ts, 0.0) - f0) / h
        for i in range(max(0, j - kl), min(n, j + ku + 1)):
            ab[ku + i - j, j] = col[i]
    # surface temperature diagonal: row N-1, column N-1
    print(f"   J[N-1,N-1] = {ab[ku + 0, N-1]:.6e}   J[N-1,N-2] = {ab[ku - 1, N-1]:.6e}"
          f"   rhs = {-f0[N-1]:.6e}")
    dU = solve_banded((kl, ku), ab, -f0)
    err = max(float(np.max(np.abs(dU[:N]))) / scaleT,
              float(np.max(np.abs(dU[N:]))) / scaleC)
    print(f"   dTsurf={dU[N-1]:.4f}  err={err:.3e}")
    if err <= 1e-13:
        break
    U = U + dU
    T, C = U[:N], U[N:]
