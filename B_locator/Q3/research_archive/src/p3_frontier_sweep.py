"""Small paired-seed screen for the experimental dynamic-covering planner."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from p3_arena import MockArena
from p3_bench import LIVE1, LIVE2, arena_from, center_cluster, outer_annulus, run_one, summarize
from p3_frontier import FrontierConfig, FrontierRobot, OriginalTourRobot, original_config
from p3_robot import load_base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--step", type=int, default=100)
    ap.add_argument("--scenarios", default="random,annulus")
    ap.add_argument("--json-out", default="tmp/frontier_sweep.json")
    args = ap.parse_args()
    base = load_base()
    makers = {"random": lambda s: MockArena(seed=s), "annulus": outer_annulus,
              "center": center_cluster, "live1": lambda s: arena_from(LIVE1, seed=s),
              "live2": lambda s: arena_from(LIVE2, seed=s)}
    variants = [("original", OriginalTourRobot, original_config())]
    variants.extend([
        ("dynamic_cover", FrontierRobot, FrontierConfig()),
        ("dynamic_cover_linear_gain", FrontierRobot,
         replace(FrontierConfig(), gain_power=1.0)),
        ("dynamic_cover_with_enroute", FrontierRobot,
         replace(FrontierConfig(), enroute_spacing_m=200.0)),
    ])
    result = {"arguments": vars(args), "results": {}}
    for name, cls, cfg in variants:
        all_reps = []
        by_scenario = {}
        for scenario in args.scenarios.split(","):
            reps = [run_one(cls, cfg, makers[scenario](args.seed + args.step * i), base)
                    for i in range(args.cases)]
            all_reps.extend(reps)
            by_scenario[scenario] = summarize(reps)
            by_scenario[scenario]["proof"] = sum(r["complete_proof"] for r in reps)
        summary = summarize(all_reps)
        summary["proof"] = sum(r["complete_proof"] for r in all_reps)
        print(name, "t=", round(summary["vtime_s"], 1), "T/N=",
              round(summary["avg_clear_time_s"], 1), "full=", summary["full_clear_cases"],
              "proof=", summary["proof"], by_scenario, flush=True)
        result["results"][name] = {"config": asdict(cfg), "summary": summary,
                                    "by_scenario": by_scenario}
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
