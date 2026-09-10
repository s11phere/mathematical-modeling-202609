# -*- coding: utf-8 -*-
"""Best-effort text extraction from the legacy .doc format specification."""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "problems" / "format2026.doc"
OUT = ROOT / "workspace" / "A_drying" / "docs" / "format2026_extract.txt"


def main() -> int:
    b = SRC.read_bytes()
    txt = b.decode("utf-16-le", errors="ignore")
    pat = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffefA-Za-z0-9，。、；：（）%．·\-—《》\s]{12,}")
    chunks = [c.strip() for c in pat.findall(txt)]
    keep = [c for c in chunks if len(re.findall(r"[\u4e00-\u9fff]", c)) >= 6]
    OUT.write_text("\n".join(keep), encoding="utf-8")
    print(f"chunks kept: {len(keep)} -> {OUT}")
    for c in keep[:40]:
        print(repr(c[:160]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
