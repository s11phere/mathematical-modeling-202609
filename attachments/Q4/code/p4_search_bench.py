"""Paired offline evaluation for Q4 policies; truth is used only after exit."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np
from p3_arena import MockArena, MockSource
from p4_arena_ext import directed_case, make_arena
from p4_robot import P4Config, P4GridRobot


def scenario_arena(scenario, seed):
    if scenario in ('mixed', 'directed', 'omni'):
        return directed_case(seed, directed_frac={'mixed':.5,'directed':1.,'omni':0.}[scenario])[0]
    if scenario in ('uniform', 'mixed_uniform', 'minrange'):
        return directed_case(seed, directed_frac=.5 if scenario=='mixed_uniform' else 1.,
                             outward_frac=0.,r_recv=(1000.,1000.) if scenario=='minrange' else (1000.,1500.))[0]
    if scenario == 'edge':
        rng=np.random.default_rng(seed)
        sources=[]
        for ch in rng.choice(np.arange(1,21),size=int(rng.integers(10,17)),replace=False):
            a=rng.uniform(0,2*math.pi);r=rng.uniform(1750,1800)
            # In the protocol's station->source convention, this orientation
            # can be heard only on the outside half-plane.
            sources.append(MockSource(int(ch),r*math.cos(a),r*math.sin(a),1000.,
                                       cone_half=90.,dir_deg=math.degrees(a)+180.))
        return MockArena(seed=seed,sources=sources,budget_s=360000.)
    raise ValueError(scenario)


def policy_robot(name, arena, overrides=None):
    if name.startswith('legacy'):
        cfg=P4Config()
        if name=='legacy_l2':cfg.outer_rings=((1850.,9),)
        elif name=='legacy_l3':cfg.grid_a=1100.;cfg.outer_rings=((1900.,4),)
        elif name=='legacy_l4':cfg.outer_rings=()
        elif name=='legacy_l6':cfg.grid_a=1100.;cfg.outer_rings=()
        cls=P4GridRobot
    elif name=='homing':
        from p4_homing import P4HomingRobot,P4HomingConfig
        cls,cfg=P4HomingRobot,P4HomingConfig()
    else:
        from p4_search import P4SearchRobot, tier_config
        cls,cfg=P4SearchRobot,tier_config(name)
    for k,v in (overrides or {}).items():
        if not hasattr(cfg,k):raise ValueError(k)
        setattr(cfg,k,v)
    return cls(arena,cfg)


def run_one(name,scenario,seed,overrides=None,trace=False):
    a=scenario_arena(scenario,seed)
    rb=policy_robot(name,a,overrides)
    t=time.perf_counter();rep=rb.run()
    row=dict(policy=name,scenario=scenario,seed=seed,cleared=rep['cleared'],
             total=rep['n_sources'],exit_s=rep['virtual_time_s'],
             last_clear_s=rb.stats['vtime_at_last_clear'],travel_m=rep['travel_m'],
             measures=rep['n_measure'],clear_fail=rep['n_clear_fail'],
             rejected=rep['n_rejected'],runtime_s=time.perf_counter()-t,
             completion_certified=rep.get('completion_certified'),
             stations=rep.get('search_stations',len(rb.visited_stations)),
             config=asdict(rb.cfg))
    if trace:row['actions']=a.actions;row['truth']=a.truth();row['events']=rb.events
    return row


def summary(rows):
    out=[]
    for policy,scenario in sorted(set((r['policy'],r['scenario']) for r in rows)):
        rr=[r for r in rows if (r['policy'],r['scenario'])==(policy,scenario)]
        out.append(dict(policy=policy,scenario=scenario,cases=len(rr),
                        sources=sum(r['total'] for r in rr),
                        cleared=sum(r['cleared'] for r in rr),
                        rate=sum(r['cleared'] for r in rr)/sum(r['total'] for r in rr),
                        full=sum(r['cleared']==r['total'] for r in rr),
                        exit_s=float(np.mean([r['exit_s'] for r in rr])),
                        last_s=float(np.mean([r['last_clear_s'] for r in rr])),
                        travel_m=float(np.mean([r['travel_m'] for r in rr])),
                        measures=float(np.mean([r['measures'] for r in rr])),
                        fails=sum(r['clear_fail'] for r in rr),
                        runtime_s=float(np.mean([r['runtime_s'] for r in rr]))))
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--policies',default='legacy')
    ap.add_argument('--scenarios',default='mixed,uniform')
    ap.add_argument('--cases',type=int,default=12)
    ap.add_argument('--seed',type=int,default=20260914)
    ap.add_argument('--stride',type=int,default=100)
    ap.add_argument('--out',default='B_locator/Q4/out/p4_search_dev/baseline.jsonl')
    ap.add_argument('--overrides',default='{}')
    ap.add_argument('--trace',action='store_true')
    args=ap.parse_args();path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    files=['p4_search.py','p4_homing.py','p4_certificate.py','p4_robot.py',
           'p3_robot.py','p3_arena.py','p1_intersection.py','p4_arena_ext.py','p4_search_bench.py']
    root=Path(__file__).parent
    hashes={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
    path.with_suffix('.meta.json').write_text(json.dumps(dict(arguments=vars(args),files=hashes,
           started_unix_s=time.time()),indent=2),encoding='utf8')
    rows=[]
    with path.open('w',encoding='utf8') as f:
        for name in args.policies.split(','):
            for scenario in args.scenarios.split(','):
                for i in range(args.cases):
                    row=run_one(name,scenario,args.seed+args.stride*i,json.loads(args.overrides),args.trace)
                    rows.append(row);f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
                print(json.dumps(summary([r for r in rows if r['policy']==name and r['scenario']==scenario])[0],ensure_ascii=False),flush=True)
    path.with_suffix('.summary.json').write_text(json.dumps(summary(rows),indent=2),encoding='utf8')


if __name__=='__main__':main()
