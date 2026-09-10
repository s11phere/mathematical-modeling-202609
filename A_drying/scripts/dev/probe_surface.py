# -*- coding: utf-8 -*-
"""Single-step diagnostic with full surface-state reporting."""
import sys
import time
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drying_solver import DryerSolver1D, c2k, k2c, Y_sat, dYsat_dT  # noqa: E402
import model_problems as mp  # noqa: E402


def report(props, s, T, C, Tamb, Camb, tag):
    st = s.surface_state(props, C, T, 0.02, Camb, Tamb)
    hm = s.hm_eff(props, Camb)
    print(f"  [{tag}] hm_eff={hm:.4e} Ysat_surf={float(Y_sat(T[-1])):.5f} "
          f"Ysat_amb={float(Y_sat(Tamb)):.5f} Yinf={Camb:.5f}")
    print(f"  [{tag}] Cs={st[0]:.6f} jw={st[1]:.4e} Ys={st[2]:.5f} "
          f"dCs={st[3]:.4e} djw/dT={st[4]:.4e}  Lw*jw={2.26e6*st[1]:.2f} W/m2")
    Twb = s.wet_bulb_temperature(props, Tamb, Camb, hm)
    print(f"  [{tag}] T_wb={k2c(Twb):.4f} C  Ysat(Twb)={float(Y_sat(Twb)):.5f}  "
          f"h*(Tinf-Twb)/Lw={props.h*(Tamb-Twb)/2.26e6:.4e}")


def main():
    amb = mp.Ambient()
    props = mp.props_problem1(amb)
    print("mode:", props.hm_mode, "wet_bulb:", props.wet_bulb)
    s = DryerSolver1D(N=100, R0=0.02)
    T = np.full(100, c2k(28.0))
    C = np.full(100, 2.55)
    Tamb, Camb = float(props.Tamb(0.0)), float(props.Camb(0.0))
    report(props, s, T, C, Tamb, Camb, "t=0")

    Cs0, jw0, Ys0, dCs0, djw0 = s.surface_state(props, C, T, 0.02, Camb, Tamb)
    print(f"  _step will use jw0={jw0:.6e}, djw_dT0={djw0:.6e}")
    Tn, Cn, nit, ok = s._step(props, 0.0, 5.0, T, C, 40, 1e-9, 1.0)
    print(f"  after _step: nit={nit} ok={ok}  Ts={k2c(Tn[-1]):.4f} C  Tc={k2c(Tn[0]):.4f} C")
    report(props, s, Tn, Cn, Tamb, Camb, "t=5")


if __name__ == "__main__":
    main()
