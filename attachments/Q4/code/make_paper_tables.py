"""Generate Q4 paper numbers and tables from the frozen paired experiments."""
from pathlib import Path
import json
import os
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('Q4_REVIEW_DATA', ROOT / 'results'))
TEX = Path(os.environ['Q4_REVIEW_OUT']) / 'tables'
TEX.mkdir(parents=True,exist_ok=True)
summary = json.loads((OUT / 'summary.json').read_text(encoding='utf-8'))
runs = [json.loads(line) for line in (OUT / 'runs.jsonl').read_text(encoding='utf-8').splitlines()]
names = {'legacy': 'grid', 'joint_strict': 'joint', 'compact_strict': 'compact',
         'compact_no_posterior': '关闭后验中心', 'compact_no_information': '关闭信息代价',
         'compact_fast99': 'fast99', 'compact_fast95': 'fast95', 'compact_fast90': 'fast90'}
scenes = {'mixed_uniform': '随机混合', 'minrange': '最小接收半径', 'edge': '贴边朝外', 'omni': '全向'}


def group(policy, scenario='mixed_uniform', experiment='main'):
    return next(g for g in summary['groups'] if (g['policy'], g['scenario'], g['experiment']) == (policy, scenario, experiment))


def rows_file(name, rows):
    (TEX / name).write_text(' \\\\\n'.join(rows) + '\n', encoding='utf-8')


def p90(policy, scenario):
    return np.percentile([r['exit_s'] for r in runs if r['policy'] == policy and r['scenario'] == scenario], 90)


policies = ('legacy', 'joint_strict', 'compact_strict')
rows_file('q4-main-rows.tex', [
    f"{names[p]} & {100*g['clearance_rate']:.2f}\\% & {g['full_clear_cases']}/{g['cases']} & {g['exit_s']:.1f} & {p90(p,'mixed_uniform'):.1f} & {g['exit_per_cleared']:.1f} & {g['travel_m']/1000:.2f}"
    for p in policies for g in [group(p)]])
rows_file('q4-stress-rows.tex', [scenes[s] + ' & ' + ' & '.join(
    f"{g['full_clear_cases']}/{g['cases']} & {g['exit_s']:.1f}" for p in policies for g in [group(p,s,'stress')])
    for s in ('minrange', 'edge', 'omni')])
rows_file('q4-supplement-rows.tex', [
    f"{scenes[g['scenario']]}/{names[g['policy']]} & {g['cleared']}/{g['total']} & {g['full_clear_cases']}/{g['cases']} & {g['exit_s']:.1f} & {g['last_per_cleared']:.1f} & {g['exit_per_cleared']:.1f} & {g['measures']:.1f} & {g['runtime_s']:.2f}"
    for g in summary['groups'] if g['experiment'] in ('main','stress')])
extra = [g for g in summary['groups'] if g['experiment'] == 'speed']
rows_file('q4-speed-rows.tex', [
    f"{names[g['policy']]} & {g['cleared']}/{g['total']} & {g['full_clear_cases']}/{g['cases']} & {g['exit_s']:.1f} & {g['last_per_cleared']:.1f} & {g['exit_per_cleared']:.1f}"
    for g in extra])
comparison = next(c for c in summary['comparisons'] if c['experiment']=='main' and c['before']=='joint_strict' and c['after']=='compact_strict')
complete = group('compact_strict')
all_compact = [r for r in runs if r['policy']=='compact_strict']
numbers = {
    'Saving': f"{100*comparison['saved_fraction']:.2f}",
    'SavingLow': f"{100*comparison['saved_fraction_ci'][0]:.2f}",
    'SavingHigh': f"{100*comparison['saved_fraction_ci'][1]:.2f}",
    'LastPerSource': f"{complete['last_per_cleared']:.1f}",
    'ExitTime': f"{complete['exit_s']:.1f}",
    'JointExitTime': f"{group('joint_strict')['exit_s']:.1f}",
    'ExitPerSource': f"{complete['exit_per_cleared']:.1f}",
    'ClearedTotal': str(sum(r['cleared'] for r in all_compact)),
    'SourceTotal': str(sum(r['total'] for r in all_compact)),
    'CertifiedTotal': str(sum(r['certified'] and r['certification_mode']=='continuous' for r in all_compact)),
}
ablation_rows=[]
for policy, macro in [('compact_no_posterior','PosteriorChange'), ('compact_no_information','InformationChange')]:
    c=next(c for c in summary['comparisons'] if c['experiment']=='ablation' and c['before']==policy)
    # Transform the same paired bootstrap samples from savings/ablated to
    # increase/complete. This monotonic transform preserves percentile bounds.
    fraction=c['saved_fraction']
    change=fraction/(1-fraction)
    lo,hi=[v/(1-v) for v in c['saved_fraction_ci']]
    numbers[macro]=f"{100*change:+.2f}"
    g=group(policy,experiment='ablation')
    ablation_rows.append(f"{names[policy]} & {g['exit_s']:.1f} & {100*change:+.2f} & [{100*lo:.2f},{100*hi:.2f}] & {g['full_clear_cases']}/{g['cases']}")
rows_file('q4-ablation-rows.tex',ablation_rows)
(TEX/'q4-numbers.tex').write_text('% Generated from Q4/out/paper_q4/summary.json.\n'+''.join(
    f'\\providecommand{{\\QFour{k}}}{{{v}}}\n' for k,v in numbers.items()),encoding='utf-8')
(TEX/'table_provenance.json').write_text(json.dumps({'source':'summary.json','p90_source':'runs.jsonl','numbers':numbers,'bootstrap':summary.get('manifest','manifest.json')},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(numbers,ensure_ascii=False))
