#!/usr/bin/env python3
"""附件调用器：转发到 research_archive 中的冻结实验驱动程序。"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "research_archive" / "scripts" / "run_p3_paper.py"
if __name__ == "__main__":
    raise SystemExit(subprocess.run([sys.executable, "-B", str(RUNNER), *sys.argv[1:]], cwd=ROOT).returncode)
