"""Fresh paired validation of tour, adaptive and joint Q3 policies."""
import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import time
import numpy as np
from p3_adaptive import AdaptiveRobot, AdaptiveConfig
from p3_joint import JointRobot, JointConfig
from p3_tour import TourRobot, TourConfig
from p3_adaptive_bench import make_scene
from p3_bench import run_one, load_base


def summarize_rows(rows):
    complete=[r for r in rows if 'error' not in r]
    out={'cases':len(rows),'paired_completed':len(complete)}
    names=('tour','adaptive','joint')
    if not complete:return out
    for name in names:
        vals=[r[name] for r in complete]
        times=np.array([r['virtual_time_s'] for r in vals])
        out[name]={
            'mean_s':float(times.mean()),'p90_s':float(np.percentile(times,90)),
            'max_s':float(times.max()),'last_clear_mean_s':float(np.mean([r['last_clear_s'] for r in vals])),
            'travel_mean_m':float(np.mean([r['travel_m'] for r in vals])),
            'measure_mean':float(np.mean([r['n_measure'] for r in vals])),
            'wall_mean_s':float(np.mean([r['_wall'] for r in vals])),
            'wall_max_s':float(max(r['_wall'] for r in vals)),
            'clear_fail_mean':float(np.mean([r['n_clear_fail'] for r in vals])),
            'full_clear_cases':sum(r['cleared']==r['n_sources'] for r in vals),
            'cleared':sum(r['cleared'] for r in vals),'sources':sum(r['n_sources'] for r in vals),
            'certificate_cases':sum(bool(r['complete_proof']) for r in vals),
            'rejections':sum(r['n_rejected'] for r in vals),
        }
    for name in ('tour','adaptive'):
        pairs=np.array([[r[name]['virtual_time_s'],r['joint']['virtual_time_s']] for r in complete])
        rng=np.random.default_rng(90711)
        means=pairs[rng.integers(0,len(pairs),size=(4000,len(pairs)))].mean(axis=1)
        out['joint_vs_'+name]={
            'saved_mean_s':float(np.mean(pairs[:,0]-pairs[:,1])),
            'saved_fraction':float(1-pairs[:,1].mean()/pairs[:,0].mean()),
            'faster_cases':int(np.count_nonzero(pairs[:,1]<pairs[:,0])),
            'bootstrap_95pct':np.percentile(1-means[:,1]/means[:,0],[2.5,97.5]).tolist(),
        }
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--counts',default='random:50,annulus:20,center:10,hash:20,worstrecv:20,live1:10,live2:10')
    ap.add_argument('--seed',type=int,default=918000)
    ap.add_argument('--step',type=int,default=53)
    ap.add_argument('--out',default=str(Path(__file__).resolve().parents[1] / 'out/p3_joint_validation'))
    args=ap.parse_args()
    dest=Path(args.out);dest.mkdir(parents=True,exist_ok=True)
    configs={'tour':TourConfig(),'adaptive':AdaptiveConfig(),'joint':JointConfig()}
    classes={'tour':TourRobot,'adaptive':AdaptiveRobot,'joint':JointRobot}
    src=Path(__file__).resolve().parent
    files=['p3_joint.py','p3_adaptive.py','p3_homing.py','p3_frontier.py','p3_coverage.py','p3_tour.py','p3_robot.py','p3_arena.py']
    result={'arguments':vars(args),'configs':{k:asdict(v) for k,v in configs.items()},
            'source_sha256':{f:hashlib.sha256((src/f).read_bytes()).hexdigest() for f in files},
            'note':'All runs offline. live1/live2 use reconstructed coordinates with assumed 1400 m receivers. tour certificate is its legacy point-grid predicate.',
            'scenarios':{}}
    base=load_base()
    for part in args.counts.split(','):
        kind,count=part.split(':');rows=[]
        for i in range(int(count)):
            row={'seed':args.seed+args.step*i}
            for name in classes:
                arena=make_scene(kind,row['seed'])
                try:
                    r=run_one(classes[name],configs[name],arena,base)
                    r['last_clear_s']=(r['avg_clear_time_s'] or 0)*r['cleared']
                    row[name]={k:v for k,v in r.items() if k not in ('truth','channels','mock_stats','scan_points')}
                    if i<3:
                        trace={'scenario':kind,'seed':row['seed'],'policy':name,'actions':arena.actions,'truth':arena.truth()}
                        (dest/f'{kind}_{row["seed"]}_{name}_trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2),encoding='utf-8')
                except Exception as exc:
                    row['error']=f'{name}: {type(exc).__name__}: {exc}'
                    print(kind,row['seed'],row['error'],flush=True);break
            rows.append(row)
            if (i+1)%10==0:print(f'{kind} {i+1}/{count}',flush=True)
        summary=summarize_rows(rows)
        result['scenarios'][kind]={'summary':summary,'rows':rows}
        (dest/'paired_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(kind,json.dumps(summary,ensure_ascii=False),flush=True)
    with (dest/'paired_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['scenario','seed','tour_s','adaptive_s','joint_s','joint_last_clear_s','saved_vs_adaptive_s','joint_cleared','n_sources','joint_certificate','error'])
        for kind,g in result['scenarios'].items():
            for r in g['rows']:
                if 'error' in r:w.writerow([kind,r['seed'],'','','','','','','','',r['error']]);continue
                a,b=r['adaptive'],r['joint']
                w.writerow([kind,r['seed'],r['tour']['virtual_time_s'],a['virtual_time_s'],b['virtual_time_s'],b['last_clear_s'],a['virtual_time_s']-b['virtual_time_s'],b['cleared'],b['n_sources'],b['complete_proof'],''])


if __name__=='__main__':main()
