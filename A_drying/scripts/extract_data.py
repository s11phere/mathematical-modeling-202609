# -*- coding: utf-8 -*-
"""Extract the A-problem attachment data into reproducible CSV files.

Reads (read-only):
    problems/A题/附件/附件1.xlsx   ambient temperature / humidity, 0..14400 s step 60 s
    problems/A题/附件/附件2.xlsx   sample radius, 0..259200 s step 1800 s

Writes (overwritten, always regenerated):
    workspace/A_drying/data/attachment1_ambient.csv
    workspace/A_drying/data/attachment2_radius.csv
    workspace/A_drying/data/data_summary.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "problems" / "A题" / "附件"
DATA = ROOT / "workspace" / "A_drying" / "data"


def read_any(path: Path) -> pd.DataFrame:
    """Read .xls or .xlsx transparently."""
    try:
        return pd.read_excel(path)
    except Exception:
        # legacy .xls needs xlrd; fall back to a manual openpyxl attempt
        import openpyxl

        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        return pd.DataFrame(rows[1:], columns=rows[0])


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {}

    a1 = SRC / "附件1.xlsx"
    df1 = read_any(a1)
    df1.columns = ["time_s", "T_ambient_C", "C_ambient_kgkg"]
    df1 = df1.astype({"time_s": "int64", "T_ambient_C": float, "C_ambient_kgkg": float})
    df1.to_csv(DATA / "attachment1_ambient.csv", index=False)
    summary["attachment1"] = {
        "source": str(a1.relative_to(ROOT)),
        "n_rows": int(len(df1)),
        "columns": list(df1.columns),
        "time_s": [int(df1.time_s.iloc[0]), int(df1.time_s.iloc[-1])],
        "dt_s": sorted(set(df1.time_s.diff().dropna().unique().tolist())),
        "T_ambient_C": [float(df1.T_ambient_C.min()), float(df1.T_ambient_C.max())],
        "C_ambient_kgkg": [float(df1.C_ambient_kgkg.min()), float(df1.C_ambient_kgkg.max())],
    }

    a2 = SRC / "附件2.xlsx"
    df2 = read_any(a2)
    df2.columns = ["time_s", "R_cm"]
    df2 = df2.astype({"time_s": "int64", "R_cm": float})
    df2.to_csv(DATA / "attachment2_radius.csv", index=False)
    summary["attachment2"] = {
        "source": str(a2.relative_to(ROOT)),
        "n_rows": int(len(df2)),
        "columns": list(df2.columns),
        "time_s": [int(df2.time_s.iloc[0]), int(df2.time_s.iloc[-1])],
        "dt_s": sorted(set(df2.time_s.diff().dropna().unique().tolist())),
        "R_cm": [float(df2.R_cm.min()), float(df2.R_cm.max())],
    }

    # sanity: monotonicity / consistency checks that later code relies on
    assert df1.time_s.is_monotonic_increasing, "attachment1 time not sorted"
    assert df2.time_s.is_monotonic_increasing, "attachment2 time not sorted"
    assert df2.R_cm.is_monotonic_decreasing, "attachment2 radius not monotone decreasing"
    assert abs(df2.time_s.iloc[-1] - 259200) == 0

    (DATA / "data_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
