# -*- coding: utf-8 -*-
"""Dump the temperature-system coefficients for the last node."""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drying_solver import DryerSolver1D, c2k, k2c, thomas  # noqa: E402
import model_problems as mp  # noqa: E402

amb = mp.Ambient()
props = mp.props_problem1(amb)
props.hm_mode = "lewis"
props.wet_bulb = True
s = DryerSolver1D(N=100, R0=0.02)
N = s.N
h = 5.0
h_r = 0.02 / (2 * N)
inv_h = 1.0 / h_r
T = np.full(N, c2k(28.0))
C = np.full(N, 2.55)
Tamb = float(props.Tamb(0.0))
Camb = float(props.Camb(0.0))

st = s.surface_state(props, C, T, 0.02, Camb, Tamb)
print("surface_state:", st)
Cs0, jw0, Ys0, dCs0, djw_dT0 = st
print(f"jw0={jw0:.6e}  djw_dT0={djw_dT0:.6e}  Lw*djw_dT={props.Lw*djw_dT0:.6e}")

k_c = np.full(N, 0.36)
rcp_c = np.full(N, 820.0 * 2600.0)
Tn = s._solve_T(props, h, T, C, k_c, rcp_c, props.rho_d0, 0.02, h_r, Tamb, Camb,
                jw0, djw_dT0)
print("T surface after solve:", k2c(Tn[-1]), "K:", Tn[-1])

# manual assembly with the same logic
diag = rcp_c / h
rhs = rcp_c / h * T
lower = np.zeros(N)
upper = np.zeros(N)
kf = 2 * k_c[:-1] * k_c[1:] / (k_c[:-1] + k_c[1:])
for i in range(N - 1):
    f = s.a[i + 1] * kf[i] * inv_h
    diag[i] += f
    upper[i] -= f
    diag[i + 1] += f
    lower[i + 1] -= f
k_g = k_c[-1]
fN = s.a[N] * k_g * inv_h
beta = props.h
src = props.h * Tamb
beta_eff = beta + props.Lw * djw_dT0
qsurf = src - props.Lw * jw0
diag[N - 1] += fN * (1.0 + h_r * beta_eff / k_g) + beta_eff
upper[N - 1] = 0.0
rhs[N - 1] += fN * (h_r * qsurf / k_g) + qsurf
print(f"fN={fN:.6e} beta_eff={beta_eff:.6e} qsurf={qsurf:.6e}")
print(f"diag[-1]={diag[-1]:.6e} lower[-1]={lower[-1]:.6e} rhs[-1]={rhs[-1]:.6e}")
print("manual surface T:", k2c(thomas(lower, diag, upper, rhs)[-1]))
