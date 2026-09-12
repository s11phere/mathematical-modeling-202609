"""Rebuild the Q4 validation report and exportable figures from frozen runs."""
from __future__ import annotations
import csv
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from p4_search_bench import summary

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/p4_search_validation'
POLICIES=['strict','fast99','fast98','fast95','fast90']
SCENARIOS=['mixed_uniform','uniform']


def bootstrap(group,seed=99331):
    rng=np.random.default_rng(seed)
    ii=rng.integers(0,len(group),size=(5000,len(group)))
    counts=np.array([(r['cleared'],r['total']) for r in group])
    rates=counts[ii,0].sum(axis=1)/counts[ii,1].sum(axis=1)
    times=np.array([r['exit_s'] for r in group])[ii].mean(axis=1)
    return dict(rate_ci=np.quantile(rates,[.025,.975]).tolist(),
                mean_exit_ci=np.quantile(times,[.025,.975]).tolist())


def table(rows,policies=POLICIES):
    lines=['| 配置 | 混合源：清除率 / 完整退出 | 全定向：清除率 / 完整退出 |',
           '|---|---:|---:|']
    for policy in policies:
        cells=[]
        for scenario in SCENARIOS:
            r=next(r for r in rows if r['policy']==policy and r['scenario']==scenario)
            cells.append(f"{100*r['rate']:.2f}% / {r['exit_s']:,.0f} s")
        lines.append(f"| `{policy}` | {' | '.join(cells)} |")
    return '\n'.join(lines)


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    paths=[OUT/'new_main.jsonl',OUT/'legacy_main.jsonl',OUT/'stress.jsonl']
    rows=[json.loads(line) for path in paths for line in path.read_text(encoding='utf8').splitlines()]
    hashes=[json.loads(p.with_suffix('.meta.json').read_text())['files'] for p in paths]
    assert all(h==hashes[0] for h in hashes),'Mixed algorithm versions in validation'
    for name,digest in hashes[0].items():
        assert hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest()==digest,name
    stats=summary(rows)
    for r in stats:
        group=[x for x in rows if (x['policy'],x['scenario'])==(r['policy'],r['scenario'])]
        r.update(bootstrap(group))
        r['p95_exit_s']=float(np.quantile([x['exit_s'] for x in group],.95))
        r['certified_cases']=sum(x['completion_certified'] is True for x in group)
        r['rejected']=sum(x['rejected'] for x in group)
    paired=[]
    for scenario in SCENARIOS:
        base={r['seed']:r for r in rows if r['scenario']==scenario and r['policy']=='legacy'}
        for policy in POLICIES:
            new=[r for r in rows if r['scenario']==scenario and r['policy']==policy]
            rng=np.random.default_rng(7729)
            gains=np.array([base[r['seed']]['exit_s']-r['exit_s'] for r in new])
            ii=rng.integers(0,len(new),(5000,len(new)))
            full=[r for r in new if r['cleared']==r['total'] and base[r['seed']]['cleared']==base[r['seed']]['total']]
            paired.append(dict(scenario=scenario,policy=policy,saved_s=float(gains.mean()),
                               saved_ci=np.quantile(gains[ii].mean(axis=1),[.025,.975]).tolist(),
                               mean_reduction=1-np.mean([r['exit_s'] for r in new])/np.mean([r['exit_s'] for r in base.values()]),
                               both_full_cases=len(full),
                               both_full_saved_s=float(np.mean([base[r['seed']]['exit_s']-r['exit_s'] for r in full])) if full else None))
    (OUT/'results.json').write_text(json.dumps(dict(summary=stats,paired=paired,source_hashes=hashes[0]),indent=2),encoding='utf8')
    with (OUT/'results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(stats[0]));writer.writeheader();writer.writerows(stats)

    colors=['#114b5f','#177e89','#37a18e','#e4aa33','#db6d28']
    fig,axs=plt.subplots(1,2,figsize=(12,5),sharey=True)
    for ax,scenario,title in zip(axs,SCENARIOS,['50% directional, uniform orientations','100% directional, uniform orientations']):
        group=[r for r in stats if r['scenario']==scenario]
        new=[next(r for r in group if r['policy']==p) for p in POLICIES]
        ax.plot([100*r['rate'] for r in new],[r['exit_s'] for r in new],color='#65a9a0',lw=1.5,zorder=1)
        for j,(r,c) in enumerate(zip(new,colors)):
            ax.scatter(100*r['rate'],r['exit_s'],s=70,color=c,zorder=3)
            ax.annotate(r['policy'],(100*r['rate'],r['exit_s']),xytext=(-7,10),textcoords='offset points',ha='right',fontsize=9,color=c)
        for r in group:
            if not r['policy'].startswith('legacy'):continue
            ax.scatter(100*r['rate'],r['exit_s'],marker='x',s=45,color='#888888')
            offset=(-5,-15) if r['policy']=='legacy_l2' and scenario=='mixed_uniform' else (-5,7)
            ax.annotate(r['policy'].replace('legacy','old'),(100*r['rate'],r['exit_s']),xytext=offset,textcoords='offset points',ha='right',fontsize=8,color='#666666')
        ax.set_title(title,fontsize=11);ax.set_xlabel('Source clearance (%)');ax.grid(alpha=.2)
        ax.set_xlim(max(65,min(100*r['rate'] for r in group)-3),101)
    axs[0].set_ylabel('Mean full enter-to-exit virtual time (s)')
    axs[0].set_ylim(3800,max(r['exit_s'] for r in stats if r['scenario'] in SCENARIOS)+500)
    fig.suptitle('Q4: frozen policies, 100 paired held-out scenes per panel',fontsize=13)
    fig.tight_layout();fig.savefig(OUT/'pareto.png',dpi=180);fig.savefig(OUT/'pareto.svg');plt.close(fig)

    fig,axs=plt.subplots(1,2,figsize=(12,4.8),sharey=True)
    labels=['legacy']+POLICIES
    for ax,scenario in zip(axs,SCENARIOS):
        rr=[next(r for r in stats if r['policy']==p and r['scenario']==scenario) for p in labels]
        travel=np.array([r['travel_m']/5 for r in rr]);total=np.array([r['exit_s'] for r in rr])
        ax.bar(labels,travel,color='#227c9d',label='Travel')
        ax.bar(labels,total-travel,bottom=travel,color='#d4ad57',label='Measure, switch and clear')
        ax.set_title(scenario);ax.tick_params(axis='x',rotation=30);ax.grid(axis='y',alpha=.2)
    axs[0].set_ylabel('Mean complete virtual time (s)');axs[1].legend(fontsize=9)
    fig.tight_layout();fig.savefig(OUT/'timing.png',dpi=180);plt.close(fig)

    main_stats=[r for r in stats if r['scenario'] in SCENARIOS]
    strict=[r for r in rows if r['policy']=='strict']
    text=['# 问题四优化：完整清除与速度档','',
          '目标是完整 `/enter` → `/exit` 虚拟时间。以下方案已实现并完成离线配对验证；并非全局最优性的证明。', '',
          '## 独立验证结果','',
          '每列 100 个未参与调参的场景。混合源的定向比例为 50%；所有定向源朝向在 0°–360° 均匀抽取，位置按靶区面积均匀抽取，接收半径在 1000–1500 m 均匀抽取，每局随机 10–16 个源。两组的源数与位置由相同种子生成规则确定，各策略按同一场景配对。','',
          table(main_stats), '',
          '`strict` 是要求 100% 时的配置；其余档位是离线平均清除率与时间的取舍，名称是开发期目标，不是每局保证。源数未知时，策略仅凭回复决定路线与退出，不读取真值。尤其每局只有 10–16 个源时，遗漏一个便是 6.25%–10%，所以 95% 或 98% 应理解为多局累计指标。', '',
          '**按留出结果选档：100% 用 strict；参考分布下至少98%选 fast99，约95%选 fast95，约90%选 fast90。fast98 在全定向留出集仅97.21%，不能按其名称当成98%保证。**', '',
          f"严格档在全部 {len(strict)} 个留出场景中清除了 {sum(r['cleared'] for r in strict)}/{sum(r['total'] for r in strict)} 个源，完整认证 {sum(r['completion_certified'] is True for r in strict)}/{len(strict)} 局。",'',
          '| 配置 / 场景 | 整局全清 | 最后清除时刻均值 | 完整退出均值 95% CI | 清除率 95% CI |',
          '|---|---:|---:|---:|---:|']
    for r in main_stats:
        if r['policy'] not in POLICIES:continue
        lo,hi=r['mean_exit_ci'];a,b=r['rate_ci']
        interval='连续认证；样本全部清除' if r['policy']=='strict' else f'{100*a:.2f}%–{100*b:.2f}%'
        text.append(f"| {r['policy']} / {r['scenario']} | {r['full']}/{r['cases']} | {r['last_s']:.0f} s | {lo:.0f}–{hi:.0f} s | {interval} |")
    text += ['', 'CI 通过按场景重采样 5000 次计算，保留同一局内源的相关性。零失败样本的 bootstrap 区间退化为 100%，不据此宣称统计上的零失败风险；严格档的保证来自几何覆盖与清除兜底。', '',
             '![清除率与完整退出时间](../out/p4_search_validation/pareto.png)','',
             '## 与原策略配对比较','',
             table(main_stats,['legacy','legacy_l2','legacy_l3','legacy_l4','legacy_l6']), '',
             '旧策略保持原有排路、定位和退出逻辑，仅修复极薄多边形计算最小包围圆时的浮点崩溃：失败时平移坐标重算；仍失败则采用保守包围圆。未调整其策略参数。', '',
             '| 新配置 / 场景 | 相对旧默认节省 | 配对节省时间 95% CI | 双方全清的配对数 |',
             '|---|---:|---:|---:|']
    for p in paired:
        lo,hi=p['saved_ci']
        text.append(f"| {p['policy']} / {p['scenario']} | {p['saved_s']:.0f} s（{100*p['mean_reduction']:.1f}%） | {lo:.0f}–{hi:.0f} s | {p['both_full_cases']} |")
    text += ['', '速度档节省时间同时包含允许遗漏带来的收益；公平取舍应同时比较表中的清除率。原策略的全清比例也已记录，不能仅比较时间而忽略遗漏。', '',
             '![时间组成](../out/p4_search_validation/timing.png)','',
             '以下轨迹取全定向留出集中最接近严格档时间中位数的一局，三种策略使用同一场景。图中的时间仅用于展示路径；总体结论使用上方完整留出集。','',
             '![代表性轨迹](../out/p4_search_validation/representative_paths.png)','',
             '## 策略与参数','',
             '原点先测全部频道。后续将扫描站与已听到目标放入同一条开放航路，用最近邻初始化并做 2-opt；每次只执行第一站，使用实际落点与新回复重新规划。扫描站还给适合交会的单方位目标补第二条方位，避免每个目标单独绕路定位。', '',
             '定位使用靶区、1500 m 正观测接收约束及 ±1.005° 方位楔交集。先做 100 m 短基线，再试清除区域中心，失败后按新回复逼近；接收角造成无信号时尝试另一侧。最后用间距 28 m 的方格清除盘覆盖整个可行多边形，保证不依赖接收朝向。单次无信号不排除 1000 m 圆盘；仅在满足横截面几何条件的双侧负观测下加纵向上界。', '',
             '| 配置 | 扫描布局，含原点 | 退出条件 |', '|---|---|---|',
             '| strict | 原点 + 950 m×6 + 1645.45 m×6（相位30°）+ 1900 m×12，共25站 | 所有频道已清除或持有连续无源证书 |',
             '| fast99 | 原点 + 1000 m×6 + 1850 m×9，共16站 | 完成该布局、清完已听到目标 |',
             '| fast98 | 原点 + 1000 m×4 + 1750 m×8，共13站 | 同上 |',
             '| fast95 | 原点 + 1100 m×4 + 1650 m×8，共13站 | 同上 |',
             '| fast90 | 原点 + 1450 m×8，共9站 | 同上 |', '',
             '速度档第二圈相位为 π/n，第一圈相位为0。共同配置为 `joint_route=True, scan_heard=True, home_fraction=0.6, home_lateral_m=100, opening_baseline_m=0, after_clear_scan=False`。部分布局中可删除被其他实际/剩余测点完全代替的扫描站；这不是额外的清除率保证。', '',
             '已比较 47 种稀疏布局和 12 组开关变体，再用最多40个开发场景精筛。单独替换定位只改善约5%；共同排路与扫描布局带来主要收益。先扫完再清、听到立即清、清后总是全频道补扫、禁用沿路第二方位等变体均未胜过最终配置；400 m 共享开场基线的收益不稳定，未作为默认。', '',
             '## 100% 的依据','',
             '未知朝向为任意180°半平面。对每个源位置，1000 m内的实际测点必须从各侧围住该位置。旧版径向朝内/朝外两遍不等于覆盖所有朝向；把不可达区域删掉也不能证明无源。', '',
             '新证书覆盖所有与半径1800 m靶区相交的20 m方格，使用方格外接圆半径ρ。测点q可排除整格某段连续朝向，须满足 `|q−c|+ρ≤1000`，且该朝向上 `(q−c)·d≥ρ`。对有效朝向圆弧作精确并集，覆盖完整圆周才排除整格；覆盖所有格子才排除该频道。只接受该频道实际收到的 `no_signal`，正观测、计划测点和未测频道均不能作证。', '',
             '严格档在退出前逐频道核验：已成功清除，或没有任何未清正观测且连续无源证书成立。证明依赖题设的半径下界、半角90°、固定源与有界方位误差；预算不足时明确返回未完成。25站是本轮找到并验证的可行布局，没有证明它是最少站数或最短可能航路。', '',
             '## 压力测试','',
             '另外每类40局：`minrange` 为全部定向且接收半径固定1000 m；`edge` 为半径1750–1800 m、必须从外侧才能收到的定向源；`omni` 为全向；`mixed` 复现原先带径向偏好的混合分布。', '',
             '| 场景 | 配置 | 清除率 | 整局全清 | 完整退出 |', '|---|---|---:|---:|---:|']
    for r in stats:
        if r['scenario'] in SCENARIOS:continue
        text.append(f"| {r['scenario']} | {r['policy']} | {100*r['rate']:.2f}% | {r['full']}/{r['cases']} | {r['exit_s']:.0f} s |")
    text += ['', '压力场景中速度档可能低于90%，因此在源分布未知、尤其可能贴边且指向不利时，应选择 `strict`。统计速度档的90%–99%取舍只在所列参考分布下标定。', '',
             '## 复现与产物','',
             '在项目根目录运行：','', '```powershell',
             'python B_locator/Q4/src/p4_run.py --mode mock --policy joint --tier strict --scenario uniform --cases 100',
             'python B_locator/Q4/src/p4_run.py --mode mock --policy joint --tier fast95 --scenario uniform --cases 100',
             'python B_locator/Q4/src/p4_run.py --geometry --policy joint --tier strict',
             'python B_locator/Q4/src/p4_search_report.py', '```','',
             '完整复现实验命令、随机种子和源码 SHA256 在 `B_locator/Q4/out/p4_search_validation/*.meta.json`；逐局配置和指标在三个 `.jsonl` 文件；汇总为 `results.json` 和 `results.csv`；图为可导出的 PNG/SVG。开发种子为20260914+100i，主留出集为1209000+71i，压力集为1709000+73i，数据不混用。', '',
             '23项结构检查通过（9项完整策略与回归、4项定位、10项几何）；定位检查还含300个随机/极端单源组合。完整策略检查包含20个最小接收半径的精确边界源、任意方向、低预算、计时重算与禁止退出前读取真值。在线模拟器尚未测试。','']
    (ROOT/'review/p4-search-design.md').write_text('\n'.join(text),encoding='utf8')
    print(table(main_stats))


if __name__=='__main__':main()
