# -*- coding: utf-8 -*-
"""Validate final_solver: steady conduction + conservation."""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from final_solver import FinalSolver, Props, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402


def steady():
    R, Ts, T0 = 0.02, 350.0, 300.0
    p = Props(rho=lambda C, T: np.full_like(T, 820.0),
              cp=lambda C, T: np.full_like(T, 2600.0),
              k=lambda C, T: np.full_like(T, 0.36),
              D=lambda C, T: np.full_like(T, 1e-12),
              h=1e8, h_m=0.0, Lw=0.0,
              Tamb=lambda t: Ts, Camb=lambda t: 0.0, rho_d0=1.0, C_sat=1.0)
    print("=== steady conduction, T = Ts + (T0-Ts)(1-(r/R)^2) ===")
    for dt in (100.0, 25.0):
        for N in (20, 40, 80):
            s = FinalSolver(N=N, R0=R)
            r = s.run(p, t_end=20000.0, T_init=T0, C_init=0.0, dt=dt,
                      max_iter=40, tol=1e-13)
            Tn = r.T[-1]
            rr = R * s.grid.xi_c
            ex = Ts + (T0 - Ts) * (1 - (rr / R) ** 2)
            e = float(np.max(np.abs(Tn - ex)))
            print(f"  dt={dt:5.0f} N={N:3d}  max|T-exact|={e:.3e} K   "
                  f"Tsurf={k2c(Tn[-1]):.4f} Tcore={k2c(Tn[0]):.4f}")


def conservation():
    print("\n=== water balance (problem 1, prescribed and lewis) ===")
    amb = mp.Ambient()
    for mode in ("prescribed", "lewis"):
        p = mp.props_problem1(amb)
        p.hm_mode = mode
        s = FinalSolver(N=40, R0=0.02)
        r = s.run(p, t_end=1800.0, T_init=c2k(28.0), C_init=2.55, dt=10.0,
                  max_iter=40, tol=1e-12)
        t = np.array(r.ts)
        W = np.array(r.W)
        jw = np.array(r.jw)
        m = 2 * np.pi * 0.02 * np.trapezoid(jw, t)
        dW = W[0] - W[-1]
        rel = abs(dW - m) / max(abs(dW), 1e-30)
        print(f"  mode={mode:11s} dW={dW:.6e} flux_int={m:.6e} rel={rel:.3e}")
        print(f"    Ts {k2c(r.Tsurf[0]):.4f} -> {k2c(r.Tsurf[-1]):.4f} degC ; "
              f"Tc {k2c(r.Tc[0]):.4f} -> {k2c(r.Tc[-1]):.4f} degC ; "
              f"Cc {r.Cc[0]:.6f} -> {r.Cc[-1]:.6f} ; Cs {r.Csurf[0]:.6f} -> {r.Csurf[-1]:.6f}")


if __name__ == "__main__":
    steady()
    conservation()
