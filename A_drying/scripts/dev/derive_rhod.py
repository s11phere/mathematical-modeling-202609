# -*- coding: utf-8 -*-
"""
Establish the correct rho_d bookkeeping for the dry-basis moisture equation.

Definition.  C is the dry-basis moisture content, m_w/m_d.  The water mass per
unit volume is rho_w = rho_d C, where rho_d = m_d/V is the dry-solid apparent
density.  Fick's law gives the water flux

    J = D grad(rho_w) = D grad(rho_d C) = rho_d D grad C      [kg m^-2 s^-1]

so the physical flux necessarily carries rho_d.  The mass balance is

    d/dt int rho_d C dV = -oint J . n dA

For a fixed mesh and constant rho_d in time this reads

    rho_d V_i dC_i/dt = F_{i-1} J_{i-1} - F_i J_i

so BOTH sides carry rho_d, and dividing through by rho_d gives the equation in
terms of J (physical):

    V_i dC_i/dt = F_{i-1} (J/rho_d)_{i-1} - F_i (J/rho_d)_i

Consequently the code must use ONE of two equivalent conventions:

  (a) J physical in the fluxes, and dC/dt = F J /(rho_d V)   [rho_d explicit]
  (b) J_dry = D dC/dr in the fluxes, and dC/dt = F J_dry / V [no rho_d]

and the water inventory diagnostic must be

    W = int rho_d C dV = 2 pi R0^2 rho_d0 * int C d(xi^2)/2

Mixing conventions produces a factor rho_d error, which is what we observe
(rho_d = 230.99 for problem 1).
"""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, c2k  # noqa: E402
import model_problems as mp  # noqa: E402

N = 10
R = 0.02
JW = 1.0e-5
T_END = 10.0

p = mp.props_problem1(mp.Ambient())
p.hm_mode = "prescribed"
s = MolSolver(N=N, R0=R)
h_r, V, F = s.geometry(R)
rd = p.rho_d0
print(f"rho_d0 = {rd:.6f}")
print(f"sum V = {np.sum(V):.8e},  pi R^2 = {np.pi*R*R:.8e}")
print()

# --- convention (a): physical flux J in the boundary term -------------------
print("convention (a): dCdt = F J / (rho_d V)")
lhs = -F[-1] * JW / V[-1]
print(f"   dCdt[N-1] = {lhs:.8e} 1/s")
print(f"   water rate = rho_d * V[-1] * dCdt = {rd*V[-1]*lhs:.8e} kg/m/s")
print(f"   physical   = -F[-1] * JW          = {-F[-1]*JW:.8e} kg/m/s")
print()
# --- convention (b): dry flux in the boundary term --------------------------
print("convention (b): dCdt = F J / V, with J = D dC/dr (dry-basis flux)")
lhs_b = -F[-1] * JW / V[-1]
print(f"   dCdt[N-1] = {lhs_b:.8e} 1/s")
print(f"   water rate = rho_d * V[-1] * dCdt = {rd*V[-1]*lhs_b:.8e} kg/m/s")
print(f"   physical   = -F[-1] * (rho_d*JW)   = {-F[-1]*rd*JW:.8e} kg/m/s")
print()
print("=> interp of the two: the pair (flux convention, W formula) must match.")
print(f"   W formula used now multiplies by rho_d0, i.e. it assumes (a).")
print(f"   The boundary term currently uses (b).  Hence the factor rho_d = {rd:.3f}.")
print()
print("FIX: use (a) everywhere, i.e. multiply the interior water flux and the")
print("     surface flux by rho_d; keep W = 2 pi R0^2 rho_d0 int C d(xi^2)/2.")
