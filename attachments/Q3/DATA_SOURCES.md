# 问题三数据来源与论文证据

本文件集中声明本题输入、实验生成规则、原始动作、统计结果和论文图表的来源。
目录名 `Q3` 仅是问题三附件的文件标识。

## 来源与可追溯链

本文件所列策略比较与消融数字来自本地离线模拟实验，并非正式在线评测数据或实测场景。
正文另列的三次正式测试结果及对应原始日志见 [正式测试说明](../formal-tests/README.md)
和 [结果汇总](../formal-tests/results.csv)，不计入下述 680 次离线运行。模拟器按题设的
靶区、误差界、接收半径、频道、移动速度及动作费用构造；源位与误差场由下述公开
种子生成。冻结实验 ID 为 `544eee966fe270395af7`，历史定义指纹为
`0ada3086f2e8384f6cfb7a8cfc1b14c907f232f67e9c874b8e10c7b4e867b70e`。

`data/` 输入和 `code/` 算法 → 种子生成场景 → `results/traces/` 原始动作及退出后真值
→ `paired_results.json/.csv` 逐局结果 → `summary.json` 汇总 → `figures/`、正文表格和摘要。

`SOURCE_MANIFEST.json` 为每个文件记录原工程来源、当前 SHA256 及改动说明。
原工程路径仅用于追溯，运行无需访问。14 个必要算法与场景依赖文件逐字节匹配历史
`results/manifest.json` 对应哈希；全部 11 个期望场输入文件同样匹配。
历史 `manifest.json` 还列有当时目录内未被本实验使用的诊断脚本，本附件没有复制
这些脚本；新复现使用仅含必要依赖的定义指纹，不能用整个历史目录的指纹替代其
运行标识。该差异仅是文件清单和路径变化，算法、场景、参数及统计函数未改动。

## 实际输入文件与字段

| 文件 | 生成方式、参数与用途 |
| --- | --- |
| `data/p2_grid_map_thi*.csv`，共 9 张 | `p3_expect_field.py::BaseMapFamily.build` 调用 `p2_grid_expectation.py` 的确定性积分。测站为原点、首次测向为 0°，源距先验 `[5,t_hi]`；`t_hi` 依次为 150、250、350、450、600、800、1000、1250、1500 m。网格步长 40 m、径向积分样本 200，靶区半径 1800 m。不是随机抽样数据。 |
| `data/p2_grid_family.json` | 上述图族的文件名、外径列表、网格步长和积分数。策略根据当前位置和方位变换这些基准场。 |
| `data/p2_grid_map.csv` | 回退基准场，来自问题二网格期望计算。首次测向 0°，测向误差界 1°，面积均匀先验，步长 20 m、径向样本 500，源距 `[5,1500]` m。图族完整时优先载入图族，不触发回退。 |
| `data/p2_grid_report.json` | 回退基准场的完整生成参数、可检测门控、输入域、检查结果及汇总。 |

九张图族 CSV 的字段为 `x_m`、`y_m`、`E_diam_given_detectable_m`，分别为检测候选点
坐标和可检测条件下的交会区域期望直径，单位均为米；空白值表示该格点没有有限的
条件期望。回退 CSV 另含距离、方位、可检测概率、权重和可用性等诊断列。
历史列名 `E_diam_mixed_mm` 的末尾 `mm` 是旧命名，代码计算量仍为米；本题载入
明确使用 `E_diam_given_detectable_m`，不读取该列作为策略目标。

需要独立重建图族时，在本题目录运行以下命令，另写输出以保护原始输入：

```bash
python3 -B code/p3_expect_field.py --build-family --family-step 40 --family-nt 200 --family-dir ../reproduction-q3-fields
```

原项目中的 `p3_scan01/02/03` 为独立接口演示数据，不是论文 680 次实验的输入，因此
本包不混入这些文件；主实验也没有使用代码中保留的 `LIVE1/LIVE2` 历史示例布局。

## 场景生成与固定参数

`code/run_p3_paper.py` 定义场景顺序；`p3_adaptive_bench.py::make_scene` 创建场景。
每类内部从 `i=0` 编号，种子为
`2026091200 + 100000 × 场景序号 + 97 × i`。

| 场景序号 | 标签 | 场景数 | 生成规则 |
| --- | --- | ---: | --- |
| 0 | `random` | 50 | `MockArena`；10–16 个源，频道从 1–20 不放回抽取，源位按半径 1800 m 圆域内面积均匀生成，接收半径均匀取 `[1000,1500]` m。 |
| 1 | `annulus` | 20 | `outer_annulus`；12 个源，源位按半径 1300–1800 m 环带内面积均匀生成；频道不重复，接收半径仍均匀生成。 |
| 2 | `center` | 10 | `center_cluster`；12 个源，频道 1–12，半径均匀取 `[0,260]` m、方位均匀取 `[0,2π)`，接收半径仍均匀生成。这里的径向均匀不等同于面积均匀。 |
| 3 | `hash` | 20 | 源位同随机场景；以位置和局部种子做 SHA256 映射产生固定、非平滑误差，幅值不超过 0.995°。 |
| 4 | `worstrecv` | 20 | 源位同随机场景，但将每个源的接收半径固定为 1000 m。 |

一般误差场由 12 项平滑正弦波与 25 m 位置量化项组合；250 m 相关尺度、0.25 局部
权重，归一化并截断在 ±1° 内。同一位置的误差固定。详细参数、场景类、源位、半径、
场系数、局部种子及两个指纹保存在各日志 `scene_manifest`。五策略每次都重建相同
种子的全新场景，使用源位指纹和误差场指纹核对配对关系。

五种策略为 `field`、`sweep`、`tour`、`adaptive`、`joint`，直接使用相应配置类的默认值。
随机集前 20 组另作四项单因素消融：清后扫描关闭、单方案规划、取消覆盖测站精修、
取消概率门槛。仅更改 `ABLATIONS` 中声明的一项参数。每次运行的 `requested_config`
和 `effective_config` 均保留；连续单元判据使用有效半径
`1000 - 50/sqrt(2) - 1e-6` m 及零额外覆盖松弛，亦由审计核对。

## 原始证据字段与统计口径

`paired_results.json` 是权威逐局表，`.csv` 提供相同记录的便于筛选形式。每行的
`split`、`scenario`、`index`、`seed`、`policy` 构成身份，`trace_file` 指向同目录下的
`traces/*.json`。完整数据为 600 次主实验加 80 次消融，不筛去未全清或失败局。

每份 trace 含 `actions`（按时间排序的进入、检测、清除、退出动作）、
`scene_manifest`、`requested_config`、`effective_config`、`report`、`guard`、
`post_exit_truth`、`metrics`、`action_audit`。其中源真值只在退出后用于核验和画图，
策略决策不能读取。`actions` 中的 `x/y`、`channel`、结果类型和相邻位置用于独立
重算移动、切频、检测、清除及累计时间；不使用报告时间作为下一步累计基数。

完整退出时间的独立计费公式为
`T = travel_m/5 + 5*N_measure + N_switch + 5*N_clear_success + 3*N_clear_failure`。
初始位置 `(0,0)`，检测频道为 1；清除动作不改变检测频道。`exit_s` 为完整退出时间，
`travel_m` 为总路程，`n_measure` 为检测次数；单源时间为每局
`exit_s/cleared` 后再跨局取均值，不是总体耗时除以总源数。零清除时该比值为 null，
有效样本数另列。源加权清除比例为清除总数除以源总数，全清局数按逐局判断。

主表报告均值和 P90。配对耗时节省为 `1 - mean(candidate)/mean(reference)`；
置信区间采用 4000 次场景配对自助重采样，固定种子 20260912，每次比较重新初始化。
消融耗时增长率取相反数。最后一次清除时间和退出尾程是解释性诊断，不替代完整 T。

所有模拟的虚拟上限为 360000 s。历史运行记录了本地策略构造与执行墙钟时间，但
没有强制 1200 s 看门狗；当前复现入口对新运行设置 1200 s 现实计时器，超时保留为
失败局。墙钟时间依赖设备和负载，不能据此声称正式在线评测通过。

## 论文数字、图表和程序对应

使用稳定的图表标签和文件名索引，避免正文重新排版后页码或编号变化造成歧义。

| 论文内容 | 权威结果或原始证据 | 实现与生成方法 |
| --- | --- | --- |
| 随机 50 组核心比较表、摘要中 42.6% 降幅 | `summary.json#/scenarios/random`；其中 `paired_vs_field/joint` 的节省与区间；`table_provenance.json#/generated` | `make_paper_tables.py` 从冻结汇总生成 `q3-core-rows.tex`、`q3-numbers.tex`、摘要片段。 |
| 五代策略全清率、完整退出时间及单源时间 | `paired_results.json` 主实验行与 `summary.json#/scenarios`、`#/overall` | `run_p3_paper.py::aggregate/summarize`；所有场景均保留。 |
| 连续覆盖几何与测站滑移，`q3-geometry-certificate` | 确定性示意图；不是实验统计 | `make_paper_figures.py::fig1_geometry`；对应 `p3_coverage.py` 连续单元判据及 `p3_joint.py` 测站精修。 |
| `q3-route-field-sweep-tour`、`q3-route-tour-adaptive-joint` | `random/index=0/seed=2026091200` 的五份 `main_random_000_2026091200_<policy>.json` | `route_comparison`，由日志绘制位置、测点、清除事件、完整 T 和行程 L。首局事先固定，不按表现挑图。 |
| `q3-time-cost-clearance` | `random` 50 组的各成本分项及固定首局清除事件 | `fig4_cost_and_clear`；时间分解来自同一逐局记录，清除曲线来自原始动作。 |
| `q3-scenarios-ablation` | `summary.json#/scenarios` 与 `#/ablations/random` | `fig5_scenarios_ablation`；单因素消融与随机前 20 组完整 `joint` 配对。 |
| 四项消融表与补充统计 | `summary.json#/ablations/random`、`table_provenance.json` | `make_paper_tables.py` 生成完整消融、耗时消融和场景补充表。 |
| 680 次独立动作与真值隔离审计 | `audit_report.json`、全部 trace 的 `actions`、`guard`、`action_audit` | `run_p3_paper.py::action_audit/static_policy_audit/audit_all`。 |
| 320 个连续覆盖声明 | `coverage_audit.json#/audits` 和 `#/counts` | 独立重建 5 m 数值网格及 50 m 闭单元证书。细网格通过本身不是连续证明。 |
| `supplement.pdf` 第 1–120 页 | 主实验全部 120 组 × 5 策略 | 依次为随机 50、外圈 20、中心 10、非平滑误差 20、最小接收半径 20；每页标注种子。 |
| `supplement.pdf` 第 121–140 页 | 四项消融全部 80 次，加对应的 20 次完整 `joint` | 同页共用种子与场景；完整基准轨迹重复展示便于直接比较。 |

## 冻结结果与新复现结果的区别

`results/`、`data/` 和五幅 `figures/` 是复制的冻结证据；SHA256 可核对原始来源。
`supplement.pdf` 是此次用这些冻结日志重新生成的完整图册，增加了原图册没有逐局
展示的 80 次消融，图册不产生或更改任何实验数据。

所有 `reproduce.py` 模式先核验哈希，随后只写指定的新目录。审计先复制原始日志再
重算，原始动作载荷不变；新审计元数据可以变化。`--smoke` 和 `--full` 才新运行策略；
比较新旧结果时按场景、种子和策略配对，算法动作、源位、配置应一致，墙钟耗时允许
变化。新输出中 `source_snapshot/` 是实际运行依赖的快照，不需要旧研究目录。

独立复核只支持论文定义的静止全向源和明确接收下界；本地合成误差与有限样本不能
覆盖所有物理环境，也不能证明策略对每个合法场景都能迅速完成。
