# 问题一：示向度交会定位与直径圆覆盖

本附件包含全部必要输入、算法、结果与图片。建议先看 `DATA_SOURCES.md`，再看正文图与
`supplement.pdf`，最后按下列命令核验。计算不依赖原项目或网络服务。

| 路径 | 内容与评审用途 |
| --- | --- |
| `code/` | 4 个脚本，集中一层：几何求解、算例与扫描、正文绘图、补充图册。 |
| `data/` | 五组检测点 CSV 与对应真值 JSON，共 10 个输入文件。 |
| `results/` | 五组逐例结果与完整扫描汇总，供核对论文数值。 |
| `figures/` | 论文采用的三幅正文图，保持论文原图。 |
| `supplement.pdf` | 4 页：全部五组定位区域、统一判定表及四组几何扫描统计。 |
| `DATA_SOURCES.md` | 输入来源、字段、随机种子及论文数值的具体出处。 |
| `SOURCE_MANIFEST.json` | 交付文件与原始文件的 SHA256、生成关系。 |
| `reproduce.py` | 统一复现入口，新结果写到本题目录之外。 |

## 复现命令

使用 Python 3.12 及以上、NumPy 与 Matplotlib。本次实际验证为 Python 3.13.15、
NumPy 2.5.3、Matplotlib 3.11.1。首次准备环境可执行：

```bash
python3 -m pip install 'numpy>=2.3,<3' 'matplotlib>=3.10,<4'
```

在本题目录执行，输出路径可改为其他新的相对路径或绝对路径：

```bash
# 核验附件 SHA256；重新求解五组保存输入，核对直径、覆盖及真值包含性。
python3 -B reproduce.py --audit-only

# 从固定种子重新生成并求解五组算例，不做大批量扫描。
python3 -B reproduce.py --smoke --out ../reproduction-q1-smoke

# 从保存输入和结果重绘正文图与 4 页补充图册。
python3 -B reproduce.py --figures --out ../reproduction-q1-figures

# 五组算例与四组几何扫描，共 48000 个扫描构型。
python3 -B reproduce.py --full --out ../reproduction-q1-full
```

`--smoke` 输出 `cases/`、`results/p1_results.jsonl` 和 `results/p1_cases_only.json`；
`--full` 的完整汇总为 `results/p1_summary.json`；`--figures` 输出 `figures/` 和
`supplement.pdf`。小规模试运行不替代完整扫描结论。

共享中文字体不随包提交以控制支撑材料体积。计算、审计与完整重跑都不需要字体，
仅制图需显式指定中文字体：

```bash
python3 -B reproduce.py --figures --font /path/to/chinese-font.ttf --out ../reproduction-q1-figures
```

原始脚本保留其历史默认目录，统一通过 `reproduce.py` 调用即可使用附件内的便携路径。
重绘会受字体与绘图库版本影响，数据、几何构造与判定不变；`figures/` 保留论文实际采用的原图。

## 代码阅读与核验范围

先读 `p1_intersection.py` 的角楔交集、直径和覆盖判定，再读 `p1_experiments.py` 的
固定种子生成与独立交叉核验，最后读两个绘图脚本。

本次实际执行了审计、试运行、制图及完整实验，并将本题独立复制到原项目之外重新运行
审计、试运行及指定字体制图。完整重跑的 `cases_summary`、全部 `per_case` 和四组 `sweeps`
与冻结汇总逐项相等；五组算例输入一致，4 页图册逐页检查通过。原算法与保存数据未改动。
验证记录见 `results/package_validation.json`。

## 继续修改代码

现有 `code/*.py` 和 `reproduce.py` 可以继续修改。试验新代码时使用
`--dev --smoke --out DIR`，完整开发实验使用 `--dev --full --out DIR`。
入口会列出源码变化，并标明开发结果不代表论文原实验；数据、结果和其他已登记文件
仍须通过校验。新增文件或修改说明后，在完整仓库运行 `python3 paper/maintain.py refresh`
更新交付清单；这不会更改历史实验来源。新输出必须位于本题目录之外。

开发模式不能与 `--audit-only` 或 `--figures` 混用。采用新实验数据后，需要同步更新
结果来源、论文统计与图件，不能只刷新文件哈希就宣称复现了原论文。
