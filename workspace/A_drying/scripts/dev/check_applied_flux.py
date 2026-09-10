# -*- coding: utf-8 -*-
"""
Measure the surface flux that the integrator actually applies.

The right-hand side is evaluated at the exact state passed in, so calling
``rhs`` at consecutive stored states gives the flux the model used, independent
of how ``Series.jw`` is post-processed.
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
N = 50
s = MolSolver(N=N, R0=0.02)
h_r, V, F = s.geometry(0.02)
prop_area = 2.0 * np.pi * 0.02

# --- fixed-step explicit-ish march using the model's own rhs ---------------
T = np.full(N, c2k(28.0))
C = np.full(N, 2.55)
dt = 1.0
print("  t      dW/dt (model)   -2piR jw(model)   Csurf    Cc")
for step in range(1, 21):
    y = np.concatenate([T, C])
    d = s.rhs(0.0, y, p, 1.0)
    Wrate = float(np.sum(V * d[N:])) * 2.0 * np.pi * 0.02 ** 2 * p.rho_d0
    jw, Cs, Ys, Ts = s.surface_state(p, C, T, 0.02, c2k(28.0), p.Camb(0.0))
    print(f"{step*dt:6.0f}  {Wrate:+.6e}     {-prop_area*jw:+.6e}    "
          f"{Cs:.6f}  {C[-1]:.6f}")
    # forward Euler with a small step, purely to expose the applied flux
    T = T + dt * d[:N]
    C = C + dt * d[N:]

print()
print("note: -2piR*jw(model) is the flux converted to kg/m/s; the two columns")
print("      must agree if Series.jw is consistent with what rhs applies.")
