# -*- coding: utf-8 -*-
"""
Generate the paper tables (表1-表6) from the produced profiles.

Writes ``out/tables.md`` with Markdown tables ready to paste into the paper, and
``out/tables.json`` with the raw numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import model_problems as mp  # noqa: E402

OUT = ROOT / "out"
IDX = [0, 5, 10, 15, 20]          # r = 0, 0.5, 1.0, 1.5, 2.0 cm at 0.1 cm spacing


def at(ts, values, t):
    k = int(np.argmin(np.abs(np.asarray(ts) - t)))
    return values[k]


def row(values, idx=IDX):
    return " | ".join(f"{values[i]:.4f}" for i in idx)


def main():
    md = []
    js = {}

    # ---- 表1/表2 : problem 1 (temperatures and moisture) -------------------
    z = np.load(OUT / "p1.npz")
    ts, T, C = z["t"], z["T"], z["C"]
    times = [100, 300, 600, 900, 1200, 1500, 1800]
    md.append("### 表1  30 分钟内药材的温度（°C）\n")
    md.append("| 时间/s | 0 cm | 0.5 cm | 1.0 cm | 1.5 cm | 2.0 cm |")
    md.append("|---|---|---|---|---|---|")
    for t in times:
        md.append(f"| {t} | {row(at(ts, T, t))} |")
    md.append("\n### 表2  30 分钟内药材的水分浓度（kg/kg）\n")
    md.append("| 时间/s | 0 cm | 0.5 cm | 1.0 cm | 1.5 cm | 2.0 cm |")
    md.append("|---|---|---|---|---|---|")
    for t in times:
        md.append(f"| {t} | {row(at(ts, C, t))} |")
    js["table1"] = {str(t): [round(float(at(ts, T, t)[i]), 4) for i in IDX] for t in times}
    js["table2"] = {str(t): [round(float(at(ts, C, t)[i]), 4) for i in IDX] for t in times}

    # ---- 表3/表4 : problem 2 ---------------------------------------------
    z2 = np.load(OUT / "p2.npz")
    ts2, T2, C2 = z2["t"], z2["T"], z2["C"]
    times2 = [1800, 3600, 5400, 7200, 9000, 10800]
    md.append("\n### 表3  3 小时内药材的温度（°C）\n")
    md.append("| 时间/h | 0 cm | 0.5 cm | 1.0 cm | 1.5 cm | 2.0 cm |")
    md.append("|---|---|---|---|---|---|")
    for t in times2:
        md.append(f"| {t/3600:.1f} | {row(at(ts2, T2, t))} |")
    md.append("\n### 表4  3 小时内药材的水分浓度（kg/kg）\n")
    md.append("| 时间/h | 0 cm | 0.5 cm | 1.0 cm | 1.5 cm | 2.0 cm |")
    md.append("|---|---|---|---|---|---|")
    for t in times2:
        md.append(f"| {t/3600:.1f} | {row(at(ts2, C2, t))} |")
    js["table3"] = {str(t): [round(float(at(ts2, T2, t)[i]), 4) for i in IDX] for t in times2}
    js["table4"] = {str(t): [round(float(at(ts2, C2, t)[i]), 4) for i in IDX] for t in times2}

    # ---- 表5 : problem 3 --------------------------------------------------
    p3 = OUT / "p3.npz"
    if p3.exists():
        z3 = np.load(p3, allow_pickle=True)
        ts3, C3 = z3["t"], z3["C"]
        Cmax = C3.max(axis=1)
        hit = np.where(Cmax < mp.C_TARGET)[0]
        t_end = float(ts3[hit[0]]) if hit.size else float(ts3[-1])
        md.append("\n### 表5  药材烘干过程的水分浓度（kg/kg）\n")
        md.append("| 时间/h | 0 cm | 0.5 cm | 1.0 cm | 1.5 cm | 2.0 cm |")
        md.append("|---|---|---|---|---|---|")
        for h in [6, 12, 18, 24, 30, 36, 42, 48]:
            t = h * 3600.0
            if t <= ts3[-1]:
                md.append(f"| {h} | {row(at(ts3, C3, t))} |")
        md.append(f"| **烘干结束 {t_end/3600:.1f}** | {row(at(ts3, C3, t_end))} |")
        js["table5"] = {str(h): [round(float(at(ts3, C3, h * 3600.0)[i]), 4) for i in IDX]
                        for h in [6, 12, 18, 24, 30, 36, 42, 48]}
        js["t_end_h"] = t_end / 3600.0

    # ---- 表6 : problem 4 --------------------------------------------------
    p4 = OUT / "p4.npz"
    if p4.exists():
        z4 = np.load(p4, allow_pickle=True)
        ts4, C4 = z4["t"], z4["C"]
        md.append("\n### 表6  药材烘干过程的水分浓度（收缩，kg/kg）\n")
        md.append("| 时间/h | 0 cm | 0.5 cm | 1.0 cm | 药材表面 |")
        md.append("|---|---|---|---|---|")
        for h in [6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72]:
            t = h * 3600.0
            if t <= ts4[-1]:
                k = int(np.argmin(np.abs(ts4 - t)))
                md.append(f"| {h} | {C4[k][0]:.4f} | {C4[k][5]:.4f} | "
                          f"{C4[k][10]:.4f} | {C4[k][-1]:.4f} |")
        js["table6"] = {str(h): [round(float(np.load(OUT/'p4.npz')['C'][int(np.argmin(np.abs(ts4-h*3600.0)))][i]), 4) for i in (0, 5, 10, -1)]
                        for h in [6, 12, 18, 24, 36, 48, 60, 72] if h * 3600.0 <= ts4[-1]}

    (OUT / "tables.md").write_text("\n".join(md), encoding="utf-8")
    (OUT / "tables.json").write_text(json.dumps(js, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
