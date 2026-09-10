# -*- coding: utf-8 -*-
"""
Driver: produce the answer tables and ``result*.xlsx`` files for problems 1-4.

Physics note (see ``docs/MODEL.md`` section 5)
----------------------------------------------
``h_m`` is taken from 附录2 as prescribed (8e-7 m/s).  With the humidity-ratio
driving force this gives a preheating phase in which the sample heats from 28 to
~37 degC while losing <1e-3 of its water -- which is what a "预热平衡阶段" should
look like.  The alternative Chilton-Colburn value is available via ``--hm-mode``
for the sensitivity study.

Phase structure (problem 2 onward)
----------------------------------
* t in [0, 1800] s : 预热平衡阶段, 附录2 properties (constant rho, cp, k, D)
* t in [1800, end] : 恒温干燥阶段, 附录3 (or 附录4 for problem 4) properties

The two phases are integrated separately and the state is carried across, so the
discontinuity in the coefficients at t = 1800 s is handled explicitly.

Usage
-----
    python scripts/run_problems.py --problem 1
    python scripts/run_problems.py --problem 2
    python scripts/run_problems.py --problem 3
    python scripts/run_problems.py --problem 4
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mol_solver import MolSolver, c2k, k2c  # noqa: E402
import model_problems as mp  # noqa: E402
from write_result import (write_result1, write_result2, write_result3,
                          write_result4)  # noqa: E402

T_PHASE = 1800.0        # preheating -> constant-temperature drying


def git_rev() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def code_md5() -> dict:
    import hashlib
    out = {}
    for f in ("src/mol_solver.py", "src/model_problems.py", "scripts/run_problems.py",
              "src/write_result.py"):
        p = ROOT / f
        if p.exists():
            out[f] = hashlib.md5(p.read_bytes()).hexdigest()
    return out


# --------------------------------------------------------------------------
def sample_fields(solver, res, r_cm):
    """Interpolate the cell-average profiles onto ``r_cm`` (cm) for all times."""
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
    return c2k(T_out), C_out


def write_diag(path: Path, res) -> None:
    keys = ["ts", "Tsurf", "Csurf", "Tc", "Cc", "jw", "W", "Tamb", "Camb"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(keys)
        for row in zip(*[getattr(res, k) for k in keys]):
            w.writerow(row)


def write_table(path: Path, res, T, C, times, idx_r, header_time="time"):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([header_time] + [f"r={r}" for r in (0, 0.5, 1.0, 1.5, 2.0)])
        for tt in times:
            k = int(np.argmin(np.abs(np.asarray(res.ts) - tt)))
            w.writerow([f"{tt:.4g}"] + [f"{T[k, i]:.4f}" for i in idx_r])
    with path.with_name(path.stem + "_C.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([header_time] + [f"r={r}" for r in (0, 0.5, 1.0, 1.5, 2.0)])
        for tt in times:
            k = int(np.argmin(np.abs(np.asarray(res.ts) - tt)))
            w.writerow([f"{tt:.4g}"] + [f"{C[k, i]:.4f}" for i in idx_r])


def run_phase(N, props, t0, t1, T0, C0, sample_dt, rtol, atol, max_step,
              Rfun=None):
    solver = MolSolver(N=N, R0=mp.R0, Rfun=Rfun)
    res = solver.run(props, t1, T0, C0, t_start=t0, sample_dt=sample_dt,
                     rtol=rtol, atol=atol, method="BDF", max_step=max_step)
    return solver, res


def merge(res_a, res_b):
    """Concatenate two phase results, dropping the duplicated switch time."""
    for k in ("ts", "T", "C", "R", "Tsurf", "Csurf", "Tc", "Cc", "jw", "q",
              "W", "Tamb", "Camb"):
        getattr(res_a, k).extend(getattr(res_b, k)[1:])
    return res_a


def meta_solve(args, res, wall):
    return dict(problem=args.problem, N=args.N, hm_mode=args.hm_mode,
                sample_dt=args.sample_dt, n_samples=len(res.ts), wall_s=wall,
                git=git_rev(), md5=code_md5(), host=platform.node(),
                python=platform.python_version(),
                Tsurf_end_C=float(k2c(res.Tsurf[-1])),
                Tc_end_C=float(k2c(res.Tc[-1])),
                Csurf_end=float(res.Csurf[-1]), Cc_end=float(res.Cc[-1]),
                W0=float(res.W[0]), W_end=float(res.W[-1]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", type=int, required=True, choices=[1, 2, 3, 4])
    ap.add_argument("--N", type=int, default=200)
    ap.add_argument("--hm-mode", type=str, default="prescribed",
                    choices=["prescribed", "lewis"])
    ap.add_argument("--sample-dt", type=float, default=None)
    ap.add_argument("--rtol", type=float, default=1e-8)
    ap.add_argument("--atol", type=float, default=1e-10)
    ap.add_argument("--max-step", type=float, default=60.0)
    ap.add_argument("--out", type=str, default="out")
    args = ap.parse_args()

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    amb = mp.Ambient()
    r_cm = mp.output_radii_cm(0.1, 2.0)
    idx_r = [int(round(x / 0.1)) for x in (0, 0.5, 1.0, 1.5, 2.0)]
    t0wall = time.time()
    N = args.N

    # ---------------- problem 1 -------------------------------------------
    if args.problem == 1:
        props = mp.props_problem1(amb)
        props.hm_mode = args.hm_mode
        sample_dt = args.sample_dt or 1.0
        solver, res = run_phase(N, props, 0.0, T_PHASE, c2k(mp.T_INIT_C),
                                mp.C_INIT, sample_dt, args.rtol, args.atol,
                                args.max_step)
        T, C = sample_fields(solver, res, r_cm)
        np.savez_compressed(out / "p1_profiles.npz", t_s=np.asarray(res.ts),
                            r_cm=r_cm, T_C=T, C=C)
        write_result1(out / "result1.xlsx", res.ts, r_cm, T, C)
        write_diag(out / "p1_diag.csv", res)
        write_table(out / "p1_table.csv", res, T, C,
                    [100, 300, 600, 900, 1200, 1500, 1800], idx_r, "时间/s")
        meta = meta_solve(args, res, time.time() - t0wall)
        (out / "p1_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(meta, indent=2, ensure_ascii=False))
        return 0

    # ---------------- problem 2 -------------------------------------------
    if args.problem == 2:
        # phase A: preheating (附录2)
        pa = mp.props_problem1(amb)
        pa.hm_mode = args.hm_mode
        _, ra = run_phase(N, pa, 0.0, T_PHASE, c2k(mp.T_INIT_C), mp.C_INIT,
                          60.0, args.rtol, args.atol, args.max_step)
        # phase B: constant-temperature drying (附录3)
        pb = mp.props_appendix3(amb)
        pb.hm_mode = args.hm_mode
        _, rb = run_phase(N, pb, T_PHASE, 3 * 3600.0, ra.T[-1], ra.C[-1],
                          60.0, args.rtol, args.atol, args.max_step)
        res = merge(ra, rb)
        solver = MolSolver(N=N, R0=mp.R0)
        T, C = sample_fields(solver, res, r_cm)
        np.savez_compressed(out / "p2_profiles.npz", t_s=np.asarray(res.ts),
                            r_cm=r_cm, T_C=T, C=C)
        write_result2(out / "result2.xlsx", res.ts, r_cm, T, C)
        write_diag(out / "p2_diag.csv", res)
        write_table(out / "p2_table.csv", res, T, C,
                    [1800, 3600, 5400, 7200, 9000, 10800], idx_r, "时间/s")
        meta = meta_solve(args, res, time.time() - t0wall)
        (out / "p2_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(meta, indent=2, ensure_ascii=False))
        return 0

    # ---------------- problem 3 -------------------------------------------
    if args.problem == 3:
        sample_dt = args.sample_dt or 60.0
        t_dry = args.dry_hours * 3600.0 if hasattr(args, "dry_hours") else 4 * 24 * 3600.0
        pa = mp.props_problem1(amb)
        pa.hm_mode = args.hm_mode
        _, ra = run_phase(N, pa, 0.0, T_PHASE, c2k(mp.T_INIT_C), mp.C_INIT,
                          sample_dt, args.rtol, args.atol, args.max_step)
        pb = mp.props_appendix3(amb)
        pb.hm_mode = args.hm_mode
        _, rb = run_phase(N, pb, T_PHASE, t_dry, ra.T[-1], ra.C[-1],
                          sample_dt, args.rtol, args.atol, args.max_step)
        res = merge(ra, rb)
        solver = MolSolver(N=N, R0=mp.R0)
        T, C = sample_fields(solver, res, r_cm)
        Cmax_t = np.max(C, axis=1)
        hit = np.where(Cmax_t < mp.C_TARGET)[0]
        t_end_h = float(res.ts[hit[0]] / 3600.0) if hit.size else float("nan")
        np.savez_compressed(out / "p3_profiles.npz", t_s=np.asarray(res.ts),
                            r_cm=r_cm, C=C, t_end_h=t_end_h)
        write_result3(out / "result3.xlsx", res.ts, r_cm, C)
        write_diag(out / "p3_diag.csv", res)
        meta = meta_solve(args, res, time.time() - t0wall)
        meta["t_end_h"] = t_end_h
        meta["Cmax_end"] = float(Cmax_t[-1])
        (out / "p3_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(meta, indent=2, ensure_ascii=False))
        return 0

    # ---------------- problem 4 -------------------------------------------
    if args.problem == 4:
        sample_dt = args.sample_dt or 60.0
        Rf, dRf = mp.make_Rfun()
        R_T = float(Rf(259200.0))
        r_cm4 = mp.output_radii_cm(0.1, round(R_T * 100, 1))
        pa = mp.props_problem1(amb)
        pa.hm_mode = args.hm_mode
        _, ra = run_phase(N, pa, 0.0, T_PHASE, c2k(mp.T_INIT_C), mp.C_INIT,
                          sample_dt, args.rtol, args.atol, args.max_step, Rf)
        pb = mp.props_appendix4(amb)
        pb.hm_mode = args.hm_mode
        _, rb = run_phase(N, pb, T_PHASE, 259200.0, ra.T[-1], ra.C[-1],
                          sample_dt, args.rtol, args.atol, args.max_step, Rf)
        res = merge(ra, rb)
        solver = MolSolver(N=N, R0=mp.R0, Rfun=Rf)
        T, C = sample_fields(solver, res, r_cm4)
        Cmax_t = np.max(C, axis=1)
        hit = np.where(Cmax_t < mp.C_TARGET)[0]
        t_end_h = float(res.ts[hit[0]] / 3600.0) if hit.size else float("nan")
        np.savez_compressed(out / "p4_profiles.npz", t_s=np.asarray(res.ts),
                            r_cm=r_cm4, C=C, t_end_h=t_end_h)
        write_result4(out / "result4.xlsx", res.ts, r_cm4, C,
                      [res.Csurf[k] for k in range(len(res.ts))])
        write_diag(out / "p4_diag.csv", res)
        meta = meta_solve(args, res, time.time() - t0wall)
        meta["t_end_h"] = t_end_h
        meta["R_end_cm"] = float(res.R[-1] * 100)
        (out / "p4_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(meta, indent=2, ensure_ascii=False))
        return 0

    raise SystemExit("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
