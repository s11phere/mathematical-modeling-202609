"""Download a pure-python wheel from PyPI and unpack it, without pip."""
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

name = sys.argv[1]
target = Path(sys.argv[2]).resolve()
work = Path(__file__).resolve().parent
target.mkdir(parents=True, exist_ok=True)

url = f"https://pypi.org/pypi/{name}/json" if len(sys.argv) < 4 else f"https://pypi.org/pypi/{name}/{sys.argv[3]}/json"
with urllib.request.urlopen(url, timeout=60) as response:
    data = json.load(response)

version = data["info"]["version"]
wheel = next(
    (item for item in data["urls"] if item["packagetype"] == "bdist_wheel" and item["filename"].endswith("py3-none-any.whl")),
    None,
)
if wheel is None:
    raise SystemExit(f"no pure-python wheel for {name} {version}")

archive = work / wheel["filename"]
urllib.request.urlretrieve(wheel["url"], archive)
with zipfile.ZipFile(archive) as bundle:
    bundle.extractall(target)
print(f"{name} {version} -> {target}")
