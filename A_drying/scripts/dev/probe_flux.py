# -*- coding: utf-8 -*-
"""Trace the surface flux fixed-point iteration."""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drying_solver import c2k, k2c, Y_sat  # noqa: E402
from robust_solver import RobustSolver  # noqa: E402
import model_problems as mp  # noqa: E402

amb = mp.Ambient()
props = mp.props_problem1(amb)
props.hm_mode = "lewis"
s = RobustSolver(N=40, R0=0.02)
N = 40
R = 0.02
h_r = R / (2 * N)
C = np.full(N, 2.55)
T = np.full(N, c2k(28.0))
Camb, Tamb = 0.01963, c2k(28.0)
hm = s.hm_eff(props)
Ds = float(np.asarray(props.D(C[-1:], T[-1:]), float)[0])
ks = float(np.asarray(props.k(C[-1:], T[-1:]), float)[0])
print(f"hm={hm:.4e} Ds={Ds:.4e} ks={ks:.4f} h_r={h_r:.3e} h={props.h} Lw={props.Lw}")
print(f"Ccell={C[-1]} Tcell={T[-1]-273.15:.4f}C Yinf={Camb} Ysat(Tcell)={float(Y_sat(T[-1])):.6f}")
print(f"Ds*Ccell/h_r = {Ds*C[-1]/h_r:.6e}   hm*Yinf = {hm*Camb:.6e}")

beta = float(props.h)
Cs, Ts, jw = props.C_sat, Tamb, 0.0
for it in range(12):
    g = h_r / ks
    Ts_new = (Tamb * beta + T[-1] / g - props.Lw * jw) / (beta + 1.0 / g)
    Ts_new = min(max(Ts_new, 200.0), max(Tamb, 200.001))
    Ys_ = float(Y_sat(Ts_new))
    cs_eq = (Ds * C[-1] / h_r - hm * Camb) / (Ds / h_r + hm * Ys_)
    if cs_eq >= props.C_sat:
        lo, hi = 0.0, props.C_sat
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            f_mid = (Ds * (C[-1] - mid) / h_r
                     - hm * ((mid / props.C_sat) * Ys_ - Camb))
            if f_mid > 0.0:
                lo = mid
            else:
                hi = mid
        Cs_new = 0.5 * (lo + hi)
        tag = "bisect"
    else:
        Cs_new = min(max(cs_eq, 0.0), props.C_sat)
        tag = "closed"
    phi = Cs_new / props.C_sat
    Ys_new = phi * Ys_
    jw_new = hm * (Ys_new - Camb)
    print(f"it{it}: Ts={k2c(Ts_new):.5f}C Ysat={Ys_:.6f} cs_eq={cs_eq:.6f} "
          f"[{tag}] Cs={Cs_new:.6f} phi={phi:.6f} Ys={Ys_new:.6f} jw={jw_new:.4e}")
    Cs, Ts, Ys, jw = Cs_new, Ts_new, Ys_new, jw_new
