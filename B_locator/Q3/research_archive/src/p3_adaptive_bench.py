"""Frozen paired benchmark; all policies receive fresh copies of each scene."""
from __future__ import annotations
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import numpy as np
from p3_arena import MockArena
from p3_adaptive import AdaptiveConfig, AdaptiveRobot
from p3_tour import TourConfig, TourRobot
from p3_bench import LIVE1,LIVE2,arena_from,outer_annulus,center_cluster,run_one,load_base


class HashErrorArena(MockArena):
    """Different bounded error model: deterministic per location, not smooth."""
    def env_error(self,x,y):
        key=f'{self._local_seed}:{float(x).hex()}:{float(y).hex()}'.encode()
        value=int.from_bytes(hashlib.sha256(key).digest()[:8],'little')/(2**64-1)
        return (2*value-1)*0.995


def make_scene(kind,seed):
    if kind=='annulus':
        return outer_annulus(seed)
    if kind=='center':
        return center_cluster(seed)
    if kind in ('live1','live2'):
        return arena_from(LIVE1 if kind=='live1' else LIVE2,seed=seed)
    if kind=='hash':
        return HashErrorArena(seed=seed)
    arena=MockArena(seed=seed)
    if kind=='worstrecv':
        for source in arena.sources:
            source.r_recv=1000.0
    elif kind!='random':
        raise ValueError(kind)
    return arena


def statistics(rows):
    good=[r for r in rows if 'error' not in r]
    out={'cases':len(rows),'paired_completed':len(good)}
    if not good:
        return out
    for name in ('tour','adaptive'):
        vals=[r[name] for r in good]
        times=[r['virtual_time_s'] for r in vals]
        out[name]={
            'mean_s':float(np.mean(times)),
            'p90_s':float(np.percentile(times,90)),
            'max_s':float(np.max(times)),
            'last_clear_mean_s':float(np.mean([r['last_clear_s'] for r in vals])),
            'last_clear_per_source_mean_s':float(np.mean([r['avg_clear_time_s'] or 0 for r in vals])),
            'exit_per_source_mean_s':float(np.mean([r['virtual_time_s']/max(r['cleared'],1) for r in vals])),
            'travel_mean_m':float(np.mean([r['travel_m'] for r in vals])),
            'measure_mean':float(np.mean([r['n_measure'] for r in vals])),
            'wall_mean_s':float(np.mean([r['_wall'] for r in vals])),
            'full_clear_cases':sum(r['cleared']==r['n_sources'] for r in vals),
            'cleared':sum(r['cleared'] for r in vals),
            'sources':sum(r['n_sources'] for r in vals),
            'complete_predicate_cases':sum(bool(r['complete_proof']) for r in vals),
            'rejections':sum(r['n_rejected'] for r in vals),
        }
    pairs=np.asarray([[r['tour']['virtual_time_s'],r['adaptive']['virtual_time_s']] for r in good])
    out['improvement_fraction']=float(1-pairs[:,1].mean()/pairs[:,0].mean())
    out['adaptive_faster_cases']=int(np.count_nonzero(pairs[:,1]<pairs[:,0]))
    sampled=np.random.default_rng(121212).integers(0,len(pairs),size=(4000,len(pairs)))
    means=pairs[sampled].mean(axis=1)
    out['paired_bootstrap_95pct']=np.percentile(1-means[:,1]/means[:,0],[2.5,97.5]).tolist()
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--counts',default='random:50,annulus:20,center:20,live1:15,live2:15,hash:20,worstrecv:20')
    ap.add_argument('--seed',type=int,default=777000)
    ap.add_argument('--step',type=int,default=37)
    ap.add_argument('--out',default=str(Path(__file__).resolve().parents[1] / 'out/p3_adaptive_validation'))
    args=ap.parse_args()
    outdir=Path(args.out);outdir.mkdir(parents=True,exist_ok=True)
    configs={'tour':TourConfig(),'adaptive':AdaptiveConfig()}
    classes={'tour':TourRobot,'adaptive':AdaptiveRobot}
    source_dir=Path(__file__).resolve().parent
    files=['p3_tour.py','p3_homing.py','p3_frontier.py','p3_coverage.py','p3_adaptive.py','p3_arena.py']
    result={'arguments':vars(args),'configs':{k:asdict(v) for k,v in configs.items()},
            'source_sha256':{f:hashlib.sha256((source_dir/f).read_bytes()).hexdigest() for f in files},
            'note':'live1/live2 are reconstructed coordinates with assumed reception radius 1400 m, not live runs; tour complete_proof is only its original grid predicate.',
            'scenarios':{}}
    base=load_base()
    for part in args.counts.split(','):
        kind,count=part.split(':');rows=[]
        for i in range(int(count)):
            seed=args.seed+args.step*i
            row={'seed':seed}
            for name in ('tour','adaptive'):
                arena=make_scene(kind,seed)
                try:
                    r=run_one(classes[name],configs[name],arena,base,want_path=True)
                    r['last_clear_s']=(r['avg_clear_time_s'] or 0)*r['cleared']
                    row[name]={k:v for k,v in r.items() if k not in ('truth','channels','mock_stats','_actions')}
                    if i<3:
                        trace={'scenario':kind,'seed':seed,'policy':name,'actions':arena.actions,'truth':arena.truth()}
                        (outdir/f'{kind}_{seed}_{name}_trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
                except Exception as exc:
                    row['error']=f'{name}: {type(exc).__name__}: {exc}'
                    print(kind,seed,row['error'],flush=True)
                    break
            rows.append(row)
            if (i+1)%10==0:
                print(f'{kind}: {i+1}/{count}',flush=True)
        summary=statistics(rows)
        result['scenarios'][kind]={'summary':summary,'rows':rows}
        (outdir/'paired_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        print(kind,json.dumps(summary,ensure_ascii=False),flush=True)
    with (outdir/'paired_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f)
        w.writerow(['scenario','seed','tour_s','adaptive_s','saved_s','tour_cleared','adaptive_cleared','n_sources','adaptive_certified','error'])
        for kind,data in result['scenarios'].items():
            for row in data['rows']:
                if 'error' in row:
                    w.writerow([kind,row['seed'],'','','','','','','',row['error']]);continue
                a,b=row['tour'],row['adaptive']
                w.writerow([kind,row['seed'],a['virtual_time_s'],b['virtual_time_s'],a['virtual_time_s']-b['virtual_time_s'],a['cleared'],b['cleared'],a['n_sources'],b['complete_proof'],''])


if __name__=='__main__':
    main()
