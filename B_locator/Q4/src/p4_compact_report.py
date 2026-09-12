"""Rebuild the second Q4 holdout report from frozen, paired offline runs."""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/p4_compact_validation'
FILES={'main_new':200,'main_base':400,'stress':320,
       'fast_new':800,'fast_base':800,'fast_stress':160}
CORE=['p4_compact.py','p4_posterior.py','p4_route_v2.py','p4_layout_v2.py',
      'p4_search.py','p4_homing.py','p4_certificate.py','p4_robot.py','p4_grid.py',
      'p4_arena_ext.py','p4_search_bench.py','p3_robot.py','p3_arena.py','p1_intersection.py']


def interval(a):
    return [float(v) for v in np.quantile(a,[.025,.975])]


def describe(rows):
    rng=np.random.default_rng(513290)
    t=np.array([r['exit_s'] for r in rows])
    last=np.array([r['last_s'] for r in rows])
    cleared=np.array([r['cleared'] for r in rows])
    total=np.array([r['total'] for r in rows])
    idx=rng.integers(0,len(rows),(5000,len(rows)))
    rates=cleared[idx].sum(axis=1)/total[idx].sum(axis=1)
    per=np.divide(t,cleared,out=np.full(len(rows),np.nan),where=cleared>0)
    last_per=np.divide(last,cleared,out=np.full(len(rows),np.nan),where=cleared>0)
    return dict(cases=len(rows),total=int(total.sum()),cleared=int(cleared.sum()),
                rate=float(cleared.sum()/total.sum()),rate_ci=interval(rates),
                full=int(np.sum(cleared==total)),certified=sum(r['certified'] is True for r in rows),
                exit_s=float(t.mean()),exit_ci=interval(t[idx].mean(axis=1)),
                exit_per_cleared=float(np.nanmean(per)) if cleared.any() else None,
                last_s=float(last.mean()),
                last_per_cleared=float(np.nanmean(last_per)) if cleared.any() else None,
                pooled_exit_per_cleared=float(t.sum()/cleared.sum()) if cleared.any() else None,
                travel_m=float(np.mean([r['travel_m'] for r in rows])),
                measures=float(np.mean([r['measures'] for r in rows])),
                failures=sum(r['failures'] for r in rows),rejected=sum(r['rejected'] for r in rows),
                runtime_mean_s=float(np.mean([r['runtime_s'] for r in rows])),
                runtime_max_s=max(r['runtime_s'] for r in rows))


def paired(a,b):
    aa={r['seed']:r for r in a};bb={r['seed']:r for r in b}
    assert aa.keys()==bb.keys()
    keys=sorted(aa)
    assert all(aa[s]['total']==bb[s]['total'] for s in keys)
    before=np.array([aa[s]['exit_s'] for s in keys]);after=np.array([bb[s]['exit_s'] for s in keys])
    delta=before-after
    idx=np.random.default_rng(71309).integers(0,len(keys),(5000,len(keys)))
    return dict(cases=len(keys),saved_s=float(delta.mean()),
                saved_fraction=float(delta.mean()/before.mean()),
                saved_ci=interval(delta[idx].mean(axis=1)),
                faster_cases=int(np.sum(delta>0)),
                paired_full=sum(aa[s]['cleared']==aa[s]['total'] and bb[s]['cleared']==bb[s]['total'] for s in keys))


def figures(groups,stats):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from p4_layout_v2 import compact21_layout
    from p4_certificate import strict_layout
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    fig,axs=plt.subplots(1,2,figsize=(11.5,4.8),layout='constrained')
    colors=['#192d4a','#087e8b','#32a287','#eea33c','#e15d44']
    tiers=['strict','fast99','fast98','fast95','fast90']
    for ax,sc,title in zip(axs,['mixed_uniform','uniform'],['50% directional sources','100% directional sources']):
        for i,tier in enumerate(tiers):
            s=stats[('compact_'+tier,sc)]
            old=stats[(tier,sc)]
            ax.scatter(old['exit_s'],100*old['rate'],s=45,color=colors[i],marker='x')
            ax.plot([old['exit_s'],s['exit_s']],[100*old['rate'],100*s['rate']],color=colors[i],alpha=.4,lw=1)
            ax.scatter(s['exit_s'],100*s['rate'],s=58,color=colors[i],label=tier)
        ax.set(title=title,xlabel='Complete exit time (s)',ylabel='Pooled clearance rate (%)')
        ax.grid(alpha=.18);ax.set_ylim(88,100.9)
        ax.legend(title='New presets (x = previous)',fontsize=8,loc='lower right')
    fig.savefig(OUT/'pareto.png',dpi=170);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(10.2,5),layout='constrained')
    theta=np.linspace(0,2*np.pi,721)
    for ax,pts,title in zip(axs,[strict_layout(),compact21_layout()],['Previous strict: 25 stations','New strict: 21 stations']):
        pts=np.asarray(pts)
        ax.fill(1800*np.cos(theta),1800*np.sin(theta),color='#edf2f7')
        ax.plot(1800*np.cos(theta),1800*np.sin(theta),'--',color='#64748b',lw=1)
        ax.scatter(pts[1:,0],pts[1:,1],s=32,color='#087e8b')
        ax.scatter([0],[0],marker='*',s=90,color='#e15d44')
        ax.set(title=title,xlabel='x (m)',ylabel='y (m)',aspect='equal',xlim=(-2050,2050),ylim=(-2050,2050))
        ax.grid(alpha=.15)
    fig.savefig(OUT/'layouts.png',dpi=170);plt.close(fig)


def main():
    groups=defaultdict(list);allrows=[]
    current={name:hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest() for name in CORE}
    manifests={}
    for name,count in FILES.items():
        path=OUT/(name+'.jsonl')
        rows=[json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]
        assert len(rows)==count,(name,len(rows),count)
        meta=json.loads(path.with_suffix('.meta.json').read_text(encoding='utf8'))
        for core in CORE:
            if core in meta['files']:assert meta['files'][core]==current[core],(name,core,'changed since benchmark')
        manifests[name]=dict(rows=len(rows),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),args=meta['args'])
        allrows.extend(rows)
        for row in rows:groups[(row['policy'],row['scenario'])].append(row)
    # Every policy/scenario/seed should appear once; no selective run removal.
    assert len({(r['policy'],r['scenario'],r['seed']) for r in allrows})==len(allrows)
    stats={key:describe(value) for key,value in groups.items()}
    comparisons={}
    for (policy,scenario),rows in groups.items():
        if policy.startswith('compact_') and (policy.removeprefix('compact_'),scenario) in groups:
            comparisons[(policy,scenario)]=paired(groups[(policy.removeprefix('compact_'),scenario)],rows)
    strict=[r for r in allrows if r['policy']=='compact_strict']
    assert all(r['cleared']==r['total'] and r['certified'] is True and r['rejected']==0 for r in strict)
    payload=dict(summary=[dict(policy=p,scenario=s,**r) for (p,s),r in sorted(stats.items())],
                 comparisons=[dict(policy=p,scenario=s,**r) for (p,s),r in sorted(comparisons.items())],
                 validation_runs=len(allrows),strict_runs=len(strict),strict_sources=sum(r['total'] for r in strict),
                 rejected=sum(r['rejected'] for r in allrows),core_sha256=current,inputs=manifests)
    (OUT/'results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
    figures(groups,stats)
    lines=['# 问题四第二轮优化：21 站、后验估计与信息排路','',
           '主目标：全部清除后的完整 `/enter` → `/exit` 虚拟时间。最终配置已冻结，下面使用新种子族 `2219000+79i` 做独立配对验证。没有证明全局最优。','',
           '## 全清结果','',
           '| 场景 | 上一版整局 → 新版整局 | 节省 | 上一版每源 → 新版每源 | 新版最后清除口径每源 |',
           '|---|---:|---:|---:|---:|']
    labels={'mixed_uniform':'混合源（50%定向）','uniform':'全定向（随机朝向）','edge':'贴边朝外','minrange':'最小接收半径','omni':'全向源','mixed':'原径向偏好混合'}
    for sc in ['mixed_uniform','uniform']:
        a=stats[('strict',sc)];b=stats[('compact_strict',sc)];c=comparisons[('compact_strict',sc)]
        lines.append(f"| {labels[sc]} | {a['exit_s']:.0f} → **{b['exit_s']:.0f} s** | **{c['saved_fraction']:.1%}** | {a['exit_per_cleared']:.1f} → **{b['exit_per_cleared']:.1f} s** | {b['last_per_cleared']:.1f} s |")
    lines+=['',f"新严格档全部 **{len(strict)} 局、{sum(r['total'] for r in strict)} 个源**完成清除，连续无源/已清除认证 {len(strict)}/{len(strict)}。包含两类主场景各100局，四类压力场景各40局。",'',
            '每源主指标先按每局 `退出时间/清除数` 计算，再对各局求平均。最后清除时刻不含随后排除未知频道的时间，不能用它代替完整退出口径。另一个口径“所有局退出时间之和/清除数之和”也保留在 results.json；源数不同会使两个均值不同。', '',
            '| 场景 | 新版整局均值95% CI | 配对节省95% CI | 完整退出总时间/总清除数 |',
            '|---|---:|---:|---:|']
    for sc in ['mixed_uniform','uniform']:
        b=stats[('compact_strict',sc)];c=comparisons[('compact_strict',sc)]
        lines.append(f"| {labels[sc]} | {b['exit_ci'][0]:.0f}–{b['exit_ci'][1]:.0f} s | {c['saved_ci'][0]:.0f}–{c['saved_ci'][1]:.0f} s | {b['pooled_exit_per_cleared']:.1f} s/源 |")
    lines+=['','按场景 bootstrap 5000 次，保留同一局内相关性；不将零失败样本的退化区间当成数学上的100%保证。严格档的完成依据是覆盖证明和清除兜底。','',
            '**目前仍不能宣称在完整退出且全清的口径下稳定达到 450 s/源。** 混合比例、源数、位置分布和计时口径都会改变结果；对方指标缺少这些信息，不能直接认定同口径优劣。','',
            '## 清除率与时间取舍','',
            '以下各配置仍然清完所有已听到目标，降低的是未知源搜索的覆盖程度。档名只是目标名称，实际清除率必须看实测；不是每局保证。','',
            '| 新配置 | 混合源：清除率 / 完整退出 / 每源 | 全定向：清除率 / 完整退出 / 每源 |',
            '|---|---:|---:|']
    for tier in ['strict','fast99','fast98','fast95','fast90']:
        cells=[]
        for sc in ['mixed_uniform','uniform']:
            s=stats[('compact_'+tier,sc)]
            cells.append(f"{s['rate']:.2%} / {s['exit_s']:.0f} s / {s['exit_per_cleared']:.1f} s")
        lines.append(f"| {tier} | {' | '.join(cells)} |")
    lines+=['','![清除率与完整时间](../out/p4_compact_validation/pareto.png)','',
            '源数未知，100%档按证据完成退出。速度档根据预设扫描布局完成退出，不能判断本局真实清除率。每局10–16源时，遗漏一个已损失6.25%–10%；90%、95%、98%只能用作分布下多局累计目标。','',
            '| 配置 / 场景 | 清除率95% CI | 整局全清 | 相对上一版同名档节省 |',
            '|---|---:|---:|---:|']
    for tier in ['fast99','fast98','fast95','fast90']:
        for sc in ['mixed_uniform','uniform']:
            s=stats[('compact_'+tier,sc)];c=comparisons[('compact_'+tier,sc)]
            saving=f"{c['saved_fraction']:.1%}" if abs(c['saved_fraction'])>=.0005 else '约持平'
            lines.append(f"| {tier} / {labels[sc]} | {s['rate_ci'][0]:.2%}–{s['rate_ci'][1]:.2%} | {s['full']}/{s['cases']} | {saving} |")
    lines+=['','按两类主场景的实测累计清除率均达到目标，在本批已测试配置中选平均完整退出时间最短者：','',
            '| 目标 | 配置 | 两类主场景最低实测清除率 |','|---|---|---:|']
    for goal in [1.,.99,.98,.95,.90]:
        eligible=[t for t in ['strict','fast99','fast98','fast95','fast90']
                  if (goal<1 or t=='strict') and all(stats[('compact_'+t,sc)]['rate']>=goal for sc in ['mixed_uniform','uniform'])]
        tier=min(eligible,key=lambda t:sum(stats[('compact_'+t,sc)]['exit_s'] for sc in ['mixed_uniform','uniform']))
        rate=min(stats[('compact_'+tier,sc)]['rate'] for sc in ['mixed_uniform','uniform'])
        lines.append(f'| {goal:.0%} | {tier} | {rate:.2%} |')
    lines+=['','此表是留出结果的描述性选档，速度档未承诺未来局数的置信下限达到该目标；为这些推荐再给出泛化保证需要额外数据。要求任意合法布局全清时只用strict。']
    lines+=['','## 策略','',
            '1. 原点检测20个频道；使用21站严格布局：原点 + 998 m×8（相位0°）+ 1867 m×12（相位15°）。',
            '2. 对只有一个方位的频道，结合实际无信号记录，对位置、接收半径和定向朝向做数值积分。其均值只用于规划；仍完整保留由正观测得到的保守可行多边形，并重算包围半径。',
            '3. 把待扫描站与待清目标联合排入开放航路。上一轮航路热启动，加5个最近邻起点；每个候选最多4轮2-opt和单点移位。目标同时计入路程和预计后续检测代价，只执行首站后重规划。',
            '4. 扫描时顺便给单方位目标补测。定位沿用100 m短横向基线、双侧无信号合法约束与28 m方格清除兜底。',
            '5. 所有频道均成功清除或取得连续无源证明，才认证完整退出。证明覆盖全靶区和任意180°发射朝向；预算不足明确返回未完成。','',
            '信息排路采用独立固定1024个参考状态（位置按面积均匀、方向均匀、接收半径1000–1500 m）。后验位置积分使用150个距离点、9个半径点、36个朝向点及50%全向先验。这些是估价模型，未使用模拟器的真实源数、坐标、朝向或误差场。','',
            '21站布局通过自适应连续证明：40 → 20 → 10 → 5 → 2.5 m，只细分未证明方格。每个方格仍要求带空间余量的完整连续角区间并集覆盖，绝非中心采样通过。原点与全部计划站只能证明布局可行；最终完成证书逐频道只使用实际无信号回复。','',
            '![扫描站布局](../out/p4_compact_validation/layouts.png)','',
            '严格档保持不删站、不依赖源数量停止。速度档沿用上一版各稀疏环形布局，新增位置估计和排路；继承的删站只保留原稀疏布局的保守离散覆盖下界，不提供100%保证。自适应旋转、直接扑向单方位估计点、自由选覆盖点、连续移动测站等变体未稳定胜出。','',
            '## 压力场景与旧策略','',
            '| 场景 | 上一版 strict | 新 strict | 全清 / 认证 |',
            '|---|---:|---:|---:|']
    for sc in ['edge','minrange','omni','mixed']:
        a=stats[('strict',sc)];b=stats[('compact_strict',sc)]
        lines.append(f"| {labels[sc]} | {a['exit_s']:.0f} s | {b['exit_s']:.0f} s | {b['full']}/{b['cases']} / {b['certified']}/{b['cases']} |")
    lines+=['','速度档压力测试（各20局）表明，参考分布的高平均清除率不能推广到任意源布局：','',
            '| 配置 | 贴边朝外清除率 | 最小接收半径清除率 |','|---|---:|---:|']
    for tier in ['fast99','fast98','fast95','fast90']:
        a=stats[('compact_'+tier,'edge')];b=stats[('compact_'+tier,'minrange')]
        lines.append(f"| {tier} | {a['rate']:.2%} | {b['rate']:.2%} |")
    lines+=['','| 原始 legacy / 场景 | 清除率 | 完整退出 | 新strict时间减少 |','|---|---:|---:|---:|']
    for sc in ['mixed_uniform','uniform']:
        a=stats[('legacy',sc)];b=stats[('compact_strict',sc)]
        lines.append(f"| {labels[sc]} | {a['rate']:.2%} | {a['exit_s']:.0f} s | {1-b['exit_s']/a['exit_s']:.1%} |")
    lines+=['','原始策略在本批新种子中有遗漏，因此不能把它当作100%全清基线；本报告主要比较双方均全清的上一版strict。','',
            '## 复现与校验','',
            '以下在仓库根目录运行，默认入口已接入新严格档；`--policy joint` 保留上一版，`--policy grid` 保留原始策略。','',
            '```powershell',
            'python B_locator/Q4/src/p4_run.py --mode mock --policy compact --tier strict --scenario uniform --cases 20',
            'python B_locator/Q4/src/p4_run.py --mode mock --policy compact --tier fast95 --scenario uniform --cases 20',
            'python B_locator/Q4/src/p4_run.py --geometry',
            'python B_locator/Q4/src/p4_compact_checks.py',
            'python B_locator/Q4/src/p4_layout_v2_checks.py',
            'python B_locator/Q4/src/p4_route_v2_checks.py',
            'python B_locator/Q4/src/p4_compact_report.py',
            '```','',
            f"本报告读取{len(allrows)}次离线运行，拒绝动作合计{payload['rejected']}。核心文件SHA256、精确命令参数、原始日志哈希和完整汇总见 [results.json](../out/p4_compact_validation/results.json)。每组原始数据同时保存实际完整配置。没有调用线上模拟器。",'',
            '6项策略检查、5项布局检查、3项路由检查通过；覆盖协议隔离、从动作账本重算全部时间、空场完整探索、60个边界/最小接收半径源、低预算不误报完成、正观测不作缺源证明、估计中心不缩小可行域。入口离线烟测2局也全部清除并认证。', '',
            '运行时间记录为策略run()墙钟耗时（含本地终止认证）；并行评测时会受机器负载影响，不是题目的虚拟耗时。旧报告保留为历史对照：[第一轮问题四优化](p4-search-design.md)。','']
    lines+=['完整留出评测命令：','','```powershell']
    for name in FILES:
        args=manifests[name]['args']
        lines.append(f"python B_locator/Q4/src/p4_improve_bench.py --policies {args['policies']} --scenarios {args['scenarios']} --cases {args['cases']} --seed {args['seed']} --stride {args['stride']} --out {args['out']}")
    lines+=['```','']
    (ROOT/'review/p4-compact-design.md').write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps({k:payload[k] for k in ['validation_runs','strict_runs','strict_sources','rejected']},indent=2))


if __name__=='__main__':main()
