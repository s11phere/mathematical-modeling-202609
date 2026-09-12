"""Development-only layout screening for directional Q4 search.

Uses the fixed development sequence, never the held-out validation sequence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time
from p4_search_bench import run_one, summary


def candidates():
    layouts = {}
    for r, counts in ((1300, (10,12)), (1350, (9, 10)), (1400,(7,8,9)),
                      (1450, (7,8,9,10)),
                      (1500, (7,8,9,10)), (1600, (8, 10, 12)),
                      (1700, (8, 10, 12)), (1800, (10, 12)),
                      (1850, (10, 12))):
        for n in counts:
            layouts[f'r{r}n{n}'] = {'search_rings': ((float(r), n),)}
    for r1, n1, r2, n2 in ((850,4,1750,8), (1000,4,1750,8),
                           (1150,4,1750,8), (900,4,1850,8),
                           (1100,4,1850,8), (1100,5,1800,5),
                           (1100,5,1800,7), (1000,6,1750,6),
                           (1100,6,1800,6), (1000,6,1850,9),
                           (1100,6,1750,8), (900,5,1800,8),
                           (900,4,1750,6), (1000,4,1800,6),
                           (800,3,1750,7), (900,4,1850,7),
                           (1000,4,1600,8), (1100,4,1650,8),
                           (1000,4,1700,7), (1000,4,1700,8),
                           (800,3,1700,8), (850,4,1700,7)):
        layouts[f'r{r1}n{n1}_r{r2}n{n2}'] = {
            'search_rings': ((float(r1), n1), (float(r2), n2))}
    return layouts


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cases', type=int, default=12)
    ap.add_argument('--names', default='')
    ap.add_argument('--variants', action='store_true')
    ap.add_argument('--only-variant', default='')
    ap.add_argument('--out', default='B_locator/Q4/out/p4_search_dev/tune_screen.jsonl')
    args=ap.parse_args()
    choices=candidates()
    if args.names:
        choices={k: choices[k] for k in args.names.split(',')}
    if args.variants:
        choices={f'{k}_{variant}': dict(v, **extra)
                 for k,v in choices.items()
                 for variant,extra in (('heard_off',{'scan_heard':False}),
                                       ('survey',{'joint_route':False}),
                                       ('endpoint',{'after_clear_scan':True}),
                                       ('selective',{'after_clear_scan':True,
                                                     'endpoint_scan_min_saved':50.}))}
        if args.only_variant:
            choices={k:v for k,v in choices.items()
                     if k.endswith('_'+args.only_variant)}
    root=Path(__file__).parent
    files=['p4_search.py','p4_homing.py','p4_certificate.py','p4_search_bench.py']
    hashes={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.with_suffix('.meta.json').write_text(json.dumps(dict(
        files=hashes,configurations=choices,seed=20260914,stride=100,
        cases=args.cases,started=time.time()),indent=2),encoding='utf8')
    rows=[]
    with path.open('w',encoding='utf8') as f:
        for label,config in choices.items():
            for scenario in ['mixed_uniform','uniform']:
                group=[]
                for i in range(args.cases):
                    row=run_one('fast95',scenario,20260914+100*i,config)
                    row['policy']=label
                    rows.append(row);group.append(row)
                    f.write(json.dumps(row)+'\n');f.flush()
                print(json.dumps(summary(group)[0]),flush=True)
    path.with_suffix('.summary.json').write_text(json.dumps(summary(rows),indent=2),encoding='utf8')


if __name__=='__main__':main()
