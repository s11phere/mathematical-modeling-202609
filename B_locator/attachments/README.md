# B题论文评审附件

本附件按问题一至问题四分别组织。四个问题均采用 `code/`、`data/`、`results/`、`figures/` 四个主目录；问题三、四的完整动作日志另集中于 `results/traces/`。必要程序集中一层，无须进入研究归档目录。共享中文制图字体只保留一份，位于 `fonts/`。

## 建议评审顺序

1. 阅读各题 `DATA_SOURCES.md`，根据其中的图表索引核对论文数据、输入和计算方法。
2. 查看 `figures/` 中的正文图和 `supplement.pdf` 中的完整补充图。
3. 运行 `--audit-only` 核验保存结果；需要了解算法运行时先运行 `--smoke`，完整实验使用 `--full`。

| 问题 | 输入与实验规模 | 图件 | 来源及运行说明 |
| --- | --- | --- | --- |
| 问题一 | 五组几何算例、四组固定种子几何扫描 | 三幅正文图、4页补充图册 | [数据来源](Q1/DATA_SOURCES.md)、[复现说明](Q1/README.md) |
| 问题二 | 36,960个理论网格点、11,168个数值网格点 | 三幅正文图、4页补充图册 | [数据来源](Q2/DATA_SOURCES.md)、[复现说明](Q2/README.md) |
| 问题三 | 120组场景的五策略比较及20组四项消融，共680次运行 | 五幅正文图、140页补充轨迹图册 | [数据来源](Q3/DATA_SOURCES.md)、[复现说明](Q3/README.md) |
| 问题四 | 60组场景的三策略比较及10组两项消融、三项快速策略，共230次运行 | 五幅正文图、80页补充轨迹图册 | [数据来源](Q4/DATA_SOURCES.md)、[复现说明](Q4/README.md) |

## 环境与统一入口

建议 Python 3.12 或更新版本。实际交付验证使用 Python 3.13.15、NumPy 2.5.3、Matplotlib 3.11.1。进入本附件根目录后安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

每题入口均支持以下四种模式，将 `Q1` 改为 `Q2`、`Q3` 或 `Q4` 即可。输出目录建议放在附件外，以保留原始证据：

```bash
python3 -B Q1/reproduce.py --audit-only
python3 -B Q1/reproduce.py --smoke --out ../reproduction-q1-smoke
python3 -B Q1/reproduce.py --figures --out ../reproduction-q1-figures
python3 -B Q1/reproduce.py --full --out ../reproduction-q1-full
```

计算、审计与制图均可离线进行，不需要原研究工程或在线模拟器。问题二同时提供原 Mathematica 理论程序；默认复现入口包含相同中点求积公式的 Python 实现，不要求安装 Mathematica。每题的具体输出、参数及已完成验证见对应 README。

## 数据与文件完整性

题设常数、构造示例、解析求积和固定种子离线仿真在各题 `DATA_SOURCES.md` 中分别说明，不将离线结果作为正式在线测试记录。失败与漏清实验均保留；问题三、四日志中的真实源位仅用于退出后的审计及作图。

每题 `SOURCE_MANIFEST.json` 记录交付文件的 SHA256、来源和路径适配；根目录 `SHA256SUMS.txt` 对整个交付包提供逐文件校验值。论文冻结数值保留，新增复现结果写至另一个目录。完整实验的计算量明显大于试运行，审计与试运行不能替代完整重跑。

历史探索脚本、重复源码快照、缓存与构建中间文件未收入本包；原工程中的研究记录保留。补充图册覆盖本次交付的全部几何算例和策略运行，便于按场景集中审阅，无须逐个打开动作日志。
