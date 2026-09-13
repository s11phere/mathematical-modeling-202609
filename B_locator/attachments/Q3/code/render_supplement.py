"""Complete trajectory evidence: 120 paired scenes and 20 ablation scenes."""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def render(output: Path, data: Path, figures):
    import make_paper_trajectory_atlas as atlas
    atlas.setup_style = figures.setup_style
    groups = atlas.load_groups(data)
    if len(groups) != 120:
        raise ValueError(f"Expected 120 paired scenes; found {len(groups)}")
    rows = json.loads((data / "paired_results.json").read_text())["rows"]
    baseline = {r["index"]: r for r in rows if r["split"] == "main" and
                r["scenario"] == "random" and r["policy"] == "joint" and r["index"] < 20}
    ablations = {}
    for row in rows:
        if row["split"] == "ablation":
            ablations.setdefault(row["index"], {})[row["policy"]] = row
    choices = [
        ("joint", "完整 joint", "#118a8c"),
        ("joint_no_after_service", "取消清后扫描", "#667085"),
        ("joint_single_plan", "单方案规划", "#3b82a0"),
        ("joint_no_cover_polish", "取消测站精修", "#7656a6"),
        ("joint_no_probability_gate", "取消概率门槛", "#b7791f"),
    ]
    if set(ablations) != set(range(20)):
        raise ValueError("The complete 20-case ablation evidence is required")
    output.parent.mkdir(parents=True, exist_ok=True)
    figures.setup_style()
    with PdfPages(output, metadata={"Title": "问题三完整补充轨迹图册",
            "Subject": "120 组五策略配对场景 + 20 组单因素消融场景；680 份原始日志",
            "Author": "", "CreationDate": None, "ModDate": None}) as pdf:
        for page, (key, grouped) in enumerate(groups, 1):
            traces = atlas.load_traces(data, grouped)
            fig = atlas.atlas_page(key, grouped, traces, page, 140)
            pdf.savefig(fig)
            plt.close(fig)
            if page % 20 == 0:
                print(f"补充图册：{page}/140 页", flush=True)
        for index in range(20):
            grouped = {"joint": baseline[index], **ablations[index]}
            traces = {policy: json.loads((data / grouped[policy]["trace_file"]).read_text())
                      for policy, _, _ in choices}
            for field in ("scene_fingerprint", "error_fingerprint"):
                if len({t["scene_manifest"][field] for t in traces.values()}) != 1:
                    raise ValueError(f"Ablation {index}: unpaired {field}")
            fig, axes = plt.subplots(2, 3, figsize=(297 * figures.MM, 210 * figures.MM))
            fig.subplots_adjust(left=.07, right=.97, bottom=.12, top=.82, wspace=.10, hspace=.72)
            for i, (policy, label, color) in enumerate(choices):
                figures.draw_route(axes.flat[i], traces[policy], color,
                    f"({chr(97+i)}) {label}", show_ylabel=(i % 3 == 0))
            ax = axes[1, 2]
            ax.axis("off")
            ax.text(.04, 1.12, "图例与读取说明", transform=ax.transAxes, fontsize=11, va="top")
            ax.legend(handles=figures.route_legend(), loc="upper left", bbox_to_anchor=(.015, 1.02),
                      frameon=False, fontsize=10, handlelength=1.4, labelspacing=.8)
            ax.text(.04, .33, "完整 joint 与四项单因素消融。\n每次仅取消一个模块，其他参数相同。\n"
                    "源位、接收半径及误差场保持一致。\nT 为完整退出时间，L 为总行程。\n"
                    "源位仅在退出后用于绘图。", transform=ax.transAxes,
                    fontsize=9.5, va="top", linespacing=1.6)
            seed = baseline[index]["seed"]
            fig.text(.5, .955, "问题三补充材料：联合调度的单因素消融", ha="center", fontsize=16)
            fig.text(.5, .908, f"随机场景 · 第 {index+1} 组 · seed {seed}", ha="center", fontsize=12)
            fig.text(.07, .025, f"原始记录：results/traces/；random_{index:03d}_{seed}_<policy>.json",
                     fontsize=8.5, color="#626d78")
            fig.text(.97, .025, f"{121+index} / 140", ha="right", fontsize=9.5)
            pdf.savefig(fig)
            plt.close(fig)
    print(f"补充图册：140/140 页；{output}", flush=True)
