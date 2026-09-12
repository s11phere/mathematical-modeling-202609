"""Produce figures and a Chinese report from frozen joint-policy validation."""
import json
import math
import os
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/p3_joint_validation'
os.environ.setdefault('MPLCONFIGDIR',str(OUT/'mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties


def main():
    data=json.loads((OUT/'paired_results.json').read_text(encoding='utf-8'))
    labels={'random':'随机分布','annulus':'外圈分布','center':'中心聚集','hash':'非平滑误差','worstrecv':'接收半径 1000 m','live1':'重建布局 1','live2':'重建布局 2'}
    groups=data['scenarios'];names=list(groups)
    font=Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'font.size':10,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(13,5.5),layout='constrained',gridspec_kw={'width_ratios':[1.4,1]})
    ax=axes[0];y=np.arange(len(names))
    for name,offset,color,label in [('tour',-.24,'#c9ced6','原始 tour'),('adaptive',0,'#75869e','上一版 adaptive'),('joint',.24,'#147f89','新 joint')]:
        vals=[groups[n]['summary'][name]['mean_s'] for n in names]
        ax.barh(y+offset,vals,.22,color=color,label=label)
    ax.axvline(2800,color='#a74429',ls='--',lw=1,label='2800 s 目标')
    ax.set_yticks(y,[labels[n] for n in names]);ax.set_ylim(len(names)+.4,-.6)
    ax.set_xlim(0,5100);ax.set_xlabel('完整退出时间（s）');ax.set_title('相同场景逐局配对：均值')
    for i,n in enumerate(names):
        s=groups[n]['summary']
        ax.text(max(s[p]['mean_s'] for p in ('tour','adaptive','joint'))+45,i,f"再省 {s['joint_vs_adaptive']['saved_fraction']:.1%}",va='center',fontsize=9)
    ax.legend(loc='lower left',ncols=2,frameon=False,fontsize=9)
    ax=axes[1];rows=groups['random']['rows']
    a=np.array([r['adaptive']['virtual_time_s'] for r in rows]);b=np.array([r['joint']['virtual_time_s'] for r in rows])
    ax.plot([2400,4100],[2400,4100],ls='--',color='#aeb7c1',label='相同耗时')
    ax.scatter(a,b,color='#147f89',s=25,alpha=.8)
    ax.axhline(2800,color='#a74429',ls=':',lw=1)
    ax.set(xlim=(2400,4100),ylim=(2400,4100),xlabel='上一版 adaptive（s）',ylabel='新 joint（s）',title='新随机 50 局：48 局更快')
    ax.set_aspect('equal');ax.legend(frameon=False)
    fig.suptitle('B 题第三问：进一步优化，平均仍未达到 2800 s',fontsize=14)
    fig.savefig(OUT/'comparison.png',dpi=170);plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(11,5.8),layout='constrained')
    for ax,name,color in zip(axes,('adaptive','joint'),('#75869e','#147f89')):
        trace=json.loads((OUT/f'random_918000_{name}_trace.json').read_text(encoding='utf-8'))
        pts=np.array([(0.,0.)]+[(a['x'],a['y']) for a in trace['actions'] if 'x' in a])
        sources=np.array([(s['x_m'],s['y_m']) for s in trace['truth']['sources']])
        theta=np.linspace(0,2*np.pi,400)
        ax.plot(1800*np.cos(theta),1800*np.sin(theta),color='#c9ced6')
        ax.plot(pts[:,0],pts[:,1],color=color,lw=1.2)
        ax.scatter(sources[:,0],sources[:,1],marker='*',s=35,color='#a74429',zorder=4,label='源位（事后绘图）')
        ax.scatter([0],[0],marker='s',s=20,color='#252a35',label='原点')
        ax.set(xlim=(-1950,1950),ylim=(-1950,1950),xlabel='x / m',ylabel='y / m',title=f"{name} · {trace['actions'][-1]['virtual_time_s']:.0f} s")
        ax.set_aspect('equal');ax.legend(frameon=False,loc='upper right',fontsize=9)
    fig.suptitle('固定展示第一局新验证场景（seed 918000）',fontsize=14)
    fig.savefig(OUT/'route_example.png',dpi=170);plt.close(fig)

    # Independently recompute saved raw traces' physics and switching costs.
    maxerr=0.;trace_count=0
    for p in OUT.glob('*_trace.json'):
        trace=json.loads(p.read_text(encoding='utf-8'));pos=(0.,0.);channel=1;t=0.
        for action in trace['actions']:
            kind=action['kind']
            if kind=='measure':
                t+=math.dist(pos,(action['x'],action['y']))/5+5+(action['channel']!=channel)
                channel=action['channel'];pos=(action['x'],action['y'])
            elif kind=='clear':
                t+=math.dist(pos,(action['x'],action['y']))/5+(5 if action['clear_result']=='success' else 3)
                pos=(action['x'],action['y'])
            maxerr=max(maxerr,abs(t-action['virtual_time_s']))
        trace_count+=1
    assert maxerr<1e-7
    r=groups['random']['summary'];a=r['adaptive'];b=r['joint'];o=r['tour']
    allrows=[r for g in groups.values() for r in g['rows']]
    assert not any('error' in r for r in allrows)
    assert all(r['joint']['cleared']==r['joint']['n_sources'] and r['joint']['complete_proof'] and not r['joint']['n_rejected'] for r in allrows)
    n_sources=sum(r['joint']['cleared'] for r in allrows)
    lines=['# B 题第三问：进一步联合优化航路与检测','',
    f"结果：新增 `--policy joint`。新随机 50 局的完整退出时间从上一版 **{a['mean_s']:.0f} s 降至 {b['mean_s']:.0f} s**，进一步降低 **{r['joint_vs_adaptive']['saved_fraction']:.1%}**。与用户最初的 tour 相比，同一批场景从 {o['mean_s']:.0f} s 降至 {b['mean_s']:.0f} s，降低 {r['joint_vs_tour']['saved_fraction']:.1%}。**尚未达到平均 2800 s**。",'',
    '用户已明确按从 `/enter` 到 `/exit` 的完整虚拟时间优化。对方的计时口径、源数与场景未知，因此本报告不推断双方算法优劣，也不将最后清除时刻当成退出时间。','',
    '## 这次改变了什么','',
    '1. **先清除，再在实际终点扫描。** 上一版按估计目标位置承担覆盖职责，单方位目标还会先在中途补测。现在到一个目标的服务流程是逼近定位、确认清除，再给剩余频道测量；下一轮依据真实检测坐标重排。',
    '2. **联合优化测站和扫描次数。** 每轮生成五条不同权重的覆盖航路，按 `行程/5 + 6×预计无信号频道检测数` 比较，不再直接执行单一贪心评分产生的结果。这个成本是规划近似；最终实验计时全部取真实动作账本。',
    '3. **删站、移站。** 如果其余计划站已覆盖全部必要单元，则删除冗余站或取消目标的覆盖职责；其余临时站先在候选格点中换位，再沿通往航路的线段连续移动。移动量受每个必需单元的接收圆约束，不能因缩短路线而放弃覆盖。',
    '4. **少做收益低的额外方位测量。** 单方位源的区域若距离当前点超过 1500 m，则跳过该次顺手补测；另以均匀面积/接收半径先验估计接收机会，低于 50% 的补测也延后。这个概率只决定可选补测，目标仍保留在清除队列，完工证明仍完全确定。',
    '5. **先尝试光学清除，失败就原地重测。** 两条以上方位且外包半径不超过 400 m 时，先尝试估计中心；失败不算清除，立即在同一点测量，再自适应逼近。这样避免部分本来可以直接成功的额外测量，也避免试探失败后无必要地横移。',
    '6. **修复末期路由与近邻补站。** 两三个目标也精确枚举顺序；取消旧循环无条件跳过 60 m 内补站的规则，靠真实信息进展和迭代限制防止空转。','',
    '## 冻结后的新场景验证','',
    '开发集使用 `20260913 + 100i`。下表使用此前未用于选择本轮策略的 `918000 + 53i`；三个策略分别运行重新创建的相同场景，固定参数后才进入此验证。没有在线模拟器调用。','',
    '| 场景 | 局数 | 原始 tour/s | 上一版 adaptive/s | 新 joint/s | 比上一版再省 |',
    '|---|---:|---:|---:|---:|---:|']
    for n,g in groups.items():
        s=g['summary']
        lines.append(f"| {labels[n]} | {s['cases']} | {s['tour']['mean_s']:.0f} | {s['adaptive']['mean_s']:.0f} | {s['joint']['mean_s']:.0f} | {s['joint_vs_adaptive']['saved_fraction']:.1%} |")
    lines += ['',f"**{len(allrows)}/{len(allrows)} 局全清，{n_sources}/{n_sources} 个源清除，新策略每局均通过连续覆盖证书，接口拒绝数为 0。** 重建布局仅使用历史源坐标，接收半径假定为 1400 m，每局改变误差；它们不是实际在线测试。",'',
    '![配对对比](../out/p3_joint_validation/comparison.png)','',
    '随机集 48/50 局快于 adaptive。平均节省比例的配对 bootstrap 95% 区间为 **5.7%–8.0%**，仅描述该离线生成器的采样不确定性。P90 从 **3653 s 降至 3467 s**，最坏局从 **3996 s 降至 3697 s**。50 局中只有 7 局完整时间低于 2800 s，不能据此宣称平均达到该目标。','',
    '| 随机集指标 | adaptive | joint |',
    '|---|---:|---:|',
    f"| 平均完整退出时间/s | {a['mean_s']:.1f} | {b['mean_s']:.1f} |",
    f"| 平均最后清除时刻/s | {a['last_clear_mean_s']:.1f} | {b['last_clear_mean_s']:.1f} |",
    f"| 平均行程/m | {a['travel_mean_m']:.0f} | {b['travel_mean_m']:.0f} |",
    f"| 平均检测次数 | {a['measure_mean']:.2f} | {b['measure_mean']:.2f} |",
    f"| 平均光学清除失败次数 | {a['clear_fail_mean']:.2f} | {b['clear_fail_mean']:.2f} |",
    f"| 本机平均策略运行时间/s | {a['wall_mean_s']:.2f} | {b['wall_mean_s']:.2f} |",'',
    '本轮收益主要是减少重复检测：随机集少约 30 次检测，行程只短约 284 m。光学试探失败次数有所增加，但其时间代价已经计入全部结果。更复杂的规划仍平均约 1.17 s/局，不含网络延迟。','',
    '![首局航路](../out/p3_joint_validation/route_example.png)','',
    '## 尝试过但未选用的方向','',
    '这轮同时测试了共享大范围预扫描、先测绘再清除、跳过原点扫描、按极角绕行、先内后外、更多 TSP 邻域交换、单方位距离后验、正负接收距离排序约束、更细覆盖网格、沿路线密集加入候选站、更激进地直接逼近估计源位。',
    '预扫描方向的独立开发对照为：10 局 adaptive 3312 s；1000 m 单站 3349 s、两站 3581 s；1300 m 六站再清除 4414 s。更多预扫描减少了部分检测，却增加重新穿越靶区的行程。其余单项也没有显示足够稳定的额外收益；未因某个小样本低值替换冻结方案。',
    '本轮最好的 20 局开发结果为约 3033 s，样本外为约 3090 s。这说明不能把开发集偶然更低的数字当成稳定收益。尚未找到能稳定比最初方案减少约三成、达到平均 2800 s 的方法，也没有证明这个目标不可达。','',
    '## 完工与验证','',
    '继续采用逐频道连续圆域覆盖证书：保留与靶区相交的 50 m 方格，只将真实 `no_signal` 测点半径 `1000−50/√2−10⁻⁶` 内的单元中心视为整格可排除。`near` 和 `direction` 都阻止“无源”结论，直到清除确认成功。计划站承担职责只是规划信息，只有实际测量才能更新证书。',
    '候选站连续平移时，保留所有原本只能由它覆盖的单元。沿线段移动参数逐个求解二次不等式，取全部接收圆容许范围的交集。12 项检查覆盖了几何边界反例、near 台账、未测点不计覆盖、计划不执行动作、移站后完整覆盖、两三目标的最短顺序、实际终点扫描、失败原地重测、可选概率过滤不能丢弃必清目标及端到端运行期间不读取真值。',
    f'另对保存的 {trace_count} 份原始动作轨迹独立重算移动、检测、频道切换和清除成本，最大累计时间偏差为 {maxerr:.2e} s。策略的源文件哈希随验证数据保存。',
    '预算不足、接口失败或迭代上限仍可能使其他合法场景未完成；返回结果中的 `complete_proof` 必须检查。当前完整清除结果是以上测试证据，不是有限预算下适用于所有场景的性能定理。','',
    '## 使用与复现','',
    '从项目根目录运行：','',
    '```powershell',
    'python B_locator/Q3/src/p3_run.py --mode mock --cases 30 --out B_locator/Q3/out/p3_joint   # 默认策略即 joint',
    'python B_locator/Q3/src/p3_joint_checks.py',
    'python B_locator/Q3/src/p3_joint_bench.py',
    'python B_locator/Q3/src/p3_joint_report.py','```','',
    '实现：[p3_joint.py](../src/p3_joint.py)。`tour` 与 `adaptive` 保留作对照。**joint 现为 `--policy` 的默认值**（`src/p3_run.py` 的 `DEFAULT_POLICY`）——不写 `--policy` 时跑的就是这一套，做对照实验请显式写 `--policy tour` / `--policy adaptive`。命令行入口为 joint 保留 `min_move=0`，避免基类默认值覆盖近邻补站行为。',
    '逐局数据：[JSON](../out/p3_joint_validation/paired_results.json)、[CSV](../out/p3_joint_validation/paired_results.csv)。前三局各策略的原始动作也保存在同目录。开发原型为 `p3_survey.py`、`p3_orbit.py`，开发批次入口为 `p3_joint_dev.py`。','']
    (ROOT/'review/p3-joint-design.md').write_text('\n'.join(lines),encoding='utf-8')
    print(f'Report written; {trace_count} raw traces audited; max time error {maxerr:.2e} s')


if __name__=='__main__':main()
