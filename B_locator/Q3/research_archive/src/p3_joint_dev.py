"""Paired development batch, deliberately disjoint from final validation."""
import argparse
import json
from dataclasses import replace
from pathlib import Path
from p3_adaptive import AdaptiveConfig,AdaptiveRobot
from p3_joint import JointConfig,JointRobot
from p3_bench import run_one,summarize,fmt_row,load_base
from p3_adaptive_bench import make_scene

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cases',type=int,default=12)
    ap.add_argument('--scenario',default='random')
    ap.add_argument('--cfg',default='{}')
    ap.add_argument('--out',default='tmp/p3_joint_dev.json')
    args=ap.parse_args();base=load_base();out={}
    vs=[('adaptive',AdaptiveRobot,AdaptiveConfig()),
        ('joint',JointRobot,replace(JointConfig(),**json.loads(args.cfg)))]
    for name,cls,cfg in vs:
        reps=[]
        for i in range(args.cases):
            seed=20260913+100*i
            r=run_one(cls,cfg,make_scene(args.scenario,seed),base)
            r['seed']=seed;reps.append(r)
        out[name]=reps
        print(fmt_row(name,summarize(reps)),sum(r['complete_proof'] for r in reps),flush=True)
    Path(args.out).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

if __name__=='__main__':main()
