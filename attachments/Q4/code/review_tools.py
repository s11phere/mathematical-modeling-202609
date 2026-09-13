"""直接重放已保存动作的独立核验，以及覆盖全部实验的补充图册。"""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,hashlib,json,math
ROOT=Path(__file__).resolve().parents[1]

def verify_package(dev=False):
    """Development relaxes only existing Python-source hashes, never evidence."""
    manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    checked=0;modified=set()
    for relative,record in manifest['files'].items():
        path=ROOT/relative
        if not path.is_file():raise RuntimeError(f'附件文件缺失：{relative}')
        editable=(relative=='reproduce.py' or (Path(relative).parent==Path('code') and Path(relative).suffix=='.py'))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            if not (dev and editable):raise RuntimeError(f'附件文件 SHA256 不一致：{relative}')
            modified.add(relative)
        else:checked+=1
    expected_files=set(manifest['files'])|{'SOURCE_MANIFEST.json'}
    extra=sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob('*')
                 if p.is_file() and p.name!='.DS_Store'
                 and '__pycache__' not in p.relative_to(ROOT).parts
                 and str(p.relative_to(ROOT)) not in expected_files)
    if extra:raise RuntimeError(f'附件存在未登记文件：{", ".join(extra)}')
    shared={}
    index=ROOT.parent/'SHA256SUMS.txt'
    lines=index.read_text(encoding='utf-8').splitlines() if index.is_file() else []
    for line in lines:
        if not line.strip():continue
        expected,relative=line.split(maxsplit=1)
        if relative.startswith('fonts/') or relative==f'{ROOT.name}/SOURCE_MANIFEST.json':
            path=ROOT.parent/relative
            if relative.startswith('fonts/') and not path.exists():continue
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise RuntimeError(f'共享字体或来源清单 SHA256 不一致：{relative}')
            shared[relative]=expected
    font=ROOT.parent/'fonts/simsun.ttc'
    if font.exists() and 'fonts/simsun.ttc' not in shared:
        expected='7a368113c36d516aac1a825acc4bbbc9906c4d197f7c649e7fe0f6f31e7475dd'
        if not font.is_file() or hashlib.sha256(font.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('共享字体 SHA256 不一致：fonts/simsun.ttc')
        shared['fonts/simsun.ttc']=expected
    frozen=json.loads((ROOT/'results/manifest.json').read_text(encoding='utf-8'))['source_sha256']
    count=0
    for path in (ROOT/'code').glob('*.py'):
        key='../run_paper_q4.py' if path.name=='run_paper_q4.py' else path.name
        if key in frozen:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=frozen[key]:
                if not dev:raise RuntimeError(f'算法与论文冻结记录不一致：{key}')
                modified.add('code/'+path.name)
            else:count+=1
    if dev:
        print('开发运行：修改代码用于新实验，不代表与论文冻结源码或结果一致。',flush=True)
        print('修改的代码：'+(', '.join(sorted(modified)) or '无'),flush=True)
    return {'mode':'development' if dev else 'frozen','package_files_verified':checked,
            'package_files_present':len(manifest['files']),'modified_code':sorted(modified),
            'shared_fonts_and_manifest_verified':len(shared),
            'included_frozen_source_files_verified':count}

def read_trace(row):
    path=ROOT/'results'/row['trace']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==row['trace_sha256'],str(path)
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)

def rows():return [json.loads(s) for s in (ROOT/'results/runs.jsonl').read_text().splitlines()]

def check(output=None):
    records=rows();assert len(records)==230
    counts=Counter();actions_total=0;source_groups=defaultdict(set)
    for r in records:
        tr=read_trace(r);xy=(0.,0.);channel=1;elapsed=0.;travel=0.;n=Counter();last=0.;cleared=set()
        assert tr['actions'][0]['kind']=='enter' and tr['actions'][-1]['kind']=='exit'
        source=[{key:value for key,value in s.items() if key!='cleared'} for s in tr['sources']]
        source_digest=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
        assert source_digest==r['source_sha256'],(r['seed'],'source hash')
        source_groups[(r['scenario'],r['seed'])].add(source_digest)
        assert tr['row']['config']==r['config']
        assert math.isclose(tr['actions'][0]['virtual_time_s'],0,abs_tol=1e-7)
        for a in tr['actions']:
            if a['kind'] not in ['measure','clear']:continue
            nxt=(a['x'],a['y']);dist=math.dist(xy,nxt);xy=nxt;travel+=dist
            dt=dist/5
            if a['kind']=='measure':
                switch=int(a['channel']!=channel)
                assert a['switch_s']==switch,(r['seed'],'switch')
                dt+=5+switch;channel=a['channel'];n['measures']+=1
            else:
                ok=a['clear_result']=='success';dt+=5 if ok else 3
                n['cleared' if ok else 'failures']+=1
                if ok:
                    assert a['channel'] not in cleared;cleared.add(a['channel'])
            elapsed+=dt
            assert math.isclose(dist,a['dist_m'],abs_tol=1e-7),(r['seed'],'distance')
            assert math.isclose(dt,a['dt'],abs_tol=1e-7),(r['seed'],'dt')
            assert math.isclose(elapsed,a['virtual_time_s'],abs_tol=1e-7),(r['seed'],'clock')
            if a['kind']=='clear' and a['clear_result']=='success':last=elapsed
        assert math.isclose(tr['actions'][-1]['virtual_time_s'],elapsed,abs_tol=1e-7)
        for name,computed in [('exit_s',elapsed),('travel_m',travel),('last_s',last),
                              ('measures',n['measures']),('cleared',n['cleared']),('failures',n['failures'])]:
            assert math.isclose(computed,r[name],abs_tol=1e-6),(name,computed,r[name])
        assert r['rejected']==0
        counts[r['cohort']]+=1;actions_total+=len(tr['actions'])
    assert len(source_groups)==60 and all(len(hashes)==1 for hashes in source_groups.values())
    summary=json.loads((ROOT/'results/summary.json').read_text());assert summary['run_count']==230
    arguments=json.loads((ROOT/'results/manifest.json').read_text())['arguments']
    for group in summary['groups']:
        # Speed and ablation comparisons reuse the first extra_cases main
        # compact runs. They are not additional rows in these cohorts.
        if group['experiment'] in ('ablation','speed') and group['policy']=='compact_strict':
            rr=[r for r in records if r['cohort']=='main' and r['scenario']=='mixed_uniform'
                and r['policy']=='compact_strict' and r['case_index']<arguments['extra_cases']]
        else:
            rr=[r for r in records if r['cohort']==group['experiment'] and r['scenario']==group['scenario'] and r['policy']==group['policy']]
        assert len(rr)==group['cases']
        assert math.isclose(sum(r['exit_s'] for r in rr)/len(rr),group['exit_s'],abs_tol=1e-7)
        assert sum(r['cleared'] for r in rr)==group['cleared']
    # Rebuild every statistic, confidence interval and paired comparison with
    # the frozen aggregation code, in addition to the independent action audit.
    from types import SimpleNamespace
    from run_paper_q4 import aggregate
    rebuilt=aggregate(records,SimpleNamespace(**arguments),summary['manifest'])
    for key,value in summary.items():
        if key!='generated_utc':assert rebuilt[key]==value,('summary',key)
    for policy in ('legacy','joint_strict','compact_strict'):
        representative=json.loads((ROOT/'data'/f'representative_{policy}.json').read_text())
        first=next(r for r in records if r['scenario']=='mixed_uniform' and r['case_index']==0 and r['policy']==policy)
        assert representative==read_trace(first),('representative trace',policy)
    report={'trace_files_verified':len(records),'action_records_verified':actions_total,
            'unique_paired_scenarios':len(source_groups),'all_source_definitions_match':True,
            'all_time_ledgers_match':True,'all_trace_hashes_match':True,
            'groups_verified':len(summary['groups']),'paired_comparisons_verified':len(summary['comparisons']),
            'representative_traces_verified':3,
            'summary_statistics_exactly_equal_frozen':True,'cohorts':dict(counts),
            'audit_scope':'Independent action/source replay plus frozen aggregation; no policy execution, no new continuous-geometry proof.'}
    if output:
        output=Path(output);output.mkdir(parents=True,exist_ok=True)
        (output/'package_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f'问题四：230份轨迹哈希、{actions_total}条动作账本及全部分组均值核验通过；{dict(counts)}。')
    return report

def supplement(output):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Circle
    import make_paper_figures as style
    style.setup_style()
    records=rows();bycase=defaultdict(dict)
    for r in records:bycase[(r['scenario'],r['seed'])][r['policy']]=r
    scenarios={'mixed_uniform':'随机混合','minrange':'最小接收半径','edge':'贴边朝外','omni':'全向'}
    labels={'legacy':'grid','joint_strict':'joint','compact_strict':'compact','compact_no_posterior':'取消后验中心','compact_no_information':'取消信息代价','compact_fast99':'fast99','compact_fast95':'fast95','compact_fast90':'fast90'}
    order=['mixed_uniform','minrange','edge','omni']
    keys=sorted(bycase,key=lambda key:(order.index(key[0]),key[1]))
    jobs=[(key,'三代策略',['legacy','joint_strict','compact_strict']) for key in keys]
    extra=[key for key in keys if 'compact_no_posterior' in bycase[key]]
    jobs.extend((key,'单因素消融',['compact_strict','compact_no_posterior','compact_no_information']) for key in extra)
    jobs.extend((key,'快速策略',['compact_strict','compact_fast99','compact_fast95','compact_fast90']) for key in extra)
    assert len(jobs)==80
    assert {bycase[key][policy]['trace'] for key,_,policies in jobs for policy in policies}=={r['trace'] for r in records}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with PdfPages(output) as pdf:
        for page,(key,heading,policies) in enumerate(jobs,1):
            fig,axes=plt.subplots(2,2,figsize=(8.27,10.5));fig.subplots_adjust(left=.10,right=.96,bottom=.09,top=.89,hspace=.40,wspace=.25)
            fig.suptitle(f'问题四补充轨迹 · {scenarios[key[0]]} · {heading}\n场景种子 {key[1]}',fontsize=13,y=.96)
            for ax,policy in zip(axes.flat,policies):
                row=bycase[key][policy];tr=read_trace(row)
                acts=[a for a in tr['actions'] if a['kind'] in ['measure','clear']];points=np.array([[0,0]]+[[a['x'],a['y']] for a in acts])
                ax.plot(points[:,0],points[:,1],color='#118a8c',lw=.8)
                ax.add_patch(Circle((0,0),1800,fill=False,ec='#888888',ls='--',lw=.6))
                for s in tr['sources']:
                    ax.plot(s['x'],s['y'],'o',ms=3,mfc='none',mec='#45505a')
                    if s['cone_half']<180:
                        angle=math.radians(s['dir_deg']+180);ax.arrow(s['x'],s['y'],180*math.cos(angle),180*math.sin(angle),head_width=60,color='#45505a',lw=.4)
                for a in acts:
                    if a['kind']=='measure':ax.plot(a['x'],a['y'],'.',ms=2,color='#d7a06b')
                    elif a['clear_result']=='success':ax.plot(a['x'],a['y'],'x',ms=3,color='#b33e36')
                    else:ax.plot(a['x'],a['y'],'^',ms=3,mfc='none',mec='#b7791f')
                ax.plot(0,0,'s',ms=3,color='#263846')
                ax.set(xlim=(-2200,2200),ylim=(-2200,2200),aspect='equal',xlabel='$x$ / m',ylabel='$y$ / m')
                ax.set_xticks([-1800,0,1800]);ax.set_yticks([-1800,0,1800]);ax.tick_params(labelsize=8)
                ax.set_title(f"{labels[policy]}\n清除 {row['cleared']}/{row['total']}；完整时间 {row['exit_s']:.1f} s\n行程 {row['travel_m']/1000:.2f} km；检测 {row['measures']} 次",fontsize=9)
            for ax in list(axes.flat)[len(policies):]:
                ax.axis('off')
                ax.text(.05,.85,'阅读说明',transform=ax.transAxes,fontsize=12,va='top')
                ax.text(.05,.74,'同组使用相同源位、接收半径及误差场。\n\n完整时间包含退出前的未知频道排除。\n源位与接收方向仅在退出后用于画图。\n\n清除比例、失败清除和漏清均如实保留。\n三角标记为尝试清除但未成功的位置。\n\n原始记录可由场景与种子在\nresults/runs.jsonl 中定位。',
                        transform=ax.transAxes,fontsize=9,va='top',linespacing=1.8)
            fig.text(.5,.045,'橙点：检测；红叉：清除成功；空心三角：清除失败；圆圈/箭头：源位/接收方向；方块：起点。',ha='center',fontsize=8)
            fig.text(.5,.022,f'同组源位相同，保留全部失败场景。  {page} / {len(jobs)}',ha='center',fontsize=8)
            pdf.savefig(fig);plt.close(fig)
            if page%20==0:print(f'补充图册：{page}/80 页',flush=True)
    print(f'生成问题四补充图册：{len(jobs)}页，覆盖全部230次运行。')
