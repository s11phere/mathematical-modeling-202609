# -*- coding: utf-8 -*-
"""
Produce result3.xlsx and result4.xlsx.

Problem 3
    Appendix 3 properties, 60 s output, integrated until the moisture target is
    reached or a 30-day cap.
Problem 4
    Appendix 4 properties, moving boundary from 附件2, 60 s output, ratio grid
    with the last column = 药材表面.

Run: python scripts/produce_p34.py --problem 3|4 [--N 100] [--days 30]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402

TEMPL = ROOT.parents[1] / "problems" / "A题" / "附件" / "附件3"
OUT = ROOT / "out"
T_PHASE = 1800.0


def sheet(ws, times, r_cm, vals, surf=None):
    if ws.max_row > 1:
        ws.delete_rows(2, ws.max_row)
    ws.cell(row=1, column=1, value="时间\\到药材中心的距离")
    for j, r in enumerate(r_cm):
        ws.cell(row=1, column=2 + j, value=float(r))
    if surf is not None:
        ws.cell(row=1, column=2 + len(r_cm), value="药材表面")
    for i, t in enumerate(times):
        ws.cell(row=2 + i, column=1, value=float(t))
        for j in range(len(r_cm)):
            ws.cell(row=2 + i, column=2 + j, value=round(float(vals[i, j]), 4))
    if surf is not None:
        for i in range(len(times)):
            ws.cell(row=2 + i, column=2 + len(r_cm),
                    value=round(float(surf[i]), 4))


def sample_to(solver, res, r_out, N):
    nT = len(res.ts)
    Co = np.empty((nT, len(r_out)))
    To = np.empty((nT, len(r_out)))
    for k in range(nT):
        R = res.R[k]
        r_nodes = np.concatenate(([0.0], R * solver.xi_c, [R]))
        Cn = np.concatenate(([res.C[k][0]], res.C[k][:N], [res.Csurf[k]]))
        Tn = np.concatenate(([res.T[k][0]], res.T[k][:N], [res.Tsurf[k]]))
        Co[k] = np.interp(r_out, r_nodes, Cn)
        To[k] = np.interp(r_out, r_nodes, Tn)
    return k2c(To), Co


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", type=int, required=True, choices=[3, 4])
    ap.add_argument("--N", type=int, default=100)
    ap.add_argument("--hm-mode", type=str, default="prescribed")
    ap.add_argument("--days", type=float, default=30.0)
    ap.add_argument("--sample-dt", type=float, default=60.0)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    amb = mp.Ambient()
    N = args.N
    tcap = args.days * 24 * 3600.0
    meta = {"problem": args.problem, "N": N, "hm_mode": args.hm_mode,
            "days": args.days}

    Rfun = None
    if args.problem == 4:
        Rf, dRf = mp.make_Rfun()
        Rfun = Rf
        R_end = float(Rf(min(tcap, 259200.0)))
        r_cm = mp.output_radii_cm(0.1, round(R_end * 100, 1))
        propsB = mp.props_appendix4(amb)
        run_to = min(tcap, 259200.0)
    else:
        r_cm = mp.output_radii_cm(0.1, 2.0)
        propsB = mp.props_appendix3(amb)
        run_to = tcap

    t0 = time.time()
    pa = mp.props_problem1(amb); pa.hm_mode = args.hm_mode
    sa = MolSolver(N=N, R0=mp.R0, Rfun=Rfun)
    ra = sa.run(pa, T_PHASE, c2k(mp.T_INIT_C), mp.C_INIT, t_start=0.0,
                sample_dt=args.sample_dt, rtol=1e-7, atol=1e-9, method="BDF",
                max_step=300.0)
    propsB.hm_mode = args.hm_mode
    sb = MolSolver(N=N, R0=mp.R0, Rfun=Rfun)
    rb = sb.run(propsB, run_to, ra.T[-1], ra.C[-1], t_start=T_PHASE,
                sample_dt=args.sample_dt, rtol=1e-6, atol=1e-8, method="BDF",
                max_step=900.0)
    ts = np.concatenate([ra.ts, rb.ts[1:]])
    T = list(ra.T) + list(rb.T)[1:]
    C = list(ra.C) + list(rb.C)[1:]
    Rl = list(ra.R) + list(rb.R)[1:]
    Tsurf = np.concatenate([ra.Tsurf, rb.Tsurf[1:]])
    Csurf = np.concatenate([ra.Csurf, rb.Csurf[1:]])
    from mol_solver import Series
    res = Series(ts=list(ts), T=T, C=C, R=Rl, Tsurf=list(Tsurf),
                 Csurf=list(Csurf))
    To, Co = sample_to(sa, res, np.asarray(r_cm) * 1e-2, N)
    Cmax = np.max(Co, axis=1)
    hit = np.where(Cmax < mp.C_TARGET)[0]
    t_end_h = float(ts[hit[0]] / 3600.0) if hit.size else float("nan")

    if args.problem == 3:
        wb = openpyxl.load_workbook(TEMPL / "result3.xlsx")
        sheet(wb.worksheets[0], ts, r_cm, Co)
        wb.save(OUT / "result3.xlsx")
        np.savez_compressed(OUT / "p3.npz", t=ts, r=r_cm, T=To, C=Co,
                            t_end_h=t_end_h)
    else:
        wb = openpyxl.load_workbook(TEMPL / "result4.xlsx")
        sheet(wb.worksheets[0], ts, r_cm, Co, surf=Csurf)
        wb.save(OUT / "result4.xlsx")
        np.savez_compressed(OUT / "p4.npz", t=ts, r=r_cm, T=To, C=Co,
                            Cs=Csurf, t_end_h=t_end_h)

    meta.update(n=len(ts), wall=time.time() - t0, t_end_h=t_end_h,
                Cmax_end=float(Cmax[-1]),
                Tsurf_end_C=float(k2c(Tsurf[-1])), Csurf_end=float(Csurf[-1]),
                Cc_end=float(C[-1][0]), R_end_cm=float(Rl[-1] * 100))
    (OUT / f"p{args.problem}_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
