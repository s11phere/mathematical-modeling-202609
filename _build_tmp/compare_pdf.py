"""Compare two PDFs: extracted text and raw bytes, ignoring reportlab date stamps."""
import difflib
import re
import sys
from pathlib import Path

from pypdf import PdfReader

left, right = (Path(item) for item in sys.argv[1:3])


def text_of(path: Path) -> list[str]:
    return [page.extract_text() for page in PdfReader(str(path)).pages]


left_text, right_text = text_of(left), text_of(right)
print(f"text identical: {left_text == right_text}  pages: {len(left_text)} vs {len(right_text)}")

if left_text != right_text:
    for line in difflib.unified_diff(left_text, right_text, "baseline", "rebuilt", lineterm=""):
        print(line)

date = re.compile(rb"D:\d{14}")
left_bytes, right_bytes = date.sub(b"D:<stamp>", left.read_bytes()), date.sub(b"D:<stamp>", right.read_bytes())
print(f"bytes identical ignoring date stamps: {left_bytes == right_bytes}")
print(f"sizes: {left.stat().st_size} vs {right.stat().st_size}")
print("stamps:", sorted(set(date.findall(left.read_bytes()))), sorted(set(date.findall(right.read_bytes()))))
