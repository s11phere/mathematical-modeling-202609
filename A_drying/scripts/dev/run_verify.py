# -*- coding: utf-8 -*-
"""Run one verification stage of scripts/verify.py: python scripts/run_verify.py <1|2|3>"""
import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location("verify", ROOT / "scripts" / "verify.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["verify"] = mod
spec.loader.exec_module(mod)

stage = sys.argv[1] if len(sys.argv) > 1 else "1"
t0 = time.time()
if stage == "1":
    mod.v1()
elif stage == "2":
    mod.v2()
elif stage == "3":
    mod.v3()
print(f"stage {stage} took {time.time()-t0:.1f} s")
print("FAILURES:", mod.FAIL)
