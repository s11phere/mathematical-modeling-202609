# -*- coding: utf-8 -*-
"""
Problem-specific physics for the 2026 CUMCM A-problem (herbal drying).

Builds the :class:`~drying_solver.Props` objects for problems 1-4 from the
appendices, and the interpolation helpers for the chamber schedule
(附件1) and the radius history (附件2).

Appendix 2 (problem 1)
    rho = 820, cp = 2600, k = 0.36, h = 25, h_m = 8e-7,
    D = 7e-9 exp(-0.89 C)
Appendix 3 (problems 2 and 3)
    rho = 650 + 128 C
    cp  = 1450 + 2736 C/(C+1)
    k   = 0.21 + 0.38 C/(C+1)
    D   = 2.4e-3 exp(-0.45 C) exp(-3850/T)
Appendix 4 (problem 4)
    rho = 760 + 90 C
    cp  = 1850 + 2150 C/(C+1)
    k   = 0.12 + 0.20 C/(C+1)
    D   = 4.2e-4 exp(-0.30 C) exp(-3850/T)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from mol_solver import Props, c2k

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# --------------------------------------------------------------------------
# global constants
# --------------------------------------------------------------------------
H_CONV = 25.0            # W m^-2 K^-1, convective heat transfer coefficient
HM_CONV = 8.0e-7         # m s^-1,  convective mass transfer coefficient
L_W = 2.26e6             # J kg^-1, latent heat of vaporisation
R0 = 0.02                # m, initial radius
C_INIT = 2.55            # kg/kg, initial dry-basis moisture
T_INIT_C = 28.0          # degC
C_TARGET = 0.15          # kg/kg, drying target

# phase switch: the preheating phase ends and the constant-temperature drying
# phase begins at t = 1800 s (preheating equilibrium lasts 30 min)
T_PHASE_S = 1800.0
# the chamber schedule is measured for 4 h (附件1); afterwards it is held at
# its final value (see docs/MODEL.md section 4)
T_AMB_END_S = 14400.0


# --------------------------------------------------------------------------
# chamber schedule (附件1)
# --------------------------------------------------------------------------
def load_ambient():
    df = pd.read_csv(DATA / "attachment1_ambient.csv")
    return df.time_s.to_numpy(float), df.T_ambient_C.to_numpy(float), df.C_ambient_kgkg.to_numpy(float)


class Ambient:
    """Piecewise-linear chamber temperature and humidity, held after 4 h."""

    def __init__(self, mode: str = "hold"):
        t, T, C = load_ambient()
        self.t, self.T, self.C = t, T, C
        self.mode = mode

    def Tamb(self, t):
        t = np.asarray(t, float)
        if self.mode == "hold":
            tt = np.minimum(t, self.t[-1])
        elif self.mode == "ramp":
            # continue the 2-4 h trend until 50 degC, then hold
            raise NotImplementedError
        return c2k(np.interp(tt, self.t, self.T))

    def Camb(self, t):
        t = np.asarray(t, float)
        tt = np.minimum(t, self.t[-1])
        return np.interp(tt, self.t, self.C)

    def Tend_C(self, t):
        return float(np.interp(min(float(t), self.t[-1]), self.t, self.T))

    def Cend(self, t):
        return float(np.interp(min(float(t), self.t[-1]), self.t, self.C))


# --------------------------------------------------------------------------
# material property sets
# --------------------------------------------------------------------------
def props_problem1(amb: Ambient, **kw) -> Props:
    c0 = 7e-9 / np.exp(-0.89 * C_INIT)      # D = 7e-9 exp(-0.89 C)
    rho_solid = 820.0
    rho_d = rho_solid / (1.0 + C_INIT)
    d = dict(
        rho=lambda C, T: np.full_like(C, rho_solid),
        cp=lambda C, T: np.full_like(C, 2600.0),
        k=lambda C, T: np.full_like(C, 0.36),
        D=lambda C, T: c0 * np.exp(-0.89 * np.clip(C, 0.0, None)),
        h=H_CONV, h_m=HM_CONV, Lw=L_W,
        Tamb=amb.Tamb, Camb=amb.Camb,
        rho_d0=rho_d, name="p1",
    )
    d.update(kw)
    return Props(**d)


def props_appendix3(amb: Ambient, **kw) -> Props:
    rho_d = 650.0 / (1.0 + C_INIT)
    d = dict(
        rho=lambda C, T: 650.0 + 128.0 * C,
        cp=lambda C, T: 1450.0 + 2736.0 * C / (C + 1.0),
        k=lambda C, T: 0.21 + 0.38 * C / (C + 1.0),
        D=lambda C, T: 2.4e-3 * np.exp(-0.45 * np.clip(C, 0.0, None)) * np.exp(-3850.0 / T),
        h=H_CONV, h_m=HM_CONV, Lw=L_W,
        Tamb=amb.Tamb, Camb=amb.Camb,
        rho_d0=rho_d, name="p23",
    )
    d.update(kw)
    return Props(**d)


def props_appendix4(amb: Ambient, **kw) -> Props:
    rho_d = 760.0 / (1.0 + C_INIT)
    d = dict(
        rho=lambda C, T: 760.0 + 90.0 * C,
        cp=lambda C, T: 1850.0 + 2150.0 * C / (C + 1.0),
        k=lambda C, T: 0.12 + 0.20 * C / (C + 1.0),
        D=lambda C, T: 4.2e-4 * np.exp(-0.30 * np.clip(C, 0.0, None)) * np.exp(-3850.0 / T),
        h=H_CONV, h_m=HM_CONV, Lw=L_W,
        Tamb=amb.Tamb, Camb=amb.Camb,
        rho_d0=rho_d, name="p4",
    )
    d.update(kw)
    return Props(**d)


# --------------------------------------------------------------------------
# radius history (附件2)
# --------------------------------------------------------------------------
def load_radius():
    df = pd.read_csv(DATA / "attachment2_radius.csv")
    return df.time_s.to_numpy(float), df.R_cm.to_numpy(float) * 1e-2


def make_Rfun(smooth: bool = True):
    """Return (R(t), dR/dt) in metres, from a monotone interpolant of 附件2."""
    t, R = load_radius()
    if not smooth:
        def Rf(tt):
            return float(np.interp(tt, t, R))
        def dRf(tt):
            h = 1.0
            return (Rf(tt + h) - Rf(tt - h)) / (2 * h)
        return Rf, dRf

    from scipy.interpolate import PchipInterpolator
    spl = PchipInterpolator(t, R, extrapolate=False)

    def Rf(tt):
        tt = np.asarray(tt, float)
        out = spl(np.clip(tt, t[0], t[-1]))
        return out if out.ndim else float(out)

    d = spl.derivative()

    def dRf(tt):
        tt = np.asarray(tt, float)
        out = d(np.clip(tt, t[0], t[-1]))
        return out if out.ndim else float(out)

    return Rf, dRf


# --------------------------------------------------------------------------
# output grids
# --------------------------------------------------------------------------
def output_radii_cm(dp: float = 0.1, rmax: float = 2.0) -> np.ndarray:
    n = int(round(rmax / dp))
    return np.round(np.arange(n + 1) * dp, 10)


def table_radii_cm(dr: float = 0.5, rmax: float = 2.0) -> np.ndarray:
    n = int(round(rmax / dr))
    return np.round(np.arange(n + 1) * dr, 10)
