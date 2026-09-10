# -*- coding: utf-8 -*-
"""Count _step calls and iterations for the first few steps of problem 1."""
import sys
import time
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import drying_solver as ds  # noqa: E402
from drying_solver import DryerSolver1D, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402

calls = {"n": 0, "iters": 0}
orig_step = DryerSolver1D._step


def counting_step(self, *a, **k):
    calls["n"] += 1
    out = orig_step(self, *a, **k)
    calls["iters"] += out[2]
    return out


DryerSolver1D._step = counting_step


def main():
    amb = mp.Ambient()
    props = mp.props_problem1(amb)
    props.hm_mode = "prescribed"
    props.wet_bulb = True
    s = DryerSolver1D(N=100, R0=0.02)
    T = np.full(100, c2k(28.0))
    C = np.full(100, 2.55)
    t = 0.0
    ta = time.time()
    for k in range(6):
        calls["n"] = calls["iters"] = 0
        Tn, Cn, nit, ok = s._step(props, t, 5.0, T, C, 40, 1e-9, 1.0)
        st = s.surface_state(props, Cn, Tn, 0.02, float(props.Camb(t)), float(props.Tamb(t)))
        print(f"k={k} t={t:.1f} nit={nit} ok={ok} calls={calls['n']} "
              f"Ts={k2c(Tn[-1]):.4f} Ccell={Cn[-1]:.6f} Cs={st[0]:.6f} jw={st[1]:.4e} "
              f"dC={np.max(np.abs(Cn-C)):.3e}", flush=True)
        T, C = Tn, Cn
        t += 5.0
        if time.time() - ta > 30:
            print("aborting probe: too slow", flush=True)
            break


if __name__ == "__main__":
    main()
