"""Render saved paired benchmark data; does not rerun or retune the policies."""
from pathlib import Path
import json
import os
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/p3_adaptive_validation_v2'
os.environ.setdefault('MPLCONFIGDIR',str(OUT/'mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from p3_adaptive_bench import statistics


def main():
    data=json.loads((OUT/'paired_results.json').read_text(encoding='utf-8'))
    # Add display metrics derivable from the saved observations.
    for group in data['scenarios'].values():
        group['summary']=statistics(group['rows'])
    (OUT/'paired_results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    labels={'random':'随机分布','annulus':'外圈分布','center':'中心聚集','live1':'重建布局 1','live2':'重建布局 2','hash':'非平滑误差','worstrecv':'接收半径 1000 m'}
    font=Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():
        plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':10,'axes.unicode_minus':False})
    groups=data['scenarios'];names=list(groups)
    fig,axes=plt.subplots(1,2,figsize=(13,5.3),layout='constrained',gridspec_kw={'width_ratios':[1.4,1]})
    y=np.arange(len(names));ax=axes[0]
    old=[groups[n]['summary']['tour']['mean_s'] for n in names]
    new=[groups[n]['summary']['adaptive']['mean_s'] for n in names]
    ax.barh(y-.18,old,.34,color='#8c99aa',label='原策略 tour')
    ax.barh(y+.18,new,.34,color='#167d9a',label='新策略 adaptive')
    ax.set_yticks(y,[labels[n] for n in names]);ax.invert_yaxis()
    ax.set_xlim(0,5100);ax.set_xlabel('从 /enter 到 /exit 的虚拟时间（s）')
    ax.set_title('相同场景逐局配对：平均耗时')
    for j,n in enumerate(names):
        rate=groups[n]['summary']['improvement_fraction']
        ax.text(max(old[j],new[j])+55,j,f'{rate:+.1%}',va='center',fontsize=9)
    ax.set_ylim(len(names)+.15,-.65)
    ax.legend(loc='lower left',ncols=2,frameon=False)
    r=groups['random']['rows'];ax=axes[1]
    a=[x['tour']['virtual_time_s'] for x in r];b=[x['adaptive']['virtual_time_s'] for x in r]
    ax.plot([2500,5300],[2500,5300],color='#b2bac4',linestyle='--',label='相同耗时')
    ax.scatter(a,b,color='#167d9a',alpha=.8,s=24)
    ax.set(xlabel='原策略（s）',ylabel='新策略（s）',xlim=(2500,5300),ylim=(2500,5300),title='50 局随机场景：49 局更快')
    ax.set_aspect('equal');ax.legend(frameon=False)
    fig.suptitle('B 题第三问：沿途定位 + 动态覆盖选站',fontsize=15)
    fig.savefig(OUT/'comparison.png',dpi=170);plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(11,5.6),layout='constrained')
    for ax,name in zip(axes,('tour','adaptive')):
        tr=json.loads((OUT/f'random_777000_{name}_trace.json').read_text(encoding='utf-8'))
        pts=np.array([(0.,0.)]+[(a['x'],a['y']) for a in tr['actions'] if 'x' in a and 'y' in a])
        src=np.array([(s['x_m'],s['y_m']) for s in tr['truth']['sources']])
        th=np.linspace(0,2*np.pi,500)
        ax.plot(1800*np.cos(th),1800*np.sin(th),color='#c7cdd4',lw=1)
        ax.plot(pts[:,0],pts[:,1],color='#167d9a' if name=='adaptive' else '#8c99aa',lw=1.2,alpha=.9)
        ax.scatter(src[:,0],src[:,1],s=32,marker='*',color='#b44626',label='源位（仅用于事后绘图）',zorder=4)
        ax.scatter([0],[0],marker='s',s=25,color='#252a35',label='原点')
        final=tr['actions'][-1]['virtual_time_s']
        ax.set(title=f'{name} · {final:.0f} s',xlabel='x / m',ylabel='y / m',xlim=(-1900,1900),ylim=(-1900,1900))
        ax.set_aspect('equal');ax.legend(loc='upper right',fontsize=8,frameon=False)
    fig.suptitle('固定展示第一局验证场景（seed 777000）',fontsize=14)
    fig.savefig(OUT/'route_example.png',dpi=170);plt.close(fig)

    lines=['# B 题第三问：沿途定位与动态覆盖策略','',
    '新增 `--policy adaptive`。**冻结验证集**（`777000+37i`）上随机分布集平均总虚拟时间从 **4121 s 降到 3327 s（−19.3%）**、外圈集 **−20.1%**；但换一套从未用于调参的种子做**样本外复核**后，随机集只省 **14.9%**（外圈 19.3%、弱接收集 18.6%、中心聚集 ±0%）。所以稳定收益是"随机场景约一成半、外圈场景约两成"，没有得到能稳定降到 2000–2500 s 的方案。`adaptive` 现为可选对照（默认策略已改为 `joint`，见 [p3-joint-design.md](p3-joint-design.md)）；独立复核方法与逐项检查见 [P3-adaptive-verification.md](P3-adaptive-verification.md)。','',
    '## 策略变化','',
    '1. 原点扫描后，用一个 **400 m 的共同短基线**补测已发现频道。方向最大化各方位的横向分量平方和；不再为每个频道求 E[D] 第二测点，也不做最多三轮的局部最优点聚类。',
    '2. **一条方位也纳入清除航路**。用靶区、1500 m 最大接收范围与方位角楔界定有限区域；历史无信号记录只改善单方位距离估计。只有一条方位时先向估计位置走 55%，加至多 100 m 横向基线，再边靠近边重测，直到清除成功。',
    '3. **取消固定八点环带和角向游标**。在 900/1100/1300/1500 m 四个半径、72 个方向上提出临时覆盖候选，先排已发现目标，再按新增覆盖、插入航程和检测成本选择额外测站。目标停点也可以承担覆盖任务。',
    '4. 对联合航路做自由 2-opt，每次只执行第一站，再按实际测量重规划。已经走到哪里、测了哪个频道，均由真实动作台账决定。',
    '5. 停止条件为：每个频道已经清除，或该频道的真实无信号测点已保守覆盖整个连续靶区。没有概率早停，也不按源数猜测剩余场景。','',
    '```text','/enter → 原点全频道扫描 → 一个共享短基线',
    '循环：估计源位 + 剩余覆盖单元 → 联合选站/排路 → 执行第一站',
    '      → 逼近、重测、清除 → 用实际观测更新台账',
    '全部频道清除或连续覆盖排除 → /exit','```','',
    '## 冻结后的配对验证','',
    '开发种子为 20260913 + 100i；以下验证使用 777000 + 37i。每局两种策略分别获得重新创建的相同场景；策略参数在验证前冻结。均使用同样的速度、检测、切换与清除计时。','',
    '| 场景 | 局数 | 原总时间/s | 新总时间/s | 节省 | 新策略全清 |',
    '|---|---:|---:|---:|---:|---:|']
    for n,g in groups.items():
        s=g['summary'];a=s['tour'];b=s['adaptive']
        lines.append(f"| {labels[n]} | {s['cases']} | {a['mean_s']:.0f} | {b['mean_s']:.0f} | {s['improvement_fraction']:.1%} | {b['full_clear_cases']}/{s['cases']} |")
    lines += ['',
    '**160/160 局全部清除，2002/2002 个源清除；新策略 160 局均有连续覆盖证书，接口拒绝数为 0。** 两个重建布局仅复用历史坐标，接收半径设为 1400 m，每局改变误差种子；它们不是新的在线测试。','',
    '随机集 49/50 局更快；平均节省比例的配对 bootstrap 95% 区间为 **17.4%–21.1%**，仅描述本离线场景生成器的采样不确定性。新旧 P90 为 **3700 / 4646 s**，最坏局为 **3840 / 5112 s**。随机集平均行程从 **14.91 km 降到 11.62 km（−22.1%）**，检测从 **176.4 次降到 157.1 次**。本机平均策略执行约 0.49 s/局，不含网络延迟。','',
    '![配对结果](../out/p3_adaptive_validation_v2/comparison.png)','',
    '![首局航路](../out/p3_adaptive_validation_v2/route_example.png)','',
    '## 计时口径与适用边界','',
    '| 场景 | 原最后清除/s | 新最后清除/s | 原退出/s | 新退出/s |',
    '|---|---:|---:|---:|---:|']
    for n in ('random','center'):
        s=groups[n]['summary'];a=s['tour'];b=s['adaptive']
        lines.append(f"| {labels[n]} | {a['last_clear_mean_s']:.0f} | {b['last_clear_mean_s']:.0f} | {a['mean_s']:.0f} | {b['mean_s']:.0f} |")
    lines += ['',
    '中心聚集时全部清除更早，但保守排除整片外圈仍需时间，因此总退出时间反而增加 2.7%。这不是每种布局都能省 20% 的策略。随机集“全程÷清除数”的逐局均值由 '+f"{groups['random']['summary']['tour']['exit_per_source_mean_s']:.1f} s 降到 {groups['random']['summary']['adaptive']['exit_per_source_mean_s']:.1f} s。",'',
    '误差模型敏感性验证改用同地固定、空间不平滑的 SHA-256 位置哈希误差（幅度 ≤0.995°，再保留接口舍入），仍节省 17.1%；全部源接收半径为 1000 m 时仍节省 16.3%。这些检验不证明正式模拟器的源位分布与误差分布等同于离线模型。此次没有调用在线模拟器或消耗正式测试次数。','',
    '## 连续覆盖判据','',
    '旧版 25 m 网格仅检查格点，不能直接作为连续圆域的证明。新策略将外接正方形划分为 50 m 闭正方形，保留所有与半径 1800 m 圆域相交的单元，包括边界单元。单元中心 q 满足下式，便可由一个真实无信号测点 p 排除整个单元：','',
    r'$$\|q-p\| \le 1000-50/\sqrt{2}-10^{-6}. $$','',
    '这是三角不等式给出的保守证书：单元内任一点离中心不超过 50/√2。只使用该频道自己的 `no_signal` 记录；`direction` 与 `near` 均阻止完工，直到该频道成功清除。新策略不会因为“离骨架点很近”就推定覆盖职责已完成。证书保证完工声明的可靠性；若预算或迭代上限先耗尽，程序仍可能带 `complete_proof=false` 返回，并不宣称任何合法场景都一定在给定预算内完成。','',
    '定位区域采用 ±1.005° 加数值余量的角楔，兼容“先加 ±1° 误差再四舍五入到两位小数”的接口读数。圆域及最大接收圆使用外包切线多边形，不用概率估计缩小已认证的区域。','',
    '## 复现','',
    '以下命令从项目根目录运行：','',
    '```powershell','python B_locator/Q3/src/p3_run.py --mode mock --policy adaptive --cases 30 --out B_locator/Q3/out/p3_adaptive',
    'python B_locator/Q3/src/p3_adaptive_checks.py',
    'python B_locator/Q3/src/p3_adaptive_bench.py --out B_locator/Q3/out/p3_adaptive_validation_v2',
    'python B_locator/Q3/src/p3_adaptive_report.py','```','',
    '实现：[p3_adaptive.py](../src/p3_adaptive.py)、[p3_homing.py](../src/p3_homing.py)、[p3_frontier.py](../src/p3_frontier.py)、[p3_coverage.py](../src/p3_coverage.py)。验证通过 7 项几何/台账/端到端检查与 CLI 冒烟测试。','',
    '逐局数据：[JSON](../out/p3_adaptive_validation_v2/paired_results.json)、[CSV](../out/p3_adaptive_validation_v2/paired_results.csv)。JSON 含冻结参数、源文件 SHA-256、各局指标与失败记录；每组固定保存前三局完整动作轨迹。','']
    lines += verification_section()
    (ROOT/'review/p3-adaptive-design.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Wrote comparison.png, route_example.png and review/p3-adaptive-design.md')


def verification_section():
    """样本外复核小节：读 `out/p3_verify_oos/paired_results.json`，缺失则跳过。"""
    src = ROOT/'out/p3_verify_oos/paired_results.json'
    doc = ROOT/'review/P3-adaptive-verification.md'
    head = ['## 独立复核（样本外）','',
            '冻结验证集用的是 `777000+37i`。为了看清"−19.3%"里有多少是种子运气，'
            '另取一套**从未用于调参**的种子 `3141592+91i` 重跑同一套脚本'
            '（`out/p3_verify_oos/`），并用 `src/p3_verify_paths.py` 从模拟器原始动作台账'
            '独立重算计时与完工声明。完整报告见 '
            '[P3-adaptive-verification.md](P3-adaptive-verification.md)。','']
    if not src.exists():
        return head + ['（尚未生成样本外数据：先跑 '
                       '`python B_locator/Q3/src/p3_adaptive_bench.py --seed 3141592 --step 91 '
                       '--counts "random:50,annulus:20,center:20,worstrecv:20" '
                       '--out B_locator/Q3/out/p3_verify_oos`。）','']
    data = json.loads(src.read_text(encoding='utf-8'))
    labels = {'random':'随机分布','annulus':'外圈分布','center':'中心聚集','worstrecv':'接收半径 1000 m'}
    out = head + ['| 场景 | 局数 | 原 `tour`/s | 新 `adaptive`/s | 节省 | 配对 bootstrap 95% | 新策略更快 | 全清 |',
                  '|---|---:|---:|---:|---:|---|---:|---:|']
    for kind, group in data['scenarios'].items():
        s = statistics(group['rows'])
        a, b = s['tour'], s['adaptive']
        lo, hi = s['paired_bootstrap_95pct']
        out.append(f"| {labels.get(kind, kind)} | {s['cases']} | {a['mean_s']:.0f} | "
                   f"{b['mean_s']:.0f} | **{s['improvement_fraction']:+.1%}** | "
                   f"{lo:.1%} – {hi:.1%} | {s['adaptive_faster_cases']}/{s['cases']} | "
                   f"{b['full_clear_cases']}/{s['cases']} |")
    out += ['',
            '随机集的"−19.3%"在样本外只有 **−14.9%**（区间 12.9%–16.8%），外圈与弱接收集仍在 19% 附近；'
            '中心聚集集由"慢 2.7%"变为 **±0%**，即该布局**没有收益也没有损失**。'
            '同一份复核还用 5 m 细网格（约 40.7 万个点）独立验证了新策略的完工声明：'
            '20 局全部有证书，未被 1000 m 覆盖的最坏点距 980.4 m，无空洞。','',
            '路径图与逐案例重算明细见 `out/p3_verify/`（`paths_pair.png`、`paths_overview.png`、'
            '`time_split.png`、`verify_table.json`、`coverage_audit.json`）。','']
    if doc.exists():
        out.append('')
    return out


if __name__=='__main__':
    main()
