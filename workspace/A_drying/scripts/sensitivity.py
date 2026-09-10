# -*- coding: utf-8 -*-
"""
Sensitivity study for problem 3: how long does drying to C = 0.15 take, and how
sensitive is that answer to the modelling choices?

Cases
-----
* ``prescribed``    appendix h_m (8e-7 m/s) with the humidity-ratio film --
                    the literal reading of 附录2.  Reaches an equilibrium
                    moisture and never attains C = 0.15.
* ``heat_limited``  evaporation limited by the convective heat supply,
                    j_w = h (T_inf - T_wb)/L_w.  This is the classical hot-air
                    drying closure and the one consistent with the 2-3 day
                    process duration implied by 附件2.
* ``scaled:k``      h_m multiplied by k, to bracket the two above.

Also varies the chamber extrapolation and the phase-switch time.

Run: python scripts/sensitivity.py
"""
from __future__ import annotations

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
N = 80


def run_case(mode, days=40.0, phase_switch=1800.0, amb_mode="hold",
             hm_scale=None, label=""):
    amb = mp.Ambient(mode=amb_mode)
    pa = mp.props_problem1(amb)
    pa.hm_mode = mode
    if mode == "scaled":
        pa.hm_scale = hm_scale
    sa = MolSolver(N=N, R0=mp.R0)
    ra = sa.run(pa, phase_switch, c2k(mp.T_INIT_C), mp.C_INIT, t_start=0.0,
                sample_dt=300.0, rtol=1e-7, atol=1e-9, method="BDF",
                max_step=300.0)
    pb = mp.props_appendix3(amb)
    pb.hm_mode = mode
    if mode == "scaled":
        pb.hm_scale = hm_scale
    sb = MolSolver(N=N, R0=mp.R0)
    t0 = time.time()
    tcap = days * 24 * 3600.0
    rb = sb.run(pb, tcap, ra.T[-1], ra.C[-1], t_start=phase_switch,
                sample_dt=1800.0, rtol=1e-6, atol=1e-8, method="BDF",
                max_step=1800.0)
    ts = np.concatenate([ra.ts, rb.ts[1:]])
    Cc = np.concatenate([ra.Cc, rb.Cc[1:]])
    Cs = np.concatenate([ra.Csurf, rb.Csurf[1:]])
    Cmax = np.maximum(Cc, Cs)
    hit = np.where(Cmax < mp.C_TARGET)[0]
    return dict(label=label or mode, mode=mode, hm_scale=hm_scale,
                phase_switch_s=phase_switch, amb=amb_mode,
                t_end_h=float(ts[hit[0]] / 3600.0) if hit.size else None,
                Cmax_end=float(Cmax[-1]), Cc_end=float(Cc[-1]),
                Cs_end=float(Cs[-1]), wall=time.time() - t0, n=len(ts))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = [
        ("prescribed", dict(days=40.0)),
        ("heat_limited", dict(days=40.0)),
        ("scaled", dict(days=40.0, hm_scale=1e2)),
        ("scaled", dict(days=40.0, hm_scale=1e3)),
        ("heat_limited", dict(days=40.0, phase_switch=1200.0)),
        ("heat_limited", dict(days=40.0, phase_switch=2400.0)),
    ]
    rows = []
    for mode, kw in cases:
        lab = mode + (f":{kw['hm_scale']:g}" if "hm_scale" in kw else "")
        if kw.get("phase_switch", 1800.0) != 1800.0:
            lab += f"@switch{kw['phase_switch']:.0f}"
        r = run_case(mode, label=lab, **kw)
        rows.append(r)
        print(f"{lab:34s} t_end={r['t_end_h']} h  Cmax_end={r['Cmax_end']:.4f}  "
              f"({r['wall']:.1f}s)", flush=True)
    (OUT / "sensitivity.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nwrote", OUT / "sensitivity.json")


if __name__ == "__main__":
    main()
