# -*- coding: utf-8 -*-
"""
Decisive instrumentation: log every rhs() flux together with the time at which
it is evaluated, and reconcile the total water loss against the flux integral.
"""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import mol_solver as M  # noqa: E402
from mol_solver import MolSolver, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402

p = mp.props_problem1(mp.Ambient())
p.hm_mode = "heat_limited"
N = 30
s = MolSolver(N=N, R0=0.02)
h_r, V, F = s.geometry(0.02)

orig = M.MolSolver.surface_state
log = []


def logged(self, props, C, T, R, Tamb, Camb):
    out = orig(self, props, C, T, R, Tamb, Camb)
    log.append((float(T[-1]), float(C[-1]), float(out[0]), float(out[1]),
                float(Tamb), float(Camb), float(T[0]), float(C[0])))
    return out


M.MolSolver.surface_state = logged

ts_end = 60.0
r = s.run(p, ts_end, c2k(28.0), 2.55, sample_dt=ts_end, rtol=1e-8, atol=1e-10,
          method="BDF", max_step=5.0)

print(f"surface_state calls: {len(log)}")
jw = np.array([x[2] for x in log])
print(f"jw over calls: min={jw.min():.4e} max={jw.max():.4e} mean={jw.mean():.4e}")
print(f"C_cell over calls: min={min(x[1] for x in log):.4f} "
      f"max={max(x[1] for x in log):.4f}")
print(f"Camb over calls: {sorted(set(round(x[5],6) for x in log))[:5]}")
print()
dW = r.W[0] - r.W[-1]
print(f"actual dW over {ts_end}s = {dW:.6e} kg/m")
print(f"required mean flux       = {dW/(2*np.pi*0.02*ts_end):.6e} kg/m2/s")
print(f"max logged flux          = {jw.max():.6e}")
print(f"ratio required/max       = {dW/(2*np.pi*0.02*ts_end)/jw.max():.1f}")
print()
# With the flux capped at jw_max, the largest possible water loss is
print(f"upper bound on dW if jw <= {jw.max():.3e}: "
      f"{2*np.pi*0.02*jw.max()*ts_end:.6e} kg/m")
print()
print("=> the integrator is NOT using the flux that surface_state returns,")
print("   OR the water diagnostic double counts the surface cell.")
print()
print(f"W0={r.W[0]:.8f}  Wend={r.W[-1]:.8f}")
print(f"sum(V)={np.sum(V):.8e}  pi R^2={np.pi*0.02**2:.8e}")
print(f"V[-1]={V[-1]:.6e}  2*pi*R*h_r={2*np.pi*0.02*h_r:.6e}")
