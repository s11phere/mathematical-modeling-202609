# -*- coding: utf-8 -*-
"""Trace the water budget step by step to locate the conservation gap."""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402

amb = mp.Ambient()
p = mp.props_problem1(amb)
p.hm_mode = "prescribed"
s = MolSolver(N=20, R0=0.02)
r = s.run(p, 300.0, c2k(28.0), 2.55, sample_dt=50.0, rtol=1e-9, atol=1e-12,
          method="Radau", max_step=5.0)

h_r, V, F = s.geometry(0.02)
print("F[N] =", F[-1], " V[-1] =", V[-1], " F/V =", F[-1] / V[-1])
print("cell centres r:", 0.02 * s.xi_c)
print()
print(" t      W            dW          jw(surface_state)   F[-1]*jw/V[-1]"
      "   dC/dt implied")
prevW = r.W[0]
for k, tt in enumerate(r.ts):
    dW = r.W[k] - (r.W[k - 1] if k else r.W[k])
    rate = F[-1] * r.jw[k] / V[-1]
    print(f"{tt:6.0f} {r.W[k]:.9f} {dW:+.3e}   {r.jw[k]:+.4e}        "
          f"{rate:+.4e}      {rate:+.4e}")

print()
print("total dW        =", r.W[0] - r.W[-1])
t = np.array(r.ts)
print("flux integral   =", 2 * np.pi * 0.02 * np.trapezoid(np.array(r.jw), t))
print()
# direct check: what does rhs() actually use in the first cell?
T0 = np.full(20, c2k(28.0))
C0 = np.full(20, 2.55)
y = np.concatenate([T0, C0])
jw, Cs, Ys, Ts = s.surface_state(p, C0, T0, 0.02, c2k(28.0), 0.01963)
print(f"surface_state at t=0: jw={jw:.6e} Cs={Cs:.6f} Ys={Ys:.6f} Ts={k2c(Ts):.4f}C")
d = s.rhs(0.0, y, p, 300.0)
print(f"rhs dC/dt[-1] = {d[20 + 19]:.6e} kg/kg/s")
print(f"   expected -F/V * jw = {-F[-1] / V[-1] * jw:.6e}")
