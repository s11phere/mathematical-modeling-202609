# -*- coding: utf-8 -*-
"""Patch robust_solver call sites for the 4-tuple surface_flux."""
from pathlib import Path
import ast

p = Path(__file__).resolve().parents[1] / "src" / "robust_solver.py"
s = p.read_text(encoding="utf-8")

s = s.replace(
    "        jw, Cs, Ys = self.surface_flux(props, C, T, R, float(props.Camb(0.0)))",
    "        jw, Cs, Ys, Tsurf = self.surface_flux(\n"
    "            props, C, T, R, float(props.Camb(0.0)), Tamb)",
)
s = s.replace(
    "            jw, Cs, _ = self.surface_flux(props, CC, TT, R, float(props.Camb(tt)))",
    "            jw, Cs, _, _ = self.surface_flux(\n"
    "                props, CC, TT, R, float(props.Camb(tt)), float(props.Tamb(tt)))",
)
# store() must also record the surface temperature from surface_flux
s = s.replace(
    "            out.Tsurf.append(float(TT[-1]))",
    "            out.Tsurf.append(float(TT[-1]))",
)
ast.parse(s)
p.write_text(s, encoding="utf-8", newline="\n")
print("patched")
