# -*- coding: utf-8 -*-
"""
Diagnostic: is the problem-1 parameter set internally consistent?

Compares three closures for the convective mass transfer coefficient

  (A) literal      : h_m = 8e-7 m/s with a concentration driving force
                     rho_d (C_surface - C_inf)
  (B) Lewis        : h_m = h / (rho_air cp_air Le^(2/3)) ~ 2.8e-4 m/s, driving
                     force Y_sat(T_surface) - Y_inf
  (C) heat-limited : surface at the wet-bulb temperature, jw = h (T_inf - T_wb)/Lw

and reports the implied evaporation rate, the surface temperature and the water
loss over the 1800 s preheating phase.

Run: python scripts/diag_consistency.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drying_solver import Props, DryerSolver1D, c2k, k2c  # noqa: E402

P_ATM = 101325.0
RHO_AIR = 1.13
CP_AIR = 1006.0
LEWIS = 0.87
H_M_LEWIS = 25.0 / (RHO_AIR * CP_AIR * LEWIS ** (2.0 / 3.0))


def p_sat(T):
    """Saturation vapour pressure over water [Pa] (Buck 1981)."""
    Tc = np.asarray(T, float) - 273.15
    return 611.21 * np.exp((18.678 - Tc / 234.5) * (Tc / (257.14 + Tc)))


def Y_sat(T, P=P_ATM):
    """Saturation humidity ratio [kg water/kg dry air]."""
    ps = p_sat(T)
    return 0.62198 * ps / (P - ps)


print("=== parameter consistency of the mass-transfer closure ===")
h, Lw, rd, R = 25.0, 2.26e6, 820.0 / (1.0 + 2.55), 0.02
hm_given, hm_lewis = 8e-7, 0.0  # placeholder
hm_lewis = 25.0 / (RHO_AIR * CP_AIR * LEWIS ** (2.0 / 3.0))
print(f"h_m given        = {hm_given:.3e} m/s")
print(f"h_m Lewis        = {hm_lewis:.3e} m/s   (ratio {hm_lewis/hm_given:.0f}x)")

Tamb, Yamb = c2k(28.0), 0.01963
Yamb_psychro = 0.62198 * (0.85 * float(p_sat(Tamb))) / (P_ATM - 0.85 * float(p_sat(Tamb)))
print(f"Y_inf given      = {Yamb:.5f} kg/kg ; 85% RH at 28 C -> {Yamb_psychro:.5f} kg/kg "
      f"(relative deviation {abs(Yamb-Yamb_psychro)/Yamb_psychro*100:.1f}%)")

# (A) literal closure with the *material* surface moisture
Cs = 2.55
jw_A = hm_given * rd * (Cs - Yamb)
print(f"\n(A) literal   jw = {jw_A:.4e} kg/(m2 s);  evaporative heat {Lw*jw_A:8.1f} W/m2")
print(f"    convective supply at T_s = T_inf        : {0.0:8.1f} W/m2")
print(f"    required surface depression dT = Lw jw / h = {Lw*jw_A/h:.1f} K  -> "
      f"T_s = {k2c(Tamb - Lw*jw_A/h):.1f} degC")

# (B) Lewis closure with the saturated surface humidity
Ts = Tamb
for _ in range(200):
    jw = hm_lewis * (float(Y_sat(Ts)) - Yamb) * RHO_AIR
    Ts_new = Tamb - Lw * jw / h
    if abs(Ts_new - Ts) < 1e-9:
        Ts = Ts_new
        break
    Ts = 0.5 * (Ts + Ts_new)
jw_B = hm_lewis * (float(Y_sat(Ts)) - Yamb) * RHO_AIR
print(f"\n(B) Lewis     jw = {jw_B:.4e} kg/(m2 s);  evaporative heat {Lw*jw_B:8.1f} W/m2")
print(f"    self-consistent T_s = {k2c(Ts):.3f} degC (wet-bulb), "
      f"Y_sat = {float(Y_sat(Ts)):.5f} kg/kg")

# (C) heat-limited bound
jw_C = h * (Tamb - Ts) / Lw / 10.0   # not used, informational
print(f"\n    energy needed to heat the sample from 28 to 50 C: "
      f"{np.pi*R**2*(820.0*2600.0)*(50-28)/1000:.1f} kJ/m")
print(f"    heat available at 25 W/m2K over 1800 s with dT = 22 K: "
      f"{25*22*2*np.pi*R*1800/1000:.1f} kJ/m")
