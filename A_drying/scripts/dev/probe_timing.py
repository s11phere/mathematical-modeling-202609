# -*- coding: utf-8 -*-
"""Timing probe: where does the solver spend its time?"""
import sys
import time
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drying_solver import DryerSolver1D, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402


def main():
    amb = mp.Ambient()
    props = mp.props_problem1(amb)
    props.hm_mode = "prescribed"
    props.wet_bulb = False
    s = DryerSolver1D(N=100, R0=0.02)
    T = np.full(100, c2k(28.0))
    C = np.full(100, 2.55)

    t0 = time.time()
    for k in range(5):
        ta = time.time()
        Tn, Cn, nit, ok = s._step(props, 0.0, 5.0, T, C, 40, 1e-9, 1.0)
        tb = time.time()
        st = s.surface_state(props, Cn, Tn, 0.02, float(props.Camb(0.0)), float(props.Tamb(0.0)))
        tc = time.time()
        print(f"step {k}: _step {tb-ta:.4f}s  surface_state {tc-tb:.4f}s  nit={nit} ok={ok} "
              f"Ts={k2c(Tn[-1]):.4f} Ccell={Cn[-1]:.6f} Cs={st[0]:.6f} jw={st[1]:.4e}",
              flush=True)
        T, C = Tn, Cn
    print(f"total {time.time()-t0:.3f}s")

    # time the wet-bulb / dew-point helpers in isolation
    ta = time.time()
    for _ in range(1000):
        s.wet_bulb_temperature(props, c2k(28.0), 0.01963, 8e-7)
    print(f"wet_bulb_temperature x1000: {time.time()-ta:.3f}s")
    from drying_solver import Y_sat, p_sat_water, dew_point
    ta = time.time()
    for _ in range(1000):
        Y_sat(c2k(28.0))
    print(f"Y_sat x1000: {time.time()-ta:.4f}s")
    ta = time.time()
    for _ in range(1000):
        dew_point(c2k(28.0), 0.01963)
    print(f"dew_point x1000: {time.time()-ta:.3f}s")


if __name__ == "__main__":
    main()
