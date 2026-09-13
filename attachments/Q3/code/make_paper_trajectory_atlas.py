"""Render every frozen main-experiment scene as a five-policy atlas page.

This command reads paired_results.json and its existing trace files. It never
loads a policy class, reruns a simulation, or rewrites experiment records.

    python B_locator/Q3/research_archive/scripts/make_paper_trajectory_atlas.py
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from make_paper_figures import (DATA, MM, POLICIES, POLICY_COLOR, SCENE_LABEL,
                               draw_route, route_legend, setup_style)

SCENES = ["random", "annulus", "center", "hash", "worstrecv"]


def load_groups(data: Path) -> list[tuple[tuple[str, int, int], dict]]:
    records = json.loads((data / "paired_results.json").read_text(encoding="utf-8"))
    groups = defaultdict(dict)
    for row in records["rows"]:
        if row["split"] != "main":
            continue
        key = (row["scenario"], int(row["index"]), int(row["seed"]))
        policy = row["policy"]
        if policy in groups[key]:
            raise ValueError(f"Duplicate record for {key}/{policy}")
        groups[key][policy] = row
    for key, rows in groups.items():
        if set(rows) != set(POLICIES):
            raise ValueError(f"Incomplete five-policy group: {key}")
    return sorted(groups.items(), key=lambda x: (SCENES.index(x[0][0]), x[0][1], x[0][2]))


def load_traces(data: Path, rows: dict) -> dict:
    traces = {}
    for policy in POLICIES:
        source = Path(rows[policy]["trace_file"])
        if not source.is_absolute():
            source = data / source
        trace = json.loads(source.read_text(encoding="utf-8"))
        if trace["policy"] != policy:
            raise ValueError(f"Trace policy mismatch: {source}")
        traces[policy] = trace
    for field in ("scene_fingerprint", "error_fingerprint"):
        if len({t["scene_manifest"][field] for t in traces.values()}) != 1:
            raise ValueError(f"The five policies do not share {field}")
    return traces


def atlas_page(key: tuple[str, int, int], rows: dict, traces: dict, page: int, total: int):
    scenario, index, seed = key
    fig, axes = plt.subplots(2, 3, figsize=(297 * MM, 210 * MM))
    fig.subplots_adjust(left=.07, right=.97, bottom=.12, top=.82, wspace=.10, hspace=.72)
    for i, policy in enumerate(POLICIES):
        ax = axes.flat[i]
        draw_route(ax, traces[policy], POLICY_COLOR[policy], f"({chr(97+i)}) {policy}",
                   show_ylabel=(i % 3 == 0))
    ax = axes[1, 2]
    ax.axis("off")
    ax.text(.04, 1.12, "图例与读取说明", transform=ax.transAxes, fontsize=11, va="top")
    ax.legend(handles=route_legend(), loc="upper left", bbox_to_anchor=(.015, 1.02),
              frameon=False, fontsize=10, handlelength=1.4, labelspacing=.8)
    ax.text(.04, .33, "同页共用源位、接收半径及误差场。\n"
            "T 为从进入到退出的完整虚拟时间；\n"
            "L 为动作账本记录的总行程。\n"
            "源位仅在退出之后用于绘图。\n"
            "未全清的运行照常保留。", transform=ax.transAxes,
            fontsize=9.5, va="top", linespacing=1.6)
    fig.text(.5, .955, "问题三补充材料：五策略同场景轨迹对照", ha="center", fontsize=16)
    fig.text(.5, .908, f"{SCENE_LABEL.get(scenario, scenario)} · 第 {index+1} 组 · seed {seed}",
             ha="center", fontsize=12)
    fig.text(.07, .025, f"冻结记录：main_{scenario}_{index:03d}_{seed}_<policy>.json",
             fontsize=8.5, color="#626d78")
    fig.text(.97, .025, f"{page} / {total}", ha="right", fontsize=9.5)
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--out", type=Path, default=DATA / "supplementary_trajectories.pdf")
    args = parser.parse_args()
    setup_style()
    groups = load_groups(args.data)
    if len(groups) != 120:
        raise ValueError(f"Expected 120 main-experiment scenes, found {len(groups)}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(args.out, metadata={"Title": "Q3 Supplementary Trajectories",
                                     "Subject": "120 frozen paired scenes; five policies per page",
                                     "Author": "", "CreationDate": None, "ModDate": None}) as pdf:
        for page, (key, rows) in enumerate(groups, 1):
            traces = load_traces(args.data, rows)
            fig = atlas_page(key, rows, traces, page, len(groups))
            pdf.savefig(fig)
            plt.close(fig)
            if page % 20 == 0:
                print(f"Rendered {page}/{len(groups)} frozen scenes", flush=True)
    print(args.out)


if __name__ == "__main__":
    main()
