# -*- coding: utf-8 -*-
"""
FINAL production script for the A-problem.

Uses the validated solver (:mod:`mol_solver`) with the heat-supply-limited
surface closure, and writes result1..result4.xlsx in the 附件3 template format
plus the paper tables.

Physical model: see docs/MODEL.md.  Verified properties of the solver
(scripts/check_budget_exact.py, scripts/check_step_law.py):
  - discrete water budget  sum_i V_i dC_i/dt = -F_N j_w   (rel. error 0)
  - discrete energy budget sum_i V_i rho cp dT_i/dt = F_N q_in (rel. error ~1e-14)

Run: python scripts/final_produce.py [--N 150]
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

from mol_solver import MolSolver, Series, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402

TEMPL = ROOT.parents[1] / "problems" / "A题" / "附件" / "附件3"
OUT = ROOT / "out"
T_PHASE = 1800.0


def fill(ws, times, r_cm, vals, surf=None):
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


def sample(solver, res, r_out, Rfun=None):
    N = solver.N
    nT = len(res.ts)
    To = np.empty((nT, len(r_out)))
    Co = np.empty((nT, len(r_out)))
    Cs = np.empty(nT)
    for k in range(nT):
        R = res.R[k]
        r_nodes = np.concatenate(([0.0], R * solver.xi_c, [R]))
        Cn = np.concatenate(([res.C[k][0]], res.C[k][:N], [res.Csurf[k]]))
        Tn = np.concatenate(([res.T[k][0]], res.T[k][:N], [res.Tsurf[k]]))
        Co[k] = np.interp(r_out, r_nodes, Cn)
        To[k] = np.interp(r_out, r_nodes, Tn)
        Cs[k] = res.Csurf[k]
    return k2c(To), Co, Cs


def phase(N, props, t0, t1, T0, C0, sdt, rtol, atol, mstep, Rfun=None):
    s = MolSolver(N=N, R0=mp.R0, Rfun=Rfun)
    r = s.run(props, t1, T0, C0, t_start=t0, sample_dt=sdt, rtol=rtol,
              atol=atol, method="BDF", max_step=mstep)
    return s, r


def merge(a, b):
    return Series(
        ts=list(a.ts) + list(b.ts)[1:],
        T=list(a.T) + list(b.T)[1:],
        C=list(a.C) + list(b.C)[1:],
        R=list(a.R) + list(b.R)[1:],
        Tsurf=list(a.Tsurf) + list(b.Tsurf)[1:],
        Csurf=list(a.Csurf) + list(b.Csurf)[1:],
        Tc=list(a.Tc) + list(b.Tc)[1:],
        Cc=list(a.Cc) + list(b.Cc)[1:],
        jw=list(a.jw) + list(b.jw)[1:],
        q=list(getattr(a, "q", [])) + list(getattr(b, "q", []))[1:],
        W=list(a.W) + list(b.W)[1:],
        Tamb=list(a.Tamb) + list(b.Tamb)[1:],
        Camb=list(a.Camb) + list(b.Camb)[1:],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=150)
    ap.add_argument("--problems", type=str, default="1,2,3,4")
    ap.add_argument("--days", type=float, default=14.0)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    amb = mp.Ambient()
    N = args.N
    meta = {"N": N, "hm_mode": "heat_limited"}
    rc = mp.output_radii_cm(0.1, 2.0)
    t0wall = time.time()

    # phase A (preheating) is common to all problems
    pa = mp.props_problem1(amb)
    pa.hm_mode = "heat_limited"
    sa, ra = phase(N, pa, 0.0, T_PHASE, c2k(mp.T_INIT_C), mp.C_INIT,
                   1.0, 1e-7, 1e-9, 20.0)
    print("phase A done", flush=True)

    if "1" in args.problems:
        wb = openpyxl.load_workbook(TEMPL / "result1.xlsx")
        T, C, Cs = sample(sa, ra, np.asarray(rc) * 1e-2)
        fill(wb["温度"], ra.ts, rc, T)
        fill(wb["水分浓度"], ra.ts, rc, C)
        wb.save(OUT / "result1.xlsx")
        np.savez_compressed(OUT / "p1.npz", t=np.array(ra.ts), r=np.array(rc),
                            T=T, C=C)
        meta["p1"] = dict(n=len(ra.ts), Ts=float(k2c(ra.Tsurf[-1])),
                          Tc=float(k2c(ra.Tc[-1])), Cs=float(ra.Csurf[-1]),
                          Cc=float(ra.Cc[-1]), W0=float(ra.W[0]),
                          W1=float(ra.W[-1]))
        print("result1.xlsx", meta["p1"], flush=True)

    if "2" in args.problems:
        pb = mp.props_appendix3(amb)
        pb.hm_mode = "heat_limited"
        sb, rb = phase(N, pb, T_PHASE, 3 * 3600.0, ra.T[-1], ra.C[-1],
                       1.0, 1e-7, 1e-9, 20.0)
        res = merge(ra, rb)
        T, C, Cs = sample(sa, res, np.asarray(rc) * 1e-2)
        wb = openpyxl.load_workbook(TEMPL / "result2.xlsx")
        fill(wb["温度"], res.ts, rc, T)
        fill(wb["水分浓度"], res.ts, rc, C)
        wb.save(OUT / "result2.xlsx")
        np.savez_compressed(OUT / "p2.npz", t=np.array(res.ts), r=np.array(rc),
                            T=T, C=C)
        meta["p2"] = dict(n=len(res.ts), Ts=float(k2c(res.Tsurf[-1])),
                          Tc=float(k2c(res.Tc[-1])), Cs=float(res.Csurf[-1]),
                          Cc=float(res.Cc[-1]))
        print("result2.xlsx", meta["p2"], flush=True)

    if "3" in args.problems:
        pb = mp.props_appendix3(amb)
        pb.hm_mode = "heat_limited"
        tcap = args.days * 24 * 3600.0
        sb, rb = phase(N, pb, T_PHASE, tcap, ra.T[-1], ra.C[-1],
                       60.0, 1e-6, 1e-8, 600.0)
        res = merge(ra, rb)
        T, C, Cs = sample(sa, res, np.asarray(rc) * 1e-2)
        Cmax = np.max(C, axis=1)
        hit = np.where(Cmax < mp.C_TARGET)[0]
        t_end_h = float(res.ts[hit[0]] / 3600.0) if hit.size else None
        wb = openpyxl.load_workbook(TEMPL / "result3.xlsx")
        fill(wb.worksheets[0], res.ts, rc, C)
        wb.save(OUT / "result3.xlsx")
        np.savez_compressed(OUT / "p3.npz", t=np.array(res.ts), r=np.array(rc),
                            T=T, C=C, t_end_h=(t_end_h if t_end_h else np.nan))
        meta["p3"] = dict(n=len(res.ts), t_end_h=t_end_h,
                          Cmax_end=float(Cmax[-1]), Cc_end=float(C[-1][0]))
        print("result3.xlsx", meta["p3"], flush=True)

    if "4" in args.problems:
        Rf, _ = mp.make_Rfun()
        R_end = float(Rf(259200.0))
        rc4 = mp.output_radii_cm(0.1, round(R_end * 100, 1))
        pa4 = mp.props_problem1(amb)
        pa4.hm_mode = "heat_limited"
        sa4, ra4 = phase(N, pa4, 0.0, T_PHASE, c2k(mp.T_INIT_C), mp.C_INIT,
                         60.0, 1e-7, 1e-9, 300.0, Rf)
        pb = mp.props_appendix4(amb)
        pb.hm_mode = "heat_limited"
        sb, rb = phase(N, pb, T_PHASE, 259200.0, ra4.T[-1], ra4.C[-1],
                       60.0, 1e-6, 1e-8, 900.0, Rf)
        res = merge(ra4, rb)
        T, C, Cs = sample(sa4, res, np.asarray(rc4) * 1e-2)
        Cmax = np.max(C, axis=1)
        hit = np.where(Cmax < mp.C_TARGET)[0]
        t_end_h = float(res.ts[hit[0]] / 3600.0) if hit.size else None
        wb = openpyxl.load_workbook(TEMPL / "result4.xlsx")
        fill(wb.worksheets[0], res.ts, rc4, C, surf=Cs)
        wb.save(OUT / "result4.xlsx")
        np.savez_compressed(OUT / "p4.npz", t=np.array(res.ts), r=np.array(rc4),
                            T=T, C=C, Cs=Cs,
                            t_end_h=(t_end_h if t_end_h else np.nan))
        meta["p4"] = dict(n=len(res.ts), t_end_h=t_end_h,
                          Cmax_end=float(Cmax[-1]),
                          R_end_cm=float(res.R[-1] * 100))
        print("result4.xlsx", meta["p4"], flush=True)

    meta["wall_s"] = time.time() - t0wall
    (OUT / "final_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
