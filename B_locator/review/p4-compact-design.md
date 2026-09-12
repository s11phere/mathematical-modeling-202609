# 问题四第二轮优化：21 站、后验估计与信息排路

主目标：全部清除后的完整 `/enter` → `/exit` 虚拟时间。最终配置已冻结，下面使用新种子族 `2219000+79i` 做独立配对验证。没有证明全局最优。

## 全清结果

| 场景 | 上一版整局 → 新版整局 | 节省 | 上一版每源 → 新版每源 | 新版最后清除口径每源 |
|---|---:|---:|---:|---:|
| 混合源（50%定向） | 6576 → **5933 s** | **9.8%** | 513.8 → **463.3 s** | 429.6 s |
| 全定向（随机朝向） | 7200 → **6491 s** | **9.8%** | 562.5 → **506.2 s** | 476.5 s |

新严格档全部 **360 局、4668 个源**完成清除，连续无源/已清除认证 360/360。包含两类主场景各100局，四类压力场景各40局。

每源主指标先按每局 `退出时间/清除数` 计算，再对各局求平均。最后清除时刻不含随后排除未知频道的时间，不能用它代替完整退出口径。另一个口径“所有局退出时间之和/清除数之和”也保留在 results.json；源数不同会使两个均值不同。

| 场景 | 新版整局均值95% CI | 配对节省95% CI | 完整退出总时间/总清除数 |
|---|---:|---:|---:|
| 混合源（50%定向） | 5866–6000 s | 557–730 s | 453.6 s/源 |
| 全定向（随机朝向） | 6417–6567 s | 614–807 s | 496.2 s/源 |

按场景 bootstrap 5000 次，保留同一局内相关性；不将零失败样本的退化区间当成数学上的100%保证。严格档的完成依据是覆盖证明和清除兜底。

**目前仍不能宣称在完整退出且全清的口径下稳定达到 450 s/源。** 混合比例、源数、位置分布和计时口径都会改变结果；对方指标缺少这些信息，不能直接认定同口径优劣。

## 清除率与时间取舍

以下各配置仍然清完所有已听到目标，降低的是未知源搜索的覆盖程度。档名只是目标名称，实际清除率必须看实测；不是每局保证。

| 新配置 | 混合源：清除率 / 完整退出 / 每源 | 全定向：清除率 / 完整退出 / 每源 |
|---|---:|---:|
| strict | 100.00% / 5933 s / 463.3 s | 100.00% / 6491 s / 506.2 s |
| fast99 | 99.77% / 5453 s / 426.2 s | 99.69% / 5976 s / 466.9 s |
| fast98 | 98.47% / 4888 s / 386.8 s | 97.17% / 5573 s / 446.2 s |
| fast95 | 97.86% / 4685 s / 372.9 s | 95.34% / 5277 s / 431.6 s |
| fast90 | 95.34% / 4141 s / 338.0 s | 89.60% / 4659 s / 406.1 s |

![清除率与完整时间](../out/p4_compact_validation/pareto.png)

源数未知，100%档按证据完成退出。速度档根据预设扫描布局完成退出，不能判断本局真实清除率。每局10–16源时，遗漏一个已损失6.25%–10%；90%、95%、98%只能用作分布下多局累计目标。

| 配置 / 场景 | 清除率95% CI | 整局全清 | 相对上一版同名档节省 |
|---|---:|---:|---:|
| fast99 / 混合源（50%定向） | 99.47%–100.00% | 97/100 | 4.0% |
| fast99 / 全定向（随机朝向） | 99.38%–99.93% | 96/100 | 4.9% |
| fast98 / 混合源（50%定向） | 97.82%–99.08% | 81/100 | 4.7% |
| fast98 / 全定向（随机朝向） | 96.21%–98.07% | 71/100 | 1.7% |
| fast95 / 混合源（50%定向） | 97.22%–98.51% | 72/100 | 4.0% |
| fast95 / 全定向（随机朝向） | 94.15%–96.46% | 54/100 | 2.4% |
| fast90 / 混合源（50%定向） | 94.36%–96.29% | 48/100 | 2.3% |
| fast90 / 全定向（随机朝向） | 87.99%–91.16% | 23/100 | 约持平 |

按两类主场景的实测累计清除率均达到目标，在本批已测试配置中选平均完整退出时间最短者：

| 目标 | 配置 | 两类主场景最低实测清除率 |
|---|---|---:|
| 100% | strict | 100.00% |
| 99% | fast99 | 99.69% |
| 98% | fast99 | 99.69% |
| 95% | fast95 | 95.34% |
| 90% | fast95 | 95.34% |

此表是留出结果的描述性选档，速度档未承诺未来局数的置信下限达到该目标；为这些推荐再给出泛化保证需要额外数据。要求任意合法布局全清时只用strict。

## 策略

1. 原点检测20个频道；使用21站严格布局：原点 + 998 m×8（相位0°）+ 1867 m×12（相位15°）。
2. 对只有一个方位的频道，结合实际无信号记录，对位置、接收半径和定向朝向做数值积分。其均值只用于规划；仍完整保留由正观测得到的保守可行多边形，并重算包围半径。
3. 把待扫描站与待清目标联合排入开放航路。上一轮航路热启动，加5个最近邻起点；每个候选最多4轮2-opt和单点移位。目标同时计入路程和预计后续检测代价，只执行首站后重规划。
4. 扫描时顺便给单方位目标补测。定位沿用100 m短横向基线、双侧无信号合法约束与28 m方格清除兜底。
5. 所有频道均成功清除或取得连续无源证明，才认证完整退出。证明覆盖全靶区和任意180°发射朝向；预算不足明确返回未完成。

信息排路采用独立固定1024个参考状态（位置按面积均匀、方向均匀、接收半径1000–1500 m）。后验位置积分使用150个距离点、9个半径点、36个朝向点及50%全向先验。这些是估价模型，未使用模拟器的真实源数、坐标、朝向或误差场。

21站布局通过自适应连续证明：40 → 20 → 10 → 5 → 2.5 m，只细分未证明方格。每个方格仍要求带空间余量的完整连续角区间并集覆盖，绝非中心采样通过。原点与全部计划站只能证明布局可行；最终完成证书逐频道只使用实际无信号回复。

![扫描站布局](../out/p4_compact_validation/layouts.png)

严格档保持不删站、不依赖源数量停止。速度档沿用上一版各稀疏环形布局，新增位置估计和排路；继承的删站只保留原稀疏布局的保守离散覆盖下界，不提供100%保证。自适应旋转、直接扑向单方位估计点、自由选覆盖点、连续移动测站等变体未稳定胜出。

## 压力场景与旧策略

| 场景 | 上一版 strict | 新 strict | 全清 / 认证 |
|---|---:|---:|---:|
| 贴边朝外 | 8349 s | 7416 s | 40/40 / 40/40 |
| 最小接收半径 | 7310 s | 6556 s | 40/40 / 40/40 |
| 全向源 | 6025 s | 5316 s | 40/40 / 40/40 |
| 原径向偏好混合 | 6525 s | 5715 s | 40/40 / 40/40 |

速度档压力测试（各20局）表明，参考分布的高平均清除率不能推广到任意源布局：

| 配置 | 贴边朝外清除率 | 最小接收半径清除率 |
|---|---:|---:|
| fast99 | 80.31% | 98.43% |
| fast98 | 0.00% | 90.16% |
| fast95 | 0.00% | 88.19% |
| fast90 | 0.00% | 79.53% |

| 原始 legacy / 场景 | 清除率 | 完整退出 | 新strict时间减少 |
|---|---:|---:|---:|
| 混合源（50%定向） | 99.69% | 8532 s | 30.5% |
| 全定向（随机朝向） | 99.77% | 9034 s | 28.2% |

原始策略在本批新种子中有遗漏，因此不能把它当作100%全清基线；本报告主要比较双方均全清的上一版strict。

## 复现与校验

以下在仓库根目录运行，默认入口已接入新严格档；`--policy joint` 保留上一版，`--policy grid` 保留原始策略。

```powershell
python B_locator/src/p4_run.py --mode mock --policy compact --tier strict --scenario uniform --cases 20
python B_locator/src/p4_run.py --mode mock --policy compact --tier fast95 --scenario uniform --cases 20
python B_locator/src/p4_run.py --geometry
python B_locator/src/p4_compact_checks.py
python B_locator/src/p4_layout_v2_checks.py
python B_locator/src/p4_route_v2_checks.py
python B_locator/src/p4_compact_report.py
```

本报告读取2680次离线运行，拒绝动作合计0。核心文件SHA256、精确命令参数、原始日志哈希和完整汇总见 [results.json](../out/p4_compact_validation/results.json)。每组原始数据同时保存实际完整配置。没有调用线上模拟器。

6项策略检查、5项布局检查、3项路由检查通过；覆盖协议隔离、从动作账本重算全部时间、空场完整探索、60个边界/最小接收半径源、低预算不误报完成、正观测不作缺源证明、估计中心不缩小可行域。入口离线烟测2局也全部清除并认证。

运行时间记录为策略run()墙钟耗时（含本地终止认证）；并行评测时会受机器负载影响，不是题目的虚拟耗时。旧报告保留为历史对照：[第一轮问题四优化](p4-search-design.md)。

完整留出评测命令：

```powershell
python B_locator/src/p4_improve_bench.py --policies compact_strict --scenarios mixed_uniform,uniform --cases 100 --seed 2219000 --stride 79 --out B_locator/out/p4_compact_validation/main_new.jsonl
python B_locator/src/p4_improve_bench.py --policies strict,legacy --scenarios mixed_uniform,uniform --cases 100 --seed 2219000 --stride 79 --out B_locator/out/p4_compact_validation/main_base.jsonl
python B_locator/src/p4_improve_bench.py --policies compact_strict,strict --scenarios edge,minrange,omni,mixed --cases 40 --seed 2219000 --stride 79 --out B_locator/out/p4_compact_validation/stress.jsonl
python B_locator/src/p4_improve_bench.py --policies compact_fast99,compact_fast98,compact_fast95,compact_fast90 --scenarios mixed_uniform,uniform --cases 100 --seed 2219000 --stride 79 --out B_locator/out/p4_compact_validation/fast_new.jsonl
python B_locator/src/p4_improve_bench.py --policies fast99,fast98,fast95,fast90 --scenarios mixed_uniform,uniform --cases 100 --seed 2219000 --stride 79 --out B_locator/out/p4_compact_validation/fast_base.jsonl
python B_locator/src/p4_improve_bench.py --policies compact_fast99,compact_fast98,compact_fast95,compact_fast90 --scenarios edge,minrange --cases 20 --seed 2219000 --stride 79 --out B_locator/out/p4_compact_validation/fast_stress.jsonl
```
