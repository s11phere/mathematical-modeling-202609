"""Development/evaluation harness for the second Q4 optimization round."""
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from p4_search_bench import scenario_arena,policy_robot


def robot_for(policy,arena,overrides=None):
    if policy.startswith('compact_') and policy!='compact_v2':
        from p4_compact import P4CompactRobot,compact_config
        cfg=compact_config(policy.removeprefix('compact_'))
        for key,value in (overrides or {}).items():
            if not hasattr(cfg,key):raise ValueError(key)
            setattr(cfg,key,value)
        rb=P4CompactRobot(arena,cfg)
    elif policy=='adaptive':
        from p4_adaptive_cover import P4AdaptiveRobot,P4AdaptiveConfig
        rb=P4AdaptiveRobot(arena,P4AdaptiveConfig(**(overrides or {})))
    elif policy=='compact_v2':
        from p4_compact import P4CompactRobot,P4CompactConfig
        rb=P4CompactRobot(arena,P4CompactConfig(**(overrides or {})))
    elif policy=='polish':
        from p4_polish import P4PolishRobot,P4PolishConfig
        rb=P4PolishRobot(arena,P4PolishConfig(**(overrides or {})))
    elif policy=='service':
        from p4_service_v2 import P4ServiceRobot,P4ServiceConfig
        rb=P4ServiceRobot(arena,P4ServiceConfig(**(overrides or {})))
    else:rb=policy_robot(policy,arena,overrides)
    return rb


def run_case(policy,scenario,seed,overrides=None,trace=False):
    arena=scenario_arena(scenario,seed);rb=robot_for(policy,arena,overrides)
    t=time.perf_counter();rep=rb.run()
    row=dict(policy=policy,scenario=scenario,seed=seed,cleared=rep['cleared'],total=rep['n_sources'],
             exit_s=rep['virtual_time_s'],last_s=rb.stats['vtime_at_last_clear'],
             travel_m=rep['travel_m'],measures=rep['n_measure'],failures=rep['n_clear_fail'],
             rejected=rep['n_rejected'],certified=rep.get('completion_certified'),
             runtime_s=time.perf_counter()-t,config=asdict(rb.cfg))
    if trace:row.update(actions=arena.actions,truth=arena.truth())
    return row


def summarize(rows):
    per_source=[r['exit_s']/r['cleared'] for r in rows if r['cleared']]
    last_per_source=[r['last_s']/r['cleared'] for r in rows if r['cleared']]
    return dict(cases=len(rows),sources=sum(r['total'] for r in rows),cleared=sum(r['cleared'] for r in rows),
                full=sum(r['cleared']==r['total'] for r in rows),certified=sum(r['certified'] is True for r in rows),
                exit_s=float(np.mean([r['exit_s'] for r in rows])),
                exit_per_source=float(np.mean(per_source)) if per_source else None,
                last_per_source=float(np.mean(last_per_source)) if last_per_source else None,
                travel_m=float(np.mean([r['travel_m'] for r in rows])),
                measures=float(np.mean([r['measures'] for r in rows])),runtime_s=float(np.mean([r['runtime_s'] for r in rows])))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--policies',default='strict,adaptive')
    ap.add_argument('--scenarios',default='mixed_uniform,uniform')
    ap.add_argument('--cases',type=int,default=12)
    ap.add_argument('--seed',type=int,default=20260914)
    ap.add_argument('--stride',type=int,default=100)
    ap.add_argument('--overrides',default='{}')
    ap.add_argument('--out',default='B_locator/Q4/out/p4_improve_dev/initial.jsonl')
    ap.add_argument('--trace',action='store_true')
    args=ap.parse_args();p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True)
    hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(__file__).parent.glob('p4_*.py')}
    p.with_suffix('.meta.json').write_text(json.dumps(dict(args=vars(args),files=hashes),indent=2),encoding='utf8')
    results=[]
    with p.open('w',encoding='utf8') as f:
        for policy in args.policies.split(','):
            for scenario in args.scenarios.split(','):
                rows=[]
                for i in range(args.cases):
                    r=run_case(policy,scenario,args.seed+i*args.stride,json.loads(args.overrides),args.trace)
                    f.write(json.dumps(r)+'\n');f.flush();rows.append(r)
                result=dict(policy=policy,scenario=scenario,**summarize(rows));results.append(result)
                print(json.dumps(result),flush=True)
    p.with_suffix('.summary.json').write_text(json.dumps(results,indent=2),encoding='utf8')


if __name__=='__main__':main()
