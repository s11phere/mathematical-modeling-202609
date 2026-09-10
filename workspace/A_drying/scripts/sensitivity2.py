# -*- coding: utf-8 -*-
"""
Sensitivity analysis for the A-problem (heat-supply-limited closure).

Varies the assumptions that most affect the answer to problems 3 and 4:

* the film mass-transfer closure (prescribed h_m vs the heat-supply limit)
* the convective heat transfer coefficient h  (25 -> 15 / 40 W m^-2 K^-1)
* the chamber extrapolation beyond the 4 h of 附件1
* the phase-switch time between 附录2 and 附录3 properties

Reports the time for every point to fall below C = 0.15 kg/kg.

Run: python scripts/sensitivity2.py [--N 60] [--days 20]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402

OUT = ROOT / "out"
T_PHASE = 1800.0


class AmbRamp(mp.Ambient):
    """Chamber continues warming after the measured window."""

    def __init__(self, rate_K_per_h=0.4, tmax_C=55.0):
        super().__init__()
        self.rate = rate_K_per_h / 3600.0
        self.tmax = tmax_C

    def Tamb(self, t):
        base = super().Tamb(t)
        t = np.asarray(t, float)
        extra = np.clip(self.rate * np.maximum(t - 14400.0, 0.0), 0.0,
                        self.tmax - 50.2)
        return base + extra

    def Camb(self, t):
        # humidity held at the measured final value
        return super().Camb(t)


def run_case(N, hm_mode, h=None, amb=None, phase=T_PHASE, days=20.0,
             label="", hm_scale=None):
    amb = amb if amb is not None else mp.Ambient()
    pa = mp.props_problem1(amb)
    pa.hm_mode = hm_mode
    if h is not None:
        pa.h = h
    if hm_scale is not None:
        pa.hm_scale = hm_scale
    sa = MolSolver(N=N, R0=mp.R0)
    t0 = time.time()
    ra = sa.run(pa, phase, c2k(mp.T_INIT_C), mp.C_INIT, t_start=0.0,
                sample_dt=300.0, rtol=1e-7, atol=1e-9, method="BDF",
                max_step=600.0)
    pb = mp.props_appendix3(amb)
    pb.hm_mode = hm_mode
    if h is not None:
        pb.h = h
    if hm_scale is not None:
        pb.hm_scale = hm_scale
    sb = MolSolver(N=N, R0=mp.R0)
    rb = sb.run(pb, days * 24 * 3600.0, ra.T[-1], ra.C[-1], t_start=phase,
                sample_dt=1800.0, rtol=1e-6, atol=1e-8, method="BDF",
                max_step=1800.0)
    ts = np.concatenate([ra.ts, rb.ts[1:]])
    Cc = np.concatenate([ra.Cc, rb.Cc[1:]])
    Cs = np.concatenate([ra.Csurf, rb.Csurf[1:]])
    Cmax = np.maximum(Cc, Cs)
    hit = np.where(Cmax < mp.C_TARGET)[0]
    return dict(label=label, hm_mode=hm_mode, h=h, phase_s=phase,
                t_end_h=float(ts[hit[0]] / 3600.0) if hit.size else None,
                Cmax_end=float(Cmax[-1]),
                Ccore_end=float(Cc[-1]), Csurf_end=float(Cs[-1]),
                wall=time.time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=60)
    ap.add_argument("--days", type=float, default=20.0)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    N = args.N

    cases = [
        ("baseline (heat-limited, h=25)", dict(hm_mode="heat_limited")),
        ("prescribed h_m = 8e-7", dict(hm_mode="prescribed")),
        ("h = 15 W/m2K", dict(hm_mode="heat_limited", h=15.0)),
        ("h = 40 W/m2K", dict(hm_mode="heat_limited", h=40.0)),
        ("chamber keeps warming", dict(hm_mode="heat_limited",
                                       amb=AmbRamp())),
        ("phase switch at 1200 s", dict(hm_mode="heat_limited", phase=1200.0)),
        ("phase switch at 2400 s", dict(hm_mode="heat_limited", phase=2400.0)),
    ]
    rows = []
    for label, kw in cases:
        r = run_case(N, days=args.days, label=label, **kw)
        rows.append(r)
        t = f"{r['t_end_h']:.1f} h" if r["t_end_h"] else "never"
        print(f"{label:34s} t_end={t:>9s}  Cmax_end={r['Cmax_end']:.4f}  "
              f"({r['wall']:.1f}s)", flush=True)
    (OUT / "sensitivity2.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nwrote", OUT / "sensitivity2.json")


if __name__ == "__main__":
    main()
