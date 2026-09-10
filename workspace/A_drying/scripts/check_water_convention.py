# -*- coding: utf-8 -*-
"""
Verify the discrete water convention that the code actually implements, at the
SAME ambient conditions rhs uses.

The scheme is   V_i dC_i/dt = (F_{i-1} q_{i-1} - F_i q_i) / rho_d ,
so the integrated identity is

    rho_d * sum_i V_i dC_i/dt = -F_N j_w .
"""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver  # noqa: E402
import model_problems as mp  # noqa: E402

p = mp.props_appendix3(mp.Ambient())
p.hm_mode = "heat_limited"
N = 60
R = 0.02
s = MolSolver(N=N, R0=R)
h_r, V, F = s.geometry(R)
rd = p.rho_d0

# freeze the boundary exactly as rhs does when called at t=0 with t_end=1
Tamb = float(p.Tamb(0.0))
Camb = float(p.Camb(0.0))
print(f"Tamb={Tamb:.4f} K  Camb={Camb:.6f}  rho_d0={rd:.4f}")

for Cval in (2.55, 1.5, 0.5, 0.15):
    T = np.full(N, Tamb)
    C = np.full(N, Cval)
    d = s.rhs(0.0, np.concatenate([T, C]), p, 1.0)
    jw, Cs, Ys, Ts = s.surface_state(p, C, T, R, Tamb, Camb)
    lhs_int = float(np.dot(V, d[N:]))          # sum V dC/dt
    rhs_int = -F[-1] * jw / rd                 # identity above
    print(f"C={Cval:5.2f}  Cs={Cs:.5f}  jw={jw:.4e}  "
          f"sumVdC={lhs_int:+.6e}  -F jw/rd={rhs_int:+.6e}  "
          f"rel={abs(lhs_int-rhs_int)/max(abs(rhs_int),1e-30):.2e}")

print()
print("water inventory check: W = rho_d0 * sum_i V_i C_i")
W = rd * float(np.dot(V, np.full(N, 2.55)))
print(f"  W(2.55) = {W:.6f} kg/m")
