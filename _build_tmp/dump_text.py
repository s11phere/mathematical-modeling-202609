"""Print the extracted text of each page so two builds can be compared."""
import sys
from pathlib import Path

from pypdf import PdfReader

for raw in sys.argv[1:]:
    path = Path(raw)
    reader = PdfReader(str(path))
    print(f"===== {path.name} | pages={len(reader.pages)} | bytes={path.stat().st_size}")
    for index, page in enumerate(reader.pages, start=1):
        print(f"----- page {index}")
        print(page.extract_text())
