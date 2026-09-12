"""Small paired development benchmark for the experimental homing policy."""
import json
from dataclasses import replace
from pathlib import Path
from p3_homing import HomingRobot, HomingConfig
from p3_tour import TourRobot, TourConfig
from p3_bench import run_one, summarize, fmt_row, load_base, MockArena, outer_annulus, center_cluster

if __name__ == '__main__':
    base=load_base()
    result={}
    variants=[('tour',TourRobot,TourConfig()),('homing',HomingRobot,HomingConfig())]
    for scenario,make in [('random',MockArena),('annulus',outer_annulus),('center',center_cluster)]:
        result[scenario]={}
        for name,cls,cfg in variants:
            reps=[]
            for i in range(20):
                seed=20260913+100*i
                r=run_one(cls,cfg,make(seed=seed),base,want_path=True)
                r['seed']=seed
                reps.append(r)
            result[scenario][name]=reps
            print(scenario,fmt_row(name,summarize(reps)),flush=True)
    dest=Path(__file__).resolve().parents[1] / 'out/p3_homing_dev.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
