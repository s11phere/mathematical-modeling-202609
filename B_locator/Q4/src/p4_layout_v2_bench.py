"""Isolated benchmark of compact certified layout with unchanged search."""
from __future__ import annotations
import json
import argparse
from pathlib import Path
from p4_search import P4SearchRobot,tier_config
from p4_search_bench import scenario_arena,summary,run_one
from p4_layout_v2 import compact_layout,compact21_layout,adaptive_complete

class CompactRobot(P4SearchRobot):
    def _build_stations(self):return (compact21_layout() if self.cfg.tier=='compact21' else compact_layout())[1:]
    def _certify_remaining(self):
        cache={}
        for rec in self.recs.values():
            if rec.cleared:continue
            if rec.n_bearings or rec.near_hits:return False
            points=tuple(sorted(set(tuple(row[:2]) for row in rec.meas_log if row[3]=='no_signal')))
            if points not in cache:cache[points]=adaptive_complete(points)
            if not cache[points]:return False
        return True

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--policies',default='strict,compact22,compact21')
    ap.add_argument('--cases',type=int,default=12);ap.add_argument('--out',default='B_locator/Q4/out/p4_layout_v2/paired.jsonl')
    args=ap.parse_args()
    rows=[]
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',encoding='utf8') as f:
        for scenario in ['mixed','uniform','edge']:
            for i in range(args.cases):
                seed=20260914+100*i
                for name in args.policies.split(','):
                    if name=='strict':row=run_one(name,scenario,seed)
                    else:
                        a=scenario_arena(scenario,seed);cfg=tier_config('strict');cfg.tier=name;rb=CompactRobot(a,cfg);rep=rb.run()
                        row=dict(policy=name,scenario=scenario,seed=seed,cleared=rep['cleared'],
                            total=rep['n_sources'],exit_s=rep['virtual_time_s'],
                            last_clear_s=rb.stats['vtime_at_last_clear'],travel_m=rep['travel_m'],
                            measures=rep['n_measure'],clear_fail=rep['n_clear_fail'],runtime_s=rep['program_runtime_s'],
                            completion_certified=rep['completion_certified'])
                    rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
            print(json.dumps(summary([r for r in rows if r['scenario']==scenario])),flush=True)
    out.with_suffix('.summary.json').write_text(json.dumps(summary(rows),indent=2),encoding='utf8')
