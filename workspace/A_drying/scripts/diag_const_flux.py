# -*- coding: utf-8 -*-
"""
Controlled experiment: replace surface_state by a constant known flux and check
that the integrated water loss equals 2 pi R j_w t.  This isolates whether the
water diagnostic or the boundary term is at fault.
"""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import mol_solver as M  # noqa: E402
from mol_solver import MolSolver, c2k  # noqa: E402
import model_problems as mp  # noqa: E402

N = 30
R = 0.02
JW = 1.0e-5          # imposed constant flux, kg m^-2 s^-1
T_END = 10.0

p = mp.props_problem1(mp.Ambient())
p.hm_mode = "prescribed"

s = MolSolver(N=N, R0=R)
h_r, V, F = s.geometry(R)


def const_flux(self, props, C, T, Rt, Tamb, Camb):
    return JW, float(C[-1]), 0.0, float(T[-1])


M.MolSolver.surface_state = const_flux
r = s.run(p, T_END, c2k(28.0), 2.55, sample_dt=T_END, rtol=1e-9, atol=1e-11,
          method="BDF", max_step=1.0)

dW = r.W[0] - r.W[-1]
expected = 2 * np.pi * R * JW * T_END
print(f"imposed flux j_w       = {JW:.4e} kg m^-2 s^-1")
print(f"duration               = {T_END} s")
print(f"expected water loss    = 2 pi R j_w t = {expected:.8e} kg/m")
print(f"measured water loss    = {dW:.8e} kg/m")
print(f"ratio measured/expect  = {dW/expected:.6f}")
print()
print(f"W0 = {r.W[0]:.8f}   Wend = {r.W[-1]:.8f}")
print()
# now check the per-step relation directly from the residual
M.MolSolver.surface_state = const_flux
T = np.full(N, c2k(28.0))
C = np.full(N, 2.55)
d = s.rhs(0.0, np.concatenate([T, C]), p, 1.0)
lhs = float(np.dot(V, d[N:]))
print(f"from rhs:  sum V dC/dt = {lhs:+.8e}")
print(f"           -F_N j_w    = {-F[-1]*JW:+.8e}")
print(f"           rel err     = {abs(lhs + F[-1]*JW)/abs(F[-1]*JW):.3e}")
