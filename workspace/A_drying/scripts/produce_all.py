# -*- coding: utf-8 -*-
"""
Produce result1..result4.xlsx and the paper tables for all four problems.

Run:  python scripts/produce_all.py [--N 100] [--hm-mode prescribed]
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


def fill_sheet(ws, times, r_cm, vals, surf=None):
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
            ws.cell(row=2 + i, column=2 + len(r_cm), value=round(float(surf[i]), 4))


def sample(solver, res, r_cm):
    N = solver.N
    r_out = np.asarray(r_cm, float) * 1e-2
    nT = len(res.ts)
    T_out = np.empty((nT, len(r_out)))
    C_out = np.empty((nT, len(r_out)))
    for k in range(nT):
        R = res.R[k]
        r_nodes = np.concatenate(([0.0], R * solver.xi_c, [R]))
        T_nodes = np.concatenate(([res.T[k][0]], res.T[k][:N], [res.Tsurf[k]]))
        C_nodes = np.concatenate(([res.C[k][0]], res.C[k][:N], [res.Csurf[k]]))
        T_out[k] = np.interp(r_out, r_nodes, T_nodes)
        C_out[k] = np.interp(r_out, r_nodes, C_nodes)
    return k2c(T_out), C_out


def run_phase(N, props, t0, t1, T0, C0, sample_dt, rtol, atol, max_step, Rfun=None,
              method="BDF"):
    s = MolSolver(N=N, R0=mp.R0, Rfun=Rfun)
    r = s.run(props, t1, T0, C0, t_start=t0, sample_dt=sample_dt, rtol=rtol,
              atol=atol, method=method, max_step=max_step)
    return s, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=100)
    ap.add_argument("--hm-mode", type=str, default="prescribed")
    ap.add_argument("--problems", type=str, default="1,2,3,4")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    amb = mp.Ambient()
    r_cm = mp.output_radii_cm(0.1, 2.0)
    N = args.N
    metas = {}

    # ---------------- problem 1 ------------------------------------------
    if "1" in args.problems:
        t0 = time.time()
        p = mp.props_problem1(amb); p.hm_mode = args.hm_mode
        s, r = run_phase(N, p, 0.0, T_PHASE, c2k(mp.T_INIT_C), mp.C_INIT,
                         1.0, 1e-7, 1e-9, 20.0)
        T, C = sample(s, r, r_cm)
        wb = openpyxl.load_workbook(TEMPL / "result1.xlsx")
        fill_sheet(wb["温度"], r.ts, r_cm, T)
        fill_sheet(wb["水分浓度"], r.ts, r_cm, C)
        wb.save(OUT / "result1.xlsx")
        np.savez_compressed(OUT / "p1.npz", t=np.array(r.ts), r=np.array(r_cm),
                            T=T, C=C)
        metas["p1"] = dict(n=len(r.ts), wall=time.time() - t0,
                           Ts=k2c(r.Tsurf[-1]), Tc=k2c(r.Tc[-1]),
                           Cs=r.Csurf[-1], Cc=r.Cc[-1], W0=r.W[0], W1=r.W[-1])
        print("p1 done", metas["p1"], flush=True)

    # ---------------- problem 2 ------------------------------------------
    if "2" in args.problems:
        t0 = time.time()
        pa = mp.props_problem1(amb); pa.hm_mode = args.hm_mode
        sa, ra = run_phase(N, pa, 0.0, T_PHASE, c2k(mp.T_INIT_C), mp.C_INIT,
                           60.0, 1e-7, 1e-9, 30.0)
        pb = mp.props_appendix3(amb); pb.hm_mode = args.hm_mode
        sb, rb = run_phase(N, pb, T_PHASE, 10800.0, ra.T[-1], ra.C[-1],
                           30.0, 1e-7, 1e-9, 30.0)
        # concatenate
        ts = list(ra.ts) + list(rb.ts)[1:]
        Tn = list(ra.T) + list(rb.T)[1:]
        Cn = list(ra.C) + list(rb.C)[1:]
        Rn = list(ra.R) + list(rb.R)[1:]
        Ts_ = list(ra.Tsurf) + list(rb.Tsurf)[1:]
        Cs_ = list(ra.Csurf) + list(rb.Csurf)[1:]
        from mol_solver import Series
        res = Series(ts=ts, T=Tn, C=Cn, R=Rn, Tsurf=Ts_, Csurf=Cs_)
        T, C = sample(sa, res, r_cm)
        wb = openpyxl.load_workbook(TEMPL / "result2.xlsx")
        fill_sheet(wb["温度"], ts, r_cm, T)
        fill_sheet(wb["水分浓度"], ts, r_cm, C)
        wb.save(OUT / "result2.xlsx")
        np.savez_compressed(OUT / "p2.npz", t=np.array(ts), r=np.array(r_cm),
                            T=T, C=C)
        metas["p2"] = dict(n=len(ts), wall=time.time() - t0,
                           Ts=k2c(Ts_[-1]), Tc=k2c(Tn[-1][0]),
                           Cs=Cs_[-1], Cc=Cn[-1][0])
        print("p2 done", metas["p2"], flush=True)

    (OUT / "produce_meta.json").write_text(
        json.dumps(metas, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
