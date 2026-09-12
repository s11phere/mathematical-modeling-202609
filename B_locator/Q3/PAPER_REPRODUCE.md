# Q3 论文与冻结实验复现

本轮在 `codex/b-locator-q3` 完成问题三写作，算法及默认配置保持原样。正文为 6 页（第 15–20 页），摘要仅回填 Q3，正式测试三行待补；Q4、摘要总述和全篇总评仍为占位。按后续格式要求，各级中文标题统一采用摘要的黑体字重，Q3 小标题改为 `(a)`、`(b)` 等独占一行；全局页边距、字号和间距参数保持原样。Q1、Q2 的内容保护及本次格式检查见 `out/paper_q3/preservation_check.json`、`formatting_check.json`。

## 交付索引

以下路径以仓库根目录为起点。

| 内容 | 路径 |
|---|---|
| 整篇论文 PDF | `B_locator/paper/main.pdf` |
| Q3 正文、概率及参数附录 | `B_locator/paper/sections/q3-model.tex`、`q3-appendix.tex` |
| 五幅主图，矢量 PDF 与 330 dpi PNG | `B_locator/paper/figures/q3-*` |
| 全部 120 场景、五策略补充轨迹图册 | `B_locator/Q3/out/paper_q3/supplementary_trajectories.pdf` |
| 冻结逐局数据及汇总 | `B_locator/Q3/out/paper_q3/paired_results.json`、`.csv`、`summary.json` |
| 680 份动作与退出后真值记录 | `B_locator/Q3/out/paper_q3/traces/` |
| 配置、源位、误差场、代码及期望场哈希 | `manifest.json`、各局 `scene_manifest`、`source_snapshot/SHA256.json` |
| 动作审计、真值访问与连续覆盖复核 | `audit_report.json`、`coverage_audit.json` |
| 结论与证据对应 | `evidence_map.json`、本文件下表、`table_provenance.json` |

后三行的文件均位于 `B_locator/Q3/out/paper_q3/`。完整算法源码在 `Q3/src/` 及输出目录中的 `source_snapshot/`；论文附录为可读展示副本，少量 Unicode 数学符号只作排版转义，执行源文件未改。

## 固定实验定义

实验 ID：`544eee966fe270395af7`。定义指纹：`0ada3086f2e8384f6cfb7a8cfc1b14c907f232f67e9c874b8e10c7b4e867b70e`。

| 场景序号 s | 场景 | 局数 |
|---|---|---:|
| 0 | 随机分布 random | 50 |
| 1 | 外圈分布 annulus | 20 |
| 2 | 中心聚集 center | 10 |
| 3 | 非平滑固定位置误差 hash | 20 |
| 4 | 全部接收半径 1000 m，worstrecv | 20 |

每组从 i=0 编号，种子为 `2026091200 + 100000*s + 97*i`。每个场景分别初始化五种策略，直接使用 `P3Config`、`SweepConfig`、`TourConfig`、`AdaptiveConfig`、`JointConfig` 的默认值，不经过会覆盖子类参数的通用命令入口。随机集前 20 局额外运行四项单因素消融，总计 680 次。

主指标是完整退出时间 T，保留均值和 P90；另报告清除比例、全清局数以及逐局 T/成功清除数的均值。零清除时每源比值记为 null 并公开有效样本数，失败或漏清局保留。bootstrap 为 4000 次配对重采样，每次比较使用独立初始化的种子 20260912；降幅为 `1 - mean(candidate)/mean(reference)`。四项消融的增长率取其相反数，未做多重比较校正。

## 复现命令

从仓库根目录执行。运行记录为 Python 3.12.14、NumPy 2.3.5；绘图另需 Matplotlib，PDF 检查需 pypdf 和 Poppler。字体使用论文已有宋体，排版使用现有 `build.sh` 与 XeLaTeX/Tectonic。

```sh
# 只重放冻结动作并审计，不构造或运行策略。
python3 -B B_locator/Q3/scripts/run_p3_paper.py --audit-only

# 只读冻结数据，重新生成数字、正文图及全部补充轨迹。
python3 -B B_locator/Q3/scripts/make_paper_tables.py
MPLCONFIGDIR=/tmp/q3-paper-mpl python3 -B B_locator/Q3/scripts/make_paper_figures.py
MPLCONFIGDIR=/tmp/q3-paper-mpl python3 -B B_locator/Q3/scripts/make_paper_trajectory_atlas.py
python3 -B B_locator/Q3/scripts/make_paper_source.py
bash B_locator/paper/build.sh build

# 在新目录完整重跑 680 次，避免混入论文冻结数据。
python3 -B B_locator/Q3/scripts/run_p3_paper.py --out B_locator/Q3/out/paper_q3_reproduction
```

默认入口会核对已有记录并仅补跑缺失局；算法、期望场或配置不匹配时停止。`--smoke` 使用独立子目录，`--max-new-runs N` 可限制一次新增运行数。绘图和表格默认读取论文冻结目录，重新跑出的原始结果可先与其按场景、种子、策略配对核对。动作应可复现，机器墙钟时间允许变化。

```sh
python3 -B B_locator/Q3/src/p3_selftest.py --out /tmp/q3-selftest.txt
python3 -B B_locator/Q3/src/p3_adaptive_checks.py
python3 -B B_locator/Q3/src/p3_joint_checks.py
```

本轮已有检查结果分别为 40/40、7/7、12/12，日志保存为 `selftest.txt`、`adaptive_checks.txt`、`joint_checks.txt`。覆盖近场、圆域边界空洞、极端及舍入测向误差、试探失败后补测，以及强制目标不被可选补测概率门槛丢弃。

## 论文结论、公式、代码与数据

TeX 标签稳定；公式编号以最终 PDF 为准。代码文件路径相对 `B_locator/Q3/`。

| 论文内容 | 公式标签或图表 | 实现与证据 |
|---|---|---|
| 完整成本与退出时间 | `eq:q3-cost`、`fig:q3-time` | `src/p3_arena.py` 接口；`scripts/run_p3_paper.py::action_audit` 独立重算；每局 `actions`、`action_audit` |
| 保守角楔及清除半径 | `eq:q3-wedge`、`eq:q3-region` | `src/p3_homing.py`、`src/p3_coverage.py`、`src/p3_robot.py`；专项检查 |
| 五代策略的递进与逐局例外 | `tab:q3-generations`、`fig:q3-fst`、`fig:q3-taj` | `src/p3_robot.py`、`p3_sweep.py`、`p3_tour.py`、`p3_adaptive.py`、`p3_joint.py`；固定 random/index=0/seed=2026091200 的五份 trace |
| 共用基线、逼近与侧移 | `eq:q3-baseline`、`eq:q3-home` | `src/p3_homing.py`、`src/p3_adaptive.py` |
| 联合覆盖及逐频道扫描代理 | `eq:q3-gain`、`eq:q3-greedy`、`eq:q3-plan` | `src/p3_frontier.py`、`src/p3_joint.py`；完整成本仍以动作审计为准 |
| 保留独占覆盖职责的测站移动 | `eq:q3-move-constraint`、`eq:q3-move` | `src/p3_joint.py`；`joint_no_cover_polish` 消融 |
| 连续覆盖与停机 | `eq:q3-cert-radius`、`eq:q3-cert-proof`、`eq:q3-stop` | `src/p3_coverage.py`；独立 `CoverageAuditor`、`coverage_audit.json` |
| 可选补测中心射线近似 | `eq:q3-prob` | `src/p3_joint.py`；`joint_no_probability_gate` 消融与强制目标专项检查 |
| 随机集 42.6% 降幅及区间 | `tab:q3-core`、`fig:q3-time` | `summary.json#/scenarios/random/paired_vs_field/joint`，由 `make_paper_tables.py` 生成摘要和正文数字 |
| 场景表现、退步及不显著的消融 | `fig:q3-cross`、附录统计 | `summary.json#/scenarios`、`#/ablations/random`；图表保留所有样本 |

## 审计结果与适用边界

680 局共 116071 个接受动作通过独立逐步成本审计，分项总和最大浮点差为 7.28e-12 s。680 局退出前真值守卫通过；8 个决策类的 147 个非报告方法未发现敏感真值读取。它是可检查的运行守卫与静态审计，不是进程级安全隔离。

全部 320 个连续覆盖声明通过 5 m 细网格复核，并分别重建 50 m 闭单元证书。细网格只是数值检查，连续结论依赖正文三角不等式及静止全向源、接收下界和无漏报前提。证书成立意味着无残留，不意味着算法在任意场景都能迅速取得证书。

本轮只做离线实验。历史运行已记录本地墙钟耗时，但未设置现实 1200 s 看门狗；虚拟上限为 360000 s。当前复现入口对新运行设置 1200 s 现实计时器，超时仍保留为失败局。本地计算时间不能替代正式在线程序运行时间。

冻结算法和期望场的哈希均已核验。早期报告编辑曾刷新运行入口哈希，因此不声称保留了历史运行入口的逐字节版本；`source_snapshot/` 保存当前审计入口，算法与场景定义可核对。缺少原始数据的历史性能数字和错误 1200 s 虚拟预算结果均未用于本论文比较。
