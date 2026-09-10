# -*- coding: utf-8 -*-
"""One-off patch: wire the surface djw/dT sensitivity into the temperature solve."""
from pathlib import Path
import ast

p = Path(__file__).resolve().parents[1] / "src" / "drying_solver.py"
s = p.read_text(encoding="utf-8")

s = s.replace(
    "    def _solve_T(self, props, h, T_old, C_lag, k_c, rcp_c, rd_new, R_eff, h_r,\n"
    "                 Tamb, Camb, jw):",
    "    def _solve_T(self, props, h, T_old, C_lag, k_c, rcp_c, rd_new, R_eff, h_r,\n"
    "                 Tamb, Camb, jw, djw_dT=0.0):",
)
s = s.replace(
    "            T_new = self._solve_T(props, h, T_old, C, k_c, rcp_c, rd_new,\n"
    "                                  R_eff, h_r, Tamb, Camb, jw0)",
    "            T_new = self._solve_T(props, h, T_old, C, k_c, rcp_c, rd_new,\n"
    "                                  R_eff, h_r, Tamb, Camb, jw0, djw_dT0)",
)
s = s.replace(
    "        Cs0, jw0, Ys0, dCs0, djw0 = self.surface_state(props, C_old, T_old, R_eff, Camb, Tamb)",
    "        Cs0, jw0, Ys0, dCs0, djw0 = self.surface_state(props, C_old, T_old, R_eff, Camb, Tamb)\n"
    "        # in the wet-bulb branch surface_state returns djw/dT_s in slot 5\n"
    "        djw_dT0 = djw0",
)
s = s.replace(
    "        jw = float(jw) + (djw_dT or 0.0) * 0.0\n",
    "",
)
ast.parse(s)
p.write_text(s, encoding="utf-8", newline="\n")
print("patched", p)
