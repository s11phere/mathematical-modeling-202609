# -*- coding: utf-8 -*-
"""Operator checks: consistency, conservativeness, and h-refinement."""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, Props  # noqa: E402

Q0 = 1.0e5
K = 0.36
H = 25.0
TINF = 350.0
R = 0.02
RHO, CP = 820.0, 2600.0

props = Props(rho=lambda C, T: np.full_like(T, RHO),
              cp=lambda C, T: np.full_like(T, CP),
              k=lambda C, T: np.full_like(T, K),
              D=lambda C, T: np.full_like(T, 1e-12),
              h=H, h_m=0.0, Lw=0.0,
              Tamb=lambda t: TINF, Camb=lambda t: 0.0, rho_d0=1.0, C_sat=1.0)

print("=== check 1: a uniform field has zero interior rate (consistency) ===")
for N in (10, 40):
    s = MolSolver(N=N, R0=R)
    y = np.concatenate([np.full(N, 400.0), np.zeros(N)])
    d = s.rhs(0.0, y, props, 1.0)
    print(f"  N={N:3d}  max|dTdt| = {np.max(np.abs(d[:N])):.3e} "
          f"(surface film: T_inf={TINF}, T=400 -> nonzero at the last cell only)")

print("\n=== check 2: the diffusion operator is conservative ===")
# With Qsrc = 0, the volume-weighted sum of the interior rates must equal the
# boundary film flux (per unit pi R^2), i.e. the operator telescopes exactly.
for N in (10, 40):
    s = MolSolver(N=N, R0=R)
    T = 300.0 + 100.0 * (R * s.xi_c / R) ** 2
    y = np.concatenate([T, np.zeros(N)])
    d = s.rhs(0.0, y, props, 1.0)
    lhs = float(np.dot(s.Vw, d[:N] * RHO * CP))
    # boundary film flux per unit pi R^2 (h_m = 0 so no latent term)
    q_film = s.Fa[N] * H * (TINF - T[-1])
    print(f"  N={N:3d}  sum(Vw*rho cp*dTdt)={lhs:+.6e}   "
          f"film flux={q_film:+.6e}   diff={lhs-q_film:+.3e}")

print("\n=== check 3: steady state with a volumetric source, h-refinement ===")
exact_drop = Q0 * R ** 2 / (4 * K)
print(f"  exact centre-to-surface drop = {exact_drop:.6f} K")
for N in (10, 20, 40, 80, 160):
    s = MolSolver(N=N, R0=R)
    r = s.run(props, 1.0e7, TINF, 0.0, sample_dt=None, rtol=1e-11, atol=1e-13,
              method="Radau", max_step=1e7, Qsrc=Q0)
    T = r.T[-1]
    drop = float(T[0] - T[-1])
    print(f"  N={N:4d}  drop={drop:12.4f} K   ratio to exact={drop/exact_drop:9.4f}")
