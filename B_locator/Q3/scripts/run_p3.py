"""B 题问题 3：运行入口（转发到 ``src/p3_run.py``）。

本机 ``scripts/`` 目录存在 ACL 限制（子进程无法读取该目录下的文件），
所以真正可执行的实现放在 ``src/p3_run.py``；本文件只是保持目录约定的转发入口。

    python scripts/run_p3.py --mode mock --cases 10
    python src/p3_run.py     --mode mock --cases 10        # 等价的直接调用
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from p3_run import main  # noqa: E402

if __name__ == "__main__":
    main()
