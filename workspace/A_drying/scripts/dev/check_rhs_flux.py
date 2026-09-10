# -*- coding: utf-8 -*-
"""Compare surface_state with what rhs() actually uses, state for state."""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402

p = mp.props_appendix3(mp.Ambient())
p.hm_mode = "heat_limited"
N = 60
s = MolSolver(N=N, R0=0.02)
R = 0.02
h_r, V, F = s.geometry(R)
T = np.full(N, c2k(50.0))
C = np.full(N, 2.55)
y = np.concatenate([T, C])

jw, Cs, Ys, Ts = s.surface_state(p, C, T, R, c2k(50.0), 0.05)
print(f"surface_state: jw={jw:.8e} Cs={Cs:.6f}")
d = s.rhs(0.0, y, p, 1.0)
implied = -d[2 * N - 1] * V[N - 1] / F[N]
print(f"rhs dCdt[-1]  = {d[2*N-1]:.8e}")
print(f"implied jw    = {implied:.8e}")
print(f"ratio implied/jw = {implied/jw:.6f}")
print()
# recompute surface_state step by step to see which branch runs
hm = s.hm_film(p)
Ds = float(np.asarray(p.D(C[-1:], T[-1:]), float)[0])
gD = Ds / (0.5 * h_r)
Twb = s.wet_bulb_temperature(p, c2k(50.0), 0.05)
jw_wet = p.h * (50.0 - k2c(Twb)) / p.Lw
denom = gD * p.C_sat + jw_wet
x = min(1.0, gD * C[-1] / denom)
print(f"gD={gD:.6e}  jw_wet={jw_wet:.6e}  denom={denom:.6e}")
print(f"x={x:.8f}  Cs={x*p.C_sat:.6f}  gD*(Ccell-Cs)={gD*(C[-1]-x*p.C_sat):.6e}")
print(f"jw_wet*x={jw_wet*x:.6e}")
print()
print(f"cell volume V[N-1]={V[N-1]:.6e}  face F[N]={F[N]:.6e}")
print(f"expected dCdt = -F[N]*jw/V[N-1] = {-F[N]*jw/V[N-1]:.6e}")
