# -*- coding: utf-8 -*-
"""
Assemble result2.xlsx (problems 2) from the saved phase results, and write the
paper tables (tables 1-5) as CSV.

Run after ``scripts/produce_all.py`` has produced ``out/p1.npz`` and
``out/p2_raw.npz``.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mol_solver import k2c  # noqa: E402
import model_problems as mp  # noqa: E402

TEMPL = ROOT.parents[1] / "problems" / "A题" / "附件" / "附件3"
OUT = ROOT / "out"
N = 100
R0 = 0.02
xi_c = 0.5 * (np.linspace(0, 1, N + 1)[:-1] + np.linspace(0, 1, N + 1)[1:])
r_cm = mp.output_radii_cm(0.1, 2.0)
r_out = r_cm * 1e-2


def interp_profiles(ts, T, C, Tsurf, Csurf):
    nT = len(ts)
    To = np.empty((nT, len(r_out)))
    Co = np.empty((nT, len(r_out)))
    for k in range(nT):
        r_nodes = np.concatenate(([0.0], R0 * xi_c, [R0]))
        Tn = np.concatenate(([T[k][0]], T[k][:N], [Tsurf[k]]))
        Cn = np.concatenate(([C[k][0]], C[k][:N], [Csurf[k]]))
        To[k] = np.interp(r_out, r_nodes, Tn)
        Co[k] = np.interp(r_out, r_nodes, Cn)
    return k2c(To), Co


def fill(ws, times, vals, surf=None):
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


def table(path, ts, T, C, times, idx_r, tlabel):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([tlabel] + ["0", "0.5", "1", "1.5", "2"])
        for tt in times:
            k = int(np.argmin(np.abs(np.asarray(ts) - tt)))
            w.writerow([f"{tt:.4g}"] + [f"{T[k, i]:.4f}" for i in idx_r])
    with path.with_name(path.stem + "_C.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([tlabel] + ["0", "0.5", "1", "1.5", "2"])
        for tt in times:
            k = int(np.argmin(np.abs(np.asarray(ts) - tt)))
            w.writerow([f"{tt:.4g}"] + [f"{C[k, i]:.4f}" for i in idx_r])


# ---- problem 1 tables -----------------------------------------------------
z1 = np.load(OUT / "p1.npz")
t1, T1, C1 = z1["t"], z1["T"], z1["C"]
idx_r = [int(round(x / 0.1)) for x in (0, 0.5, 1.0, 1.5, 2.0)]
table(OUT / "table1_T.csv", t1, T1, C1, [100, 300, 600, 900, 1200, 1500, 1800],
      idx_r, "时间/s")
print("table1 written")

# ---- problem 2 ------------------------------------------------------------
z2 = np.load(OUT / "p2_raw.npz")
ts = np.concatenate([z2["ta"], z2["tb"][1:]])
T = np.concatenate([z2["Ta"], z2["Tb"][1:]])
C = np.concatenate([z2["Ca"], z2["Cb"][1:]])
Tsurf = np.concatenate([z2["Tsa"], z2["Tsb"][1:]])
Csurf = np.concatenate([z2["Csa"], z2["Csb"][1:]])
T2, C2 = interp_profiles(ts, T, C, Tsurf, Csurf)
wb = openpyxl.load_workbook(TEMPL / "result2.xlsx")
fill(wb["温度"], ts, T2)
fill(wb["水分浓度"], ts, C2)
wb.save(OUT / "result2.xlsx")
print("result2.xlsx written:", len(ts), "rows")
np.savez_compressed(OUT / "p2.npz", t=ts, r=r_cm, T=T2, C=C2)
table(OUT / "table3_T.csv", ts, T2, C2, [1800, 3600, 5400, 7200, 9000, 10800],
      idx_r, "时间/s")
print("table3 written")
