#!/usr/bin/env python3
"""问题三独立复现：只读审计、9 次试运行、制图制表或完整 680 次实验。"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code"))
from package_runtime import FROZEN, load_runner, render_all, verify_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--audit-only", action="store_true", help="独立重算已保存的 680 局动作和覆盖证书")
    modes.add_argument("--smoke", action="store_true", help="同一场景的五策略及四项消融，共 9 次")
    modes.add_argument("--figures", action="store_true", help="读取冻结数据重绘 5 幅正文图、140 页图册及表格")
    modes.add_argument("--full", action="store_true", help="完整重跑 600 次主实验及 80 次消融")
    parser.add_argument("--out", type=Path, help="新输出目录；审计未指定时自动创建临时目录")
    parser.add_argument("--font", type=Path, help="可选中文字体路径；默认使用 ../fonts/simsun.ttc")
    parser.add_argument("--max-new-runs", type=int, default=0, help="完整实验分批运行时的新增运行上限")
    args = parser.parse_args()
    if not args.out and not args.audit_only:
        parser.error("--smoke、--figures、--full 必须指定 --out DIR，以保护论文冻结结果")
    out = (args.out or Path(tempfile.mkdtemp(prefix="q3-audit-"))).expanduser().resolve()
    if out == ROOT or out.is_relative_to(ROOT):
        parser.error("--out 必须位于 Q3 附件目录之外，冻结附件保持只读")
    print(json.dumps(verify_package(), ensure_ascii=False), flush=True)
    if args.figures:
        out.mkdir(parents=True, exist_ok=True)
        render_all(out, args.font)
    else:
        runner = load_runner()
        if args.audit_only:
            if out.exists() and any(out.iterdir()):
                parser.error("审计的 --out 必须为空目录，避免覆盖已有复现结果")
            out.mkdir(parents=True, exist_ok=True)
            for name in ("paired_results.json", "summary.json", "audit_report.json"):
                shutil.copy2(FROZEN / name, out / name)
            shutil.copytree(FROZEN / "traces", out / "traces")
            historical = runner.read_json(FROZEN / "manifest.json")
            manifest = runner.make_manifest()
            manifest.update({"experiment_id": historical["experiment_id"],
                "replay_of_frozen_definition": historical["definition_fingerprint"],
                "portable_definition_note": "Algorithm bytes, parameters and fields match the frozen experiment; "
                    "unused historical diagnostic modules are excluded from the portable dependency fingerprint."})
            rows = runner.read_json(out / "paired_results.json")["rows"]
            runner.audit_all(out, rows, manifest)
            report = runner.read_json(out / "audit_report.json")
            if not (report["action_audit_pass"] == report["truth_guard_pass"] ==
                    report["scene_fingerprint_pass"] == len(rows) and
                    report["all_raw_payloads_unchanged"] and
                    not report["configuration_mismatches"] and not report["pairing_mismatches"] and
                    report["static_policy_audit"]["audit_ok"] and
                    all(report["audit_contract_checks"].values())):
                raise RuntimeError("独立审计未全部通过，详见新输出目录。")
            coverage = report["coverage"]
            if not (coverage["runs"] == coverage["numerical_pass"] == coverage["cell_certificate_pass"]):
                raise RuntimeError("覆盖复核未全部通过。")
        else:
            argv = ["--out", str(out)]
            if args.smoke:
                argv += ["--smoke"]
            if args.max_new_runs:
                argv += ["--max-new-runs", str(args.max_new_runs)]
            runner.main(argv)
    print(f"复现输出：{out}", flush=True)
    print("论文冻结 results/ 未被改写。", flush=True)


if __name__ == "__main__":
    main()
