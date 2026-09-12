#!/usr/bin/env python3
"""Q3 复现入口。

默认重放已保存的动作并执行独立审计；传入 ``--smoke`` 可运行一局离线演练，
传入 ``--out PATH`` 可将完整重跑结果写入新的目录。冻结实验驱动程序保存在
``research_archive/scripts``，这里仅作稳定的附件入口。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "research_archive" / "scripts" / "run_p3_paper.py"


def main() -> int:
    if not RUNNER.exists():
        raise SystemExit(f"missing frozen runner: {RUNNER}")
    cmd = [sys.executable, "-B", str(RUNNER), *sys.argv[1:]]
    return subprocess.run(cmd, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
