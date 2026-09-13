"""Read frozen Q3 rows and emit paper tables, macros and supporting statistics."""
import json
import hashlib
from pathlib import Path
import numpy as np

Q3 = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
DATA = Q3 / 'out/paper_q3'
SECTIONS = REPO / 'paper/sections'
POLICIES = ('field', 'sweep', 'tour', 'adaptive', 'joint')
SCENARIOS = ('random', 'annulus', 'center', 'hash', 'worstrecv')

def main():
    obj = json.loads((DATA/'paired_results.json').read_text())
    rows = obj['rows']
    summary = json.loads((DATA/'summary.json').read_text())
    random = summary['scenarios']['random']
    body=[]
    for p in POLICIES:
        s=random[p]
        body.append(f"{p} & {s['clear_ratio_source_weighted']:.3f} & {s['full_clear_cases']}/50 & {s['mean_exit_s']:.0f} & {s['p90_exit_s']:.0f} & {s['mean_exit_per_source_s']:.0f}" + r' \\')
    (SECTIONS/'q3-core-rows.tex').write_text('\n'.join(body).rstrip().removesuffix(r'\\')+'\n')
    full={p:sum(r['full_clear'] for r in rows if r['split']=='main' and r['policy']==p) for p in POLICIES}
    pair=random['paired_vs_field']['joint']
    base20=[r for r in rows if r['split']=='main' and r['scenario']=='random' and r['policy']=='joint' and r['index']<20]
    values={'QThreeFieldFull':str(full['field']), 'QThreeSweepFull':str(full['sweep']),
            'QThreeSaving':f"{100*pair['saving']:.1f}", 'QThreeSavingLow':f"{100*pair['ci95'][0]:.1f}",
            'QThreeSavingHigh':f"{100*pair['ci95'][1]:.1f}", 'QThreeAblationBase':f"{np.mean([r['exit_s'] for r in base20]):.1f}"}
    for policy in POLICIES:
        title=policy.capitalize()
        first=next(r for r in rows if r['split']=='main' and r['scenario']=='random' and r['index']==0 and r['policy']==policy)
        values[f'QThreeFirst{title}Time']=f"{first['exit_s']:.0f}"
        values[f'QThreeFirst{title}Travel']=f"{first['travel_m']/1000:.2f}"
        values[f'QThreeFirst{title}Measure']=str(first['n_measure'])
        trace=json.loads((DATA/first['trace_file'].replace('\\', '/')).read_text())
        clears=[a['virtual_time_s'] for a in trace['actions']
                if a.get('kind')=='clear' and a.get('clear_result')=='success']
        values[f'QThreeFirst{title}FourthClear']=f"{clears[3]:.0f}"
        values[f'QThreeFirst{title}Tail']=f"{first['exit_s']-clears[-1]:.0f}"
        values[f'QThreeRandom{title}Travel']=f"{random[policy]['mean_travel_m']/1000:.2f}"
        values[f'QThreeRandom{title}Measure']=f"{random[policy]['mean_measure']:.1f}"
        values[f'QThreeCenter{title}Time']=f"{summary['scenarios']['center'][policy]['mean_exit_s']:.1f}"
    for suffix, policy in [('After','joint_no_after_service'),('Multi','joint_single_plan'),('Polish','joint_no_cover_polish'),('Prob','joint_no_probability_gate')]:
        values[f'QThreeAblation{suffix}Increase']=f"{-100*summary['ablations']['random']['paired_vs_joint'][policy]['saving']:.2f}"
    (SECTIONS/'q3-numbers.tex').write_text('% Generated from the frozen Q3 data; do not hand edit.\n'+''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in values.items()))
    # Abstract prose is maintained in the paper; only numeric tables and macros
    # are generated here so reproduction never overwrites the edited abstract.
    lines=[]
    for kind in SCENARIOS:
        for p in POLICIES:
            rs=[r for r in rows if r['split']=='main' and r['scenario']==kind and r['policy']==p]
            s=summary['scenarios'][kind][p]
            lines.append(f"{kind}/{p} & {s['clear_ratio_source_weighted']:.3f} & {s['full_clear_cases']}/{len(rs)} & {s['mean_exit_s']:.1f} & {s['p90_exit_s']:.1f} & {s['mean_exit_per_source_s']:.1f} & {s['mean_travel_m']/1000:.2f} & {s['mean_measure']:.1f} & {s['wall_mean_s']:.3f}"+r' \\')
    (SECTIONS/'q3-supplement-rows.tex').write_text('\n'.join(lines).rstrip().removesuffix(r'\\')+'\n')
    lines=[]
    for p in ('joint_no_after_service','joint_single_plan','joint_no_cover_polish','joint_no_probability_gate'):
        s=summary['ablations']['random'][p]
        pair=summary['ablations']['random']['paired_vs_joint'][p]
        label={'joint_no_after_service':'取消清后扫描','joint_single_plan':'单方案规划','joint_no_cover_polish':'取消测站精修','joint_no_probability_gate':'取消概率门槛'}[p]
        lines.append(f"{label} & {s['mean_exit_s']:.1f} & {-100*pair['saving']:.2f} & [{-100*pair['ci95'][1]:.2f}, {-100*pair['ci95'][0]:.2f}] & {s['mean_travel_m']/1000:.2f} & {s['mean_measure']:.1f} & {s['wall_mean_s']:.3f}"+r' \\')
    (SECTIONS/'q3-ablation-rows.tex').write_text('\n'.join(lines).rstrip().removesuffix(r'\\')+'\n')
    lines=[]
    for p,label in [('joint_baseline','完整 joint'),('joint_no_after_service','取消清后扫描'),('joint_single_plan','单方案规划'),('joint_no_cover_polish','取消测站精修'),('joint_no_probability_gate','取消概率门槛')]:
        s=summary['ablations']['random'][p]
        lines.append(f"{label} & {s['clear_ratio_source_weighted']:.3f} & {s['full_clear_cases']}/20 & {s['mean_exit_s']:.1f} & {s['p90_exit_s']:.1f} & {s['mean_exit_per_source_s']:.1f}"+r' \\')
    (SECTIONS/'q3-ablation-complete-rows.tex').write_text('\n'.join(lines).rstrip().removesuffix(r'\\')+'\n')
    (DATA/'table_provenance.json').write_text(json.dumps({'experiment_id':obj['experiment_id'], 'data_sha256':hashlib.sha256((DATA/'paired_results.json').read_bytes()).hexdigest(), 'summary_sha256':hashlib.sha256((DATA/'summary.json').read_bytes()).hexdigest(), 'generated':values, 'all_main_full_clear':full},indent=2)+'\n')

if __name__=='__main__':main()
