# B 题问题三附件：多源定位与清除

本目录是论文提交和评审时使用的精简附件。评审只需查看顶层的四个目录和
`reproduce.py`；开发阶段的调试脚本、完整动作日志及历史研究记录统一保存在
`research_archive/`，不参与附件阅读。

## 附件结构

| 路径 | 内容 |
| --- | --- |
| `code/` | `field`、`sweep`、`tour`、`adaptive`、`joint` 五代策略及其公共模拟器副本；`p3_joint.py` 是论文采用的最终策略。 |
| `data/` | 论文实验所用期望场及先验场数据。 |
| `results/` | 600 局五策略配对实验与 80 局消融的汇总、审计报告、覆盖复核和论文证据映射；正文表格和图中的数字均由此目录生成。 |
| `figures/` | 五幅正文图及补充轨迹图册；PDF 与高清 PNG 同时提供。 |
| `reproduce.py` | 稳定的复现入口，转调用冻结实验驱动程序。 |
| `research_archive/` | 完整历史源码、脚本、逐动作日志、研究记录和原始输出，仅用于追溯。 |

论文源码和 PDF 位于 `../paper/`。附录 A 说明了附件结构、实验定义及结论与
代码、数据的对应关系。

## 复现

从仓库根目录执行：

```bash
# 重放已保存动作，并独立重算移动、切频、检测和清除成本
python3 -B B_locator/Q3/reproduce.py --audit-only

# 运行一局离线演练（结果写入 research_archive/out/paper_q3/smoke）
python3 -B B_locator/Q3/reproduce.py --smoke

# 完整重跑请使用新的输出目录，不覆盖论文冻结结果
python3 -B B_locator/Q3/reproduce.py --out /tmp/q3-reproduction
```

复现程序固定五种策略、场景种子和默认参数，并在运行前校验源码与期望场哈希。
`--audit-only` 不会构造策略；正式重跑保留失败和漏清局，不按结果筛选样本。
运行需要 Python 3.12、NumPy 2.3；生成图表时另需 Matplotlib。

## 结果索引

- `results/paired_results.csv`：每个场景、策略和消融的一行记录。
- `results/summary.json`：论文核心结果表和图中数值的唯一汇总来源。
- `results/evidence_map.json`：正文结论与公式、源码、数据和图表的对应关系。
- `results/audit_report.json`、`coverage_audit.json`：独立成本审计、真值访问守卫和覆盖复核。

逐动作原始记录、完整源文件哈希和历史调试输出均在
`research_archive/out/paper_q3/`，不重复放入提交附件，以控制附件体积。
