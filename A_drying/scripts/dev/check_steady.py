# -*- coding: utf-8 -*-
"""Steady-state check of final_solver in a single very large backward-Euler step."""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from final_solver import FinalSolver, Props, c2k, k2c  # noqa: E402

R, Ts, T0 = 0.02, 350.0, 300.0
p = Props(rho=lambda C, T: np.full_like(T, 820.0),
          cp=lambda C, T: np.full_like(T, 2600.0),
          k=lambda C, T: np.full_like(T, 0.36),
          D=lambda C, T: np.full_like(T, 1e-12),
          h=1e8, h_m=0.0, Lw=0.0,
          Tamb=lambda t: Ts, Camb=lambda t: 0.0, rho_d0=1.0, C_sat=1.0)

for N in (10, 20, 40):
    s = FinalSolver(N=N, R0=R)
    T = np.full(N, T0)
    C = np.full(N, 0.0)
    Tn, Cn, nit, ok, rs = s.step(p, 0.0, 1.0e6, T, C, Ts, 0.0, max_iter=40, tol=1e-13)
    rr = R * s.grid.xi_c
    ex = Ts + (T0 - Ts) * (1 - (rr / R) ** 2)
    print(f"N={N:3d} ok={ok} it={nit} res={rs:.2e}  "
          f"max|T-exact|={np.max(np.abs(Tn - ex)):.3e} K  "
          f"Tsurf={k2c(Tn[-1]):.4f} Tcore={k2c(Tn[0]):.4f}")

# print the surface row of the residual for a hand check
N = 10
s = FinalSolver(N=N, R0=R)
T = np.full(N, T0)
C = np.full(N, 0.0)
U = np.concatenate([T, C])
F = s.residual(p, 1.0e6, R, T, C, U, Ts, 0.0)
print("residual (T rows):", np.array2string(F[:N], precision=3))
print("residual (C rows):", np.array2string(F[N:], precision=3))
gr = s.grid
print("Vw:", np.array2string(gr.Vw, precision=4))
print("Fa:", np.array2string(gr.Fa, precision=4))
print(f"surface row: -Fa[N]*q_in = -{gr.Fa[N]}*{p.h * (Ts - T[-1]):.6e} = {-gr.Fa[N] * p.h * (Ts - T[-1]):.6e}")
