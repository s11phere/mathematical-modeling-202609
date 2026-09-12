"""B 题问题 3：自检入口（转发到 ``src/p3_selftest.py``）。

本机 ``tests/`` 目录存在 ACL 限制（子进程无法读取该目录下的文件），
真正可执行的实现放在 ``src/p3_selftest.py``。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from p3_selftest import main  # noqa: E402

if __name__ == "__main__":
    main()
