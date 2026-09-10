# -*- coding: utf-8 -*-
"""
Check the discrete water-conservation identity on a single forward-Euler step.

The exact statement of the scheme is

    sum_i V_i (C_i(t+dt) - C_i(t)) = -dt F_N j_w + O(dt^2),

where V_i, F_N are the *physical* volumes and areas from ``geometry(R)`` and
``j_w`` is the flux the right-hand side reports.  Any mismatch is a coding error
rather than a modelling choice.
"""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402

p = mp.props_problem1(mp.Ambient())
p.hm_mode = "heat_limited"
N = 60
R = 0.02
s = MolSolver(N=N, R0=R)
h_r, V, F = s.geometry(R)
print(f"sum V = {np.sum(V):.8e}   pi R^2 = {np.pi*R*R:.8e}")
print(f"F[-1] = {F[-1]:.8e}   2 pi R = {2*np.pi*R:.8e}")

Tamb = c2k(28.0)
Camb = 0.01963
T = np.full(N, Tamb)
C = np.full(N, 2.55)

jw, Cs, Ys, Ts = s.surface_state(p, C, T, R, Tamb, Camb)
print(f"\nsurface_state: jw={jw:.8e}  Cs={Cs:.6f}")

# exact identity from the residual
d = s.rhs(0.0, np.concatenate([T, C]), p, 1.0)
lhs = float(np.dot(V, d[N:]))
rhs = -F[-1] * jw
print(f"sum_i V_i dC_i/dt = {lhs:+.8e}")
print(f"-F_N j_w          = {rhs:+.8e}")
print(f"relative mismatch = {abs(lhs-rhs)/abs(rhs):.3e}")

# now a finite backward-Euler step and compare with dt * (-F jw)
for dt in (1.0, 10.0):
    d = s.rhs(0.0, np.concatenate([T, C]), p, 1.0)
    Cnew = C + dt * d[N:]
    dW = float(np.dot(V, Cnew - C))
    print(f"\ndt={dt:5.1f}s  sum V dC = {dW:+.8e}   -dt F jw = {-dt*F[-1]*jw:+.8e}"
          f"   ratio = {dW/(-dt*F[-1]*jw):.6f}")
