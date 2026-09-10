# -*- coding: utf-8 -*-
"""
Exact discrete water-budget check.

The discrete conservation law is

    d/dt sum_i V_i C_i = -F_N j_w

so a *single* explicit backward-Euler step must satisfy

    sum_i V_i (C_i^new - C_i^old) = -dt F_N j_w + (numerical) O(dt^2),

and, more sharply, integrating the model's own right-hand side

    sum_i V_i dC_i/dt = -F_N j_w        (exactly, by construction)

must hold to machine precision.  This tests the discrete operator rather than a
post-processed diagnostic, which is what the earlier V3 was really measuring.
"""
import sys
from pathlib import Path

import numpy as np

np.seterr(all="ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402

FAIL = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


amb = mp.Ambient()
for mode in ("prescribed", "lewis"):
    p = mp.props_problem1(amb)
    p.hm_mode = mode
    for N in (20, 50):
        s = MolSolver(N=N, R0=0.02)
        R = 0.02
        h_r, V, F = s.geometry(R)
        # an arbitrary but non-trivial state
        rng = np.random.default_rng(0)
        T = c2k(28.0) + 3.0 * rng.random(N)
        C = 2.55 * (1.0 - 0.05 * rng.random(N))
        y = np.concatenate([T, C])
        d = s.rhs(0.0, y, p, 1.0)
        lhs = float(np.sum(V * d[N:]))
        jw, Cs, Ys, Ts = s.surface_state(p, C, T, R, float(p.Tamb(0.0)),
                                         float(p.Camb(0.0)))
        rhs = -F[-1] * jw
        rel = abs(lhs - rhs) / max(abs(rhs), 1e-30)
        print(f"  mode={mode:11s} N={N:3d}  sum(V dC/dt)={lhs:+.6e}  "
              f"-F_N jw={rhs:+.6e}  rel={rel:.3e}")
        check(f"exact discrete water balance {mode} N={N}", rel < 1e-10, f"{rel:.2e}")

print()
print("=== same check for the energy equation (conduction + film) ===")
p = mp.props_problem1(amb)
for N in (20, 50):
    s = MolSolver(N=N, R0=0.02)
    R = 0.02
    h_r, V, F = s.geometry(R)
    rng = np.random.default_rng(1)
    T = c2k(28.0) + 3.0 * rng.random(N)
    C = 2.55 * (1.0 - 0.05 * rng.random(N))
    y = np.concatenate([T, C])
    d = s.rhs(0.0, y, p, 1.0)
    rcp = np.asarray(p.rho(C, T) * p.cp(C, T), float)
    lhs = float(np.sum(V * rcp * d[:N]))
    jw, Cs, Ys, Ts = s.surface_state(p, C, T, R, float(p.Tamb(0.0)),
                                     float(p.Camb(0.0)))
    q_in = p.h * (float(p.Tamb(0.0)) - T[-1]) - p.Lw * jw
    rhs = F[-1] * q_in
    rel = abs(lhs - rhs) / max(abs(rhs), 1e-30)
    print(f"  N={N:3d}  sum(V rho cp dT/dt)={lhs:+.6e}  F_N q_in={rhs:+.6e}  rel={rel:.3e}")
    check(f"exact discrete energy balance N={N}", rel < 1e-10, f"{rel:.2e}")

print()
print("FAILURES: " + ", ".join(FAIL) if FAIL else "ALL CHECKS PASSED")
