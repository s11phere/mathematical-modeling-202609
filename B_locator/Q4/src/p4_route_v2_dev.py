"""Development-only paired benchmark for independent Q4 routing trials."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from p4_search import tier_config, P4SearchRobot
from p4_route_v2 import P4RouteV2Robot, P4RouteV2Config
from p4_search_bench import scenario_arena, summary


def run(name, scenario, seed):
    cfg=P4RouteV2Config(**asdict(tier_config('strict')))
    cls=P4SearchRobot if name=='baseline' else P4RouteV2Robot
    cfg.route_service_entry = name in ('entry', 'entry_long')
    cfg.route_fixed_stations = name=='fixed'
    cfg.route_information = name=='info'
    cfg.route_v2_rounds = 8 if name in ('long', 'entry_long') else 4
    cfg.route_v2_starts = 10 if name in ('long', 'entry_long') else 5
    a=scenario_arena(scenario, seed);rb=cls(a,cfg)
    t=time.perf_counter();rep=rb.run()
    return dict(policy=name,scenario=scenario,seed=seed,cleared=rep['cleared'],
        total=rep['n_sources'],exit_s=rep['virtual_time_s'],
        last_clear_s=rb.stats['vtime_at_last_clear'],travel_m=rep['travel_m'],
        measures=rep['n_measure'],clear_fail=rep['n_clear_fail'],
        rejected=rep['n_rejected'],runtime_s=time.perf_counter()-t,
        completion_certified=rep.get('completion_certified'),
        stations=rep['search_stations'],config=asdict(rb.cfg))


def main():
    p=argparse.ArgumentParser();p.add_argument('--names',default='baseline,tsp,entry')
    p.add_argument('--scenarios',default='mixed_uniform,uniform');p.add_argument('--cases',type=int,default=12)
    p.add_argument('--out',default='B_locator/Q4/out/p4_route_v2_dev/first.jsonl')
    args=p.parse_args();path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True);rows=[]
    with path.open('w',encoding='utf8') as f:
        for name in args.names.split(','):
            for scenario in args.scenarios.split(','):
                for i in range(args.cases):
                    row=run(name,scenario,20260914+100*i);rows.append(row)
                    f.write(json.dumps(row)+'\n');f.flush()
                print(json.dumps(summary([r for r in rows if r['policy']==name and r['scenario']==scenario])[0]),flush=True)
    path.with_suffix('.summary.json').write_text(json.dumps(summary(rows),indent=2),encoding='utf8')


if __name__=='__main__':main()
