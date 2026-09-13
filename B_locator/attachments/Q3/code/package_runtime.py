"""Portable paths and output protection for the unchanged paper experiment.

Only filesystem/reporting concerns are adapted. Algorithm classes, simulator
rules, all policy configurations, seeds, scene generation and audit arithmetic
are imported without editing the original source bytes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
DATA = ROOT / "data"
FROZEN = ROOT / "results"
DEPENDENCIES = (
    "p1_intersection.py", "p2_grid_expectation.py", "p3_adaptive.py",
    "p3_adaptive_bench.py", "p3_arena.py", "p3_bench.py", "p3_coverage.py",
    "p3_expect_field.py", "p3_frontier.py", "p3_homing.py", "p3_joint.py",
    "p3_robot.py", "p3_sweep.py", "p3_tour.py",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_package():
    manifest = json.loads((ROOT / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    checked = 0
    for relative, record in manifest["files"].items():
        path = ROOT / relative
        if not path.is_file() or sha(path) != record["sha256"]:
            raise RuntimeError(f"附件文件缺失或 SHA256 不一致：{relative}")
        checked += 1
    historical = json.loads((FROZEN / "manifest.json").read_text(encoding="utf-8"))
    for filename in DEPENDENCIES:
        expected = historical["source_sha256"]["src/" + filename]
        if sha(CODE / filename) != expected:
            raise RuntimeError(f"算法与论文冻结记录不一致：{filename}")
    expected_fields = historical["field_sha256"]
    for old_path, expected in expected_fields.items():
        if sha(DATA / Path(old_path).name) != expected:
            raise RuntimeError(f"期望场与论文冻结记录不一致：{old_path}")
    return {"package_files_verified": checked,
            "frozen_algorithm_dependencies_verified": len(DEPENDENCIES),
            "frozen_field_files_verified": len(expected_fields)}


def load_runner():
    sys.path.insert(0, str(CODE))
    # These values are read into load_base's default arguments at import time.
    import p3_expect_field as field
    field.DEFAULT_BASE_CSV = str(DATA / "p2_grid_map.csv")
    field.DEFAULT_FAMILY_DIR = str(DATA)
    import run_p3_paper as runner
    runner.Q3, runner.SRC = ROOT, CODE
    runner.OUT_DEFAULT = ROOT / "reproduction"

    original_inputs = runner.frozen_inputs
    def inputs():
        _, _, configs = original_inputs()
        sources = {"code/" + name: sha(CODE / name) for name in DEPENDENCIES}
        fields = {"data/" + p.name: sha(p) for p in sorted(DATA.glob("p2_grid*.csv"))}
        fields["data/p2_grid_family.json"] = sha(DATA / "p2_grid_family.json")
        return sources, fields, configs
    runner.frozen_inputs = inputs

    # The old archival hook used a repository-wide scratch path. A portable
    # package never moves evidence; unreferenced output logs are rejected.
    def archive_scratch(outdir, rows):
        refs = {(outdir / row["trace_file"]).resolve() for row in rows}
        extra = [p for p in (outdir / "traces").glob("*.json") if p.resolve() not in refs]
        if extra:
            raise RuntimeError("输出目录存在不属于本实验的动作日志，请使用新目录。")
        return []
    runner.archive_scratch = archive_scratch

    def snapshot_sources(outdir, manifest):
        hashes = {**manifest["source_sha256"], **manifest["field_sha256"],
                  "code/run_p3_paper.py": sha(CODE / "run_p3_paper.py"),
                  "code/package_runtime.py": sha(CODE / "package_runtime.py"),
                  "reproduce.py": sha(ROOT / "reproduce.py")}
        for relative, expected in hashes.items():
            source, dest = ROOT / relative, outdir / "source_snapshot" / relative
            if sha(source) != expected:
                raise RuntimeError(f"运行中输入变化：{relative}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        runner.atomic_json(outdir / "source_snapshot/SHA256.json", hashes)
        return len(hashes)
    runner.snapshot_sources = snapshot_sources

    # Preserve line numbers but make source references resolve in this package.
    original_static = runner.static_policy_audit
    def static_audit():
        obj = original_static()
        def adapt(value):
            if isinstance(value, dict):
                return {k: adapt(v) for k, v in value.items()}
            if isinstance(value, list):
                return [adapt(v) for v in value]
            if isinstance(value, str) and value.startswith("src/"):
                return "code/" + value[4:]
            return value
        return adapt(obj)
    runner.static_policy_audit = static_audit
    original_readme = runner.write_readme_and_evidence
    def write_readme(outdir, summary, audit, manifest):
        original_readme(outdir, summary, audit, manifest)
        (outdir / "README.md").write_text(
            "# 问题三新复现输出\n\n本目录由独立评审附件生成，不是论文冻结数据。\n"
            "输入、算法和统计口径见附件根目录 DATA_SOURCES.md。\n"
            "paired_results.json/.csv 保存逐局结果，summary.json 保存汇总，"
            "audit_report.json 和 coverage_audit.json 保存独立审计。\n"
            "traces/ 保留动作日志，source_snapshot/ 记录本次所用依赖及其哈希。\n",
            encoding="utf-8")
    runner.write_readme_and_evidence = write_readme
    return runner


def configure_figures(font_path=None):
    import make_paper_figures as figures
    figures.DATA = FROZEN
    def style():
        import matplotlib
        from matplotlib import font_manager
        font = Path(font_path).expanduser().resolve() if font_path else ROOT.parent / "fonts/simsun.ttc"
        if not font.exists():
            raise FileNotFoundError("中文字体不存在，请保留附件 fonts/ 或指定 --font PATH")
        font_manager.fontManager.addfont(str(font))
        cjk = font_manager.FontProperties(fname=font).get_name()
        latin = Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf")
        if latin.exists():
            font_manager.fontManager.addfont(str(latin))
        families = ["Times New Roman" if latin.exists() else "STIXGeneral", cjk]
        matplotlib.rcParams.update({
            "font.family": families, "mathtext.fontset": "cm", "font.size": 9.0,
            "axes.titlesize": 9.2, "axes.labelsize": 9.0, "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5, "legend.fontsize": 8.5, "font.style": "normal",
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.unicode_minus": False, "pdf.fonttype": 42, "ps.fonttype": 42,
        })
    figures.setup_style = style
    return figures


def render_all(outdir, font_path=None, include_supplement=True):
    figures = configure_figures(font_path)
    figures.OUT = outdir / "figures"
    figures.OUT.mkdir(parents=True, exist_ok=True)
    figures.setup_style()
    _, rows = figures.load_data(FROZEN)
    figures.fig1_geometry(rows, FROZEN)
    figures.fig2_field_sweep_tour(rows, FROZEN)
    figures.fig3_tour_adaptive_joint(rows, FROZEN)
    figures.fig4_cost_and_clear(rows, FROZEN)
    figures.fig5_scenarios_ablation(rows)
    import make_paper_tables as tables
    tables.DATA = outdir / "tables"
    tables.DATA.mkdir(parents=True, exist_ok=True)
    tables.SECTIONS = tables.DATA
    # The legacy table renderer writes one provenance JSON beside its inputs.
    # Supply a small independent working copy; link trace reads to frozen data.
    records = json.loads((FROZEN / "paired_results.json").read_text())
    for row in records["rows"]:
        row["trace_file"] = str((FROZEN / row["trace_file"]).resolve())
    (tables.DATA / "paired_results.json").write_text(json.dumps(records), encoding="utf-8")
    shutil.copy2(FROZEN / "summary.json", tables.DATA / "summary.json")
    tables.main()
    # Preserve portable generated tables without redundant input rows carrying
    # machine-specific absolute paths. Record their real frozen input hashes.
    (tables.DATA / "paired_results.json").unlink()
    (tables.DATA / "summary.json").unlink()
    provenance = json.loads((tables.DATA / "table_provenance.json").read_text())
    provenance.update({"data_sha256": sha(FROZEN / "paired_results.json"),
                       "summary_sha256": sha(FROZEN / "summary.json"),
                       "data_source": "Q3/results/paired_results.json",
                       "summary_source": "Q3/results/summary.json"})
    (tables.DATA / "table_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    if include_supplement:
        from render_supplement import render
        render(outdir / "supplement.pdf", FROZEN, figures)
