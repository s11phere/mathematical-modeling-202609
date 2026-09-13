"""Prepare the portable problem-three review package from frozen evidence."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "paper").is_dir() and (p / "Q3").is_dir())
SOURCE = ROOT / "Q3"
ARCHIVE = SOURCE / "research_archive"
TARGET = ROOT / "attachments/Q3"
ENTRIES = {}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, relative):
    target = TARGET / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    ENTRIES[relative] = {"source": str(source.relative_to(ROOT.parent)),
                         "source_sha256": sha(source), "sha256": sha(target),
                         "adaptation": "none; byte-for-byte copy"}


def main():
    for name in ("code", "data", "results", "figures"):
        (TARGET / name).mkdir(parents=True, exist_ok=True)
    algorithms = sorted(p for p in (SOURCE / "code").glob("*.py") if p.name != "run_p3_paper.py")
    for source in algorithms:
        copy(source, "code/" + source.name)
    for name in ("p2_grid_expectation.py", "p3_selftest.py", "p3_adaptive_checks.py", "p3_joint_checks.py"):
        copy(ARCHIVE / "src" / name, "code/" + name)
    for name in ("run_p3_paper.py", "make_paper_figures.py", "make_paper_tables.py", "make_paper_trajectory_atlas.py"):
        copy(ARCHIVE / "scripts" / name, "code/" + name)
    for source in sorted((SOURCE / "data").glob("p2_grid*")):
        copy(source, "data/" + source.name)
    copy(ARCHIVE / "out/p2_grid/p2_grid_report.json", "data/p2_grid_report.json")
    frozen = ARCHIVE / "out/paper_q3"
    for name in ("paired_results.json", "paired_results.csv", "summary.json", "manifest.json",
                 "audit_report.json", "coverage_audit.json", "evidence_map.json", "table_provenance.json",
                 "selftest.txt", "adaptive_checks.txt", "joint_checks.txt"):
        copy(frozen / name, "results/" + name)
    rows = json.loads((frozen / "paired_results.json").read_text())["rows"]
    for row in rows:
        copy(frozen / row["trace_file"], "results/" + row["trace_file"])
    assert len(rows) == 680
    for source in sorted((ROOT / "paper/figures").glob("q3-*")):
        if source.suffix in (".pdf", ".png"):
            copy(source, "figures/" + source.name)
    old = json.loads((frozen / "manifest.json").read_text())
    for key, entry in ENTRIES.items():
        name = Path(key).name
        if key.startswith("code/") and "src/" + name in old["source_sha256"]:
            assert entry["sha256"] == old["source_sha256"]["src/" + name], key
            entry["frozen_manifest_key"] = "src/" + name
    previous_path = TARGET / "SOURCE_MANIFEST.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    for path in sorted(TARGET.rglob("*")):
        if not path.is_file() or path == previous_path:
            continue
        relative = str(path.relative_to(TARGET))
        if relative not in ENTRIES:
            entry = previous.get("files", {}).get(relative, {
                "source": "Generated for the portable review package",
                "adaptation": "Authored from frozen evidence; no algorithm modifications",
            }).copy()
            entry["sha256"] = sha(path)
            ENTRIES[relative] = entry
    manifest = {
        "package": "Problem 3 portable review materials", "schema": "review-package-v1",
        "original_experiment_id": old["experiment_id"],
        "original_definition_fingerprint": old["definition_fingerprint"],
        "files": ENTRIES,
        "path_adaptation": "The original algorithms and reporting scripts are byte-for-byte copies. "
            "code/package_runtime.py supplies code/data/results locations at import time; the public "
            "reproduce.py protects frozen results and directs every generated file to a separate output directory. "
            "Historical src/ paths in results/manifest.json map to code/ for included files; old diagnostic "
            "modules that are not needed by the experiment are intentionally excluded. The portable execution "
            "manifest hashes only the included dependency set and has a separate definition fingerprint. "
            "Shared Chinese font: ../fonts/simsun.ttc; a --font argument can supply a font if Q3 is moved alone.",
    }
    (TARGET / "SOURCE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Copied {len(ENTRIES)} files; {len(rows)} frozen action logs.")


if __name__ == "__main__":
    main()
