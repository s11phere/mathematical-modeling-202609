# 问题四数据来源与论文证据

本文集中列出模拟场景、实验输入、动作证据、统计定义和论文图表来源。附件目录
`Q4` 仅为问题四的文件标识。本文件所列策略比较、消融与压力场景数字来自离线模拟实验。
正文另列的三次正式测试结果及对应原始日志见 [正式测试说明](../formal-tests/README.md)
和 [结果汇总](../formal-tests/results.csv)，不计入下述 230 次离线运行。

## 数据与源码来源

`code/` 必要模块复制自原项目问题四源码，包括该版本依赖的公共几何和模拟器；
与问题三同名的共享文件也保留问题四实际使用的版本，避免换库改变冻结算法。
`SOURCE_MANIFEST.json` 逐文件记录原路径、源文件 SHA256、当前 SHA256 和适配说明。
原路径只作为来源元数据，不是运行依赖。

`results/manifest.json` 是当前全量重跑的实验定义，含所有任务、源码哈希、种子、环境和启动参数。
其完整源目录清单还包括未被这次实验使用的诊断脚本，本附件仅收录必要依赖与对应
专项检查。`results/runs.jsonl` 是权威逐局表，230 行分别指向一份
`results/traces/*.json.gz`，并记录压缩文件 SHA256。压缩日志含完整精度的源参数、
动作和响应、算法事件、配置与最终报告，可直接重算计费。

`data/representative_legacy.json`、`representative_joint_strict.json`、
`representative_compact_strict.json` 是主集第一例种子 2026091201 的未压缩可读
摘录，供正文案例图使用；审计同时检查其与对应压缩轨迹一致。它们不是另一批实验，
也不是策略提前知道的真值输入。本题实验无需外部 CSV，场景在运行时按下述规则生成。

本文采用 2026-09-13 在 macOS、Python 3.12.14、NumPy 2.3.5 下完整重跑的 230 次结果（两个工作进程）。所有当前正文图表与数值均取该批记录，替换先前 Windows 批次；正式测试独立保留。采纳来源与核验范围见 `results/adoption.json`、`package_validation.json`。

## 场景生成与实验矩阵

入口 `run_paper_q4.py::build_tasks` 定义全部任务，
`p4_search_bench.py::scenario_arena`、`p4_arena_ext.py::directed_case` 生成场景，
`p3_arena.py::MockArena` 提供确定地点误差场和接口计费。靶区半径 1800 m，频道
1–20，每局源数离散均匀取 10–16，频道不放回抽取，虚拟预算 360000 s。

| 实验部分 | 数量与种子 | 场景规则 |
| --- | --- | --- |
| 随机主集 `mixed_uniform` | 30 组，`2026091201 + 79*i`，`i=0…29` | 源位在圆域内面积均匀；每源以概率 0.5 为半角 90° 的定向源，朝向均匀；其余全向。接收半径均匀取 1000–1500 m。定向比例是逐源概率，不要求每局恰好一半。 |
| 最小半径 `minrange` | 10 组，`2027091201 + 79*i` | 全部定向，随机朝向，接收半径固定 1000 m；源位仍按面积均匀。 |
| 贴边朝外 `edge` | 10 组，`2028091201 + 79*i` | 源位半径均匀取 1750–1800 m，极角均匀，全部定向；接收半径 1000 m，仅从外侧半平面能收到。 |
| 全向 `omni` | 10 组，`2029091201 + 79*i` | 全部全向，源位按面积均匀，接收半径均匀取 1000–1500 m。 |
| 两项消融 | 主集前 10 组追加 20 次 | 分别只关闭 `posterior_estimate` 或 `route_information`，其余参数保持完整 `compact`。 |
| 三个快速档 | 主集前 10 组追加 30 次 | `compact_fast99`、`compact_fast95`、`compact_fast90`；名称是配置标识，不是清除概率保证。 |

四类场景各运行 `grid`、`joint`、`compact` 三代策略：60 组 × 3 = 180 次；加 20 次
消融和 30 次速度比较，共 230 次、3002 次源暴露，无结果筛选。

消融与快速档使用的完整 `compact` 基准复用主集前 10 次，不额外运行；其均值不能
用主集全部 30 次均值替代。因此 `summary.groups` 包含相同基准在不同比较组的
视图，分组数量之和不是独立运行次数。`review_tools.py` 明确实现这一复用规则。

源参数中的 `dir_deg` 是接口“测站指向源”的角度约定；论文表示物理接收方向的向量
与之相反，图中箭头采用 `dir_deg + 180°`。`edge` 使用
`dir_deg = polar_angle + 180°`，因此物理接收方向指向圆盘外侧。全向源的
`cone_half=180°`，定向源为 `90°`。

一般误差场由模拟器中固定种子的平滑正弦项与局部位置量化项构造，限于 ±1°，同一
地点误差固定。每个策略重新构造相同种子的新场景；原始实验各配对源参数哈希一致。
完整源参数只在策略退出后取得，用于评分和制图，不回流给决策。

## 策略、参数和文件标识

| 论文名称 | 逐局数据名称 | 实现 |
| --- | --- | --- |
| `grid` | `legacy` | `p4_robot.py::P4GridRobot`、`P4Config` |
| `joint` | `joint_strict` | `p4_search.py::P4SearchRobot`，`tier_config('strict')` |
| `compact` | `compact_strict` | `p4_compact.py::P4CompactRobot`，`compact_config('strict')` |
| 关闭后验中心 | `compact_no_posterior` | 仅将 `posterior_estimate=False` |
| 关闭信息代价 | `compact_no_information` | 仅将 `route_information=False` |
| `fast99/95/90` | `compact_fast99/95/90` | `compact_config` 对应档位 |

每行 `config` 保存完整有效配置，`actual_policy`、`overrides` 说明构造入口与消融
参数；`run_paper_q4.py::POLICIES` 是唯一实验映射。连续认证标志与快速档配置必须
同时读取，不可把某次经验全清当作连续覆盖保证。

## 证据字段与统计口径

逐局 `scenario`、`seed`、`policy` 唯一标识运行，`cohort` 区分主集、压力集、消融
和速度比较；`case_index` 是该场景内的零起始编号。`trace` 和 `trace_sha256`
给出动作日志的路径与校验值，`source_sha256` 是去除事后 `cleared` 标志后的源定义
哈希。日志的 `sources` 包含 `channel,x,y,r_recv,cone_half,dir_deg,cleared`；
`actions` 保存检测和清除的位置、频道、结果、行程、单步与累计时间；`events`、
`report`、`robot_stats`、`scheduled_stations` 提供算法过程与计划站位。

主指标 `exit_s` 从进入计时到退出，包含最后一次清除后的未知频道排除。独立计费为
`T = L/5 + 5*N_measure + N_switch + 5*N_success + 3*N_failure`；起点 `(0,0)`、
初始检测频道 1，只有检测动作切频，清除不切频。审计依据相邻动作位置重新计算
距离与累计时间，不以报告时间作为下一步累计基数；逐步核对距离、切频、`dt`、
累计时刻、总行程、检测数与成功/失败清除数。

`last_s` 为最后成功清除时刻，`tail_s=exit_s-last_s`。`exit_per_cleared` 和
`last_per_cleared` 均先逐局除以成功清除数再取均值；
`pooled_exit_per_cleared=sum(exit_s)/sum(cleared)` 是另一种统计，不能混用。
零清除时逐局比值为 null；本批本批记录没有零清除局。清除率为成功源总数除以源
总数，全清率按完整场景计算。失败、漏清和全部成功清除尝试均保留。

`certified` 是原策略的完成标志，只有同时满足 `certification_mode='continuous'`
才计入连续认证。本批两个严格版本共 120 次均全清且认证；最终 `compact` 的
60 次共清除 779/779 个源。只读动作审计核对原记录及统计，不把重放动作误称为
重新证明全部连续几何条件；覆盖证明实现及已有专项检查单独提供。

置信区间采用 10000 次场景级百分位 bootstrap。描述统计种子 2026091209，配对
比较种子 2026091210。`saved_s=mean(T_before-T_after)`，
`saved_fraction=saved_s/mean(T_before)`，重采样时同场景配对。消融比较方向为
“关闭模块 → 完整 compact”，速度比较方向为“完整 compact → 快速档”。论文消融
增长率由 `s/(1-s)` 变换节省率及其区间。

`runtime_s` 为本地策略执行及终止认证墙钟时间，`setup_runtime_s` 为构造与布局
认证时间，均受平台和并行负载影响，不等于题目虚拟代价，也不是正式在线运行证明。

## 论文图表、公式和数据对应

| 论文内容 | 来源与核对位置 |
| --- | --- |
| 主集完整退出均值 5840.0 s、比 `joint` 降低 10.40% | `summary.json#/groups` 的 main/mixed_uniform/compact_strict；`comparisons` 中 main 的 joint_strict → compact_strict；`table_provenance.json#/numbers`。 |
| 最终策略清除 779/779、60 次连续认证 | `runs.jsonl` 中 `policy=compact_strict` 的全部 60 行；逐行 `cleared,total,certified,certification_mode`。 |
| 主比较表及 P90 | 均值取 `summary.groups`；P90 由 `make_paper_tables.py` 对对应 `runs.jsonl` 的 `exit_s` 计算。 |
| 压力场景、消融与速度档表 | `summary.groups` 与 `comparisons` 对应的 experiment；消融/速度完整基线严格限于主集前 10 例。 |
| `q4-geometry-certificate`：接收半平面、方格朝向排除及 21 站布局 | `make_paper_figures.py::fig_geometry` 的确定性模型示意；布局来自 `p4_certificate.py`、`p4_layout_v2.py`，不是从实验中挑出的场景。 |
| `q4-homing-posterior`：定位交会、负观测与后验估计 | `make_paper_figures.py::fig_homing` 构造的确定性几何示意；实现为 `p4_homing.py`、`p4_posterior.py`。 |
| `q4-route-generations`：三代同场景轨迹 | `data/representative_*.json`；固定主集第一例 seed=2026091201，非按结果挑选。 |
| `q4-results-cost`：耗时、分项与压力结果 | `summary.groups` 的完整退出耗时、`time_components` 及各压力场景。 |
| `q4-ablation-tradeoff`：消融与速度取舍 | `summary.groups/comparisons` 的 ablation、speed 视图，配对基线为固定前 10 例。 |
| 接收模型 `eq:q4-reception` | `p3_arena.py`；接收距离与半平面必须同时成立。 |
| 连续位置/朝向证书、21 站布局 | `p4_certificate.py`、`p4_layout_v2.py`、`p4_compact.py`；六组检查与 `results/checks_summary.json`。 |
| 定位外包、负观测与清除兜底 | `p4_homing.py`；后验中心不替代保守外包和清除兜底。 |
| 后验近似、信息代价排路 | `p4_posterior.py`、`p4_route_v2.py`；对应两项单因素消融。 |
| `--figures` 生成的 `supplement.pdf` 第 1–30 页 | 随机主集全部 30 组的三代策略。 |
| 第 31–40、41–50、51–60 页 | 分别为最小接收半径、贴边朝外、全向压力集，每类 10 组。 |
| 第 61–70 页 | 主集前 10 组的完整 `compact` 与两项消融。 |
| 第 71–80 页 | 同样前 10 组的完整 `compact` 与 fast99/95/90。 |

图册每页标出场景和种子，可以直接在逐局表中筛选，再由 `trace` 定位原始证据。
图册显示全部运行、失败清除和未清源，不按成功率筛图；额外比较页重复展示完整
基准以方便观察，230 次唯一运行均已覆盖。

## 当前证据与新输出

`results/` 的 manifest、runs、summary 和完整压缩日志来自本次采纳的 230 次全量重跑，`data/` 是对应第一例的可读摘录；独立审计记录为 `audit.json`。正文图表全部读取当前批次，`--figures` 还可生成完整轨迹图册。`adoption.json` 和 `package_validation.json` 记录采纳来源及核验范围。

当前批次中，两个严格版本共 120 次均全清且连续认证，65173 条动作账本与全部统计通过独立重放。复现入口核验交付文件和本批实验的源码哈希，`--audit-only` 精确重建保存统计，`--full` 在新目录运行相同矩阵。跨平台运算可能影响启发式分支，因此应逐组比较新输出，不能将不同批次的数值混合。旧 Windows 批次不再用于当前论文。
