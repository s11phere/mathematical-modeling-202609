# -*- coding: utf-8 -*-
"""Verify that the spatially integrated water rate equals the surface flux."""
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
T = np.full(N, c2k(28.0))
C = np.full(N, 2.55)
h_r, V, F = s.geometry(0.02)
jw, Cs, Ys, Ts = s.surface_state(p, C, T, 0.02, c2k(28.0), 0.01963)
d = s.rhs(0.0, np.concatenate([T, C]), p, 1.0)

print(f"jw                = {jw:.6e} kg m^-2 s^-1")
print(f"Wet-bulb T        = {k2c(Ts):.4f} C")
print(f"F[-1]             = {F[-1]:.6e} m")
print(f"V[-1]             = {V[-1]:.6e} m^2")
print(f"F[-1]/V[-1]       = {F[-1]/V[-1]:.4f} 1/m")
print()
print(f"code dCdt[-1]     = {d[N + N - 1]:.6e}")
print(f"  -F/V*jw         = {-F[-1]/V[-1]*jw:.6e}")
print()
lhs = float(np.sum(V * d[N:]))
print(f"sum V dC/dt       = {lhs:.6e}  (per unit pi R^2 basis)")
print(f"-F[-1] jw         = {-F[-1]*jw:.6e}")
print(f"ratio             = {lhs/(-F[-1]*jw):.6f}")
print()
# convert to physical water mass per unit length
k = 2.0 * np.pi * 0.02 ** 2 * p.rho_d0
print(f"dW/dt (kg/m/s)    = {k*lhs:.6e}")
print(f"-2 pi R jw        = {-2*np.pi*0.02*jw:.6e}")
print(f"ratio             = {k*lhs/(-2*np.pi*0.02*jw):.6f}")
