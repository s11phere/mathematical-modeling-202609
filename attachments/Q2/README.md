# 问题二：第二检测点选择与期望直径

本附件包含理论网格、数值网格、全部必要程序及论文图片。建议先查 `DATA_SOURCES.md`
定位论文数字，再审阅正文图与 `supplement.pdf`，最后运行核验；无需原项目或在线服务。

| 路径 | 内容与评审用途 |
| --- | --- |
| `code/` | 7 个源程序集中一层：理论 Wolfram 程序、数值积分、公共几何、四个绘图脚本。 |
| `data/` | 理论与数值两张完整 CSV 网格。 |
| `results/` | 数值网格报告与独立几何自检结果。 |
| `figures/` | 论文三幅正文图：双角楔几何、两方法对照、60 m 待选区域。 |
| `supplement.pdf` | 4 页：独立理论场、数值场、可检测比例、误差平均后的条件期望。 |
| `DATA_SOURCES.md` | 数据来源、计算参数、字段说明及论文数值索引。 |
| `SOURCE_MANIFEST.json` | 各交付文件与原始来源的 SHA256、生成关系。 |
| `reproduce.py` | 审计、试运行、完整重算、制图的统一入口。 |

## 复现命令

使用 Python 3.12 及以上、NumPy 与 Matplotlib。本次实际验证为 Python 3.13.15、
NumPy 2.5.3、Matplotlib 3.11.1。首次准备环境可执行：

```bash
python3 -m pip install 'numpy>=2.3,<3' 'matplotlib>=3.10,<4'
```

在本题目录执行；所有新输出必须在本题附件之外：

```bash
# 分别选取理论和数值网格的 41 点，独立重算并核对保存值。
python3 -B reproduce.py --audit-only

# 300 m 网格、30 个源位、10 组误差抽样及 11 项几何自检。
python3 -B reproduce.py --smoke --out ../reproduction-q2-smoke

# 从保存的完整网格重绘正文图与 4 页补充图册。
python3 -B reproduce.py --figures --out ../reproduction-q2-figures

# 重建论文采用的 30 m 数值网格（理论网格由 code/Q2_theory_corrected.wl 在 Mathematica 中导出）。
python3 -B reproduce.py --full --out ../reproduction-q2-full
```

`--full` 以原始数值算法使用 300 个源位、200 组测向误差重建 30 m 数值网格；理论网格由
`code/Q2_theory_corrected.wl` 在 Mathematica 中导出，本附件不再用 Python 复算理论网格
（`--audit-only` 仍以同一解析式抽 41 点核对保存值）。完整数值输出含 CSV、参数报告与
自检结果；`--smoke` 为流程检查，其粗网格最小值不能代替论文数值。

制图输出为 `figures/` 和 `supplement.pdf`。除三幅正文图外，还输出两幅单独的热力图，
补充 PDF 已集中展示这些结果及另外两个诊断场。附件 `figures/` 只保留论文原图，避免重复。

本题目录可与同级 `fonts/` 一起移动。单独复制本题时计算仍可运行；制图可显式指定中文字体：

```bash
python3 -B reproduce.py --figures --font /path/to/chinese-font.ttf --out ../reproduction-q2-figures
```

计算公式保留；数值程序已改用同目录几何依赖，绘图脚本的历史默认路径由入口适配。请通过 `reproduce.py` 调用便携输入、输出路径。
`code/p1_intersection.py` 是本题所需的独立几何校验依赖，已一并提供。

## 代码阅读与核验范围

先读 `Q2_theory_corrected.wl` 的直径式与源位积分，再读 `p2_grid_expectation.py` 的
交会区域、接收条件与加权平均；后者调用本目录的 `p1_intersection.py` 交叉校验。
其余脚本负责正文图、几何示意和补充图册。

本次实际执行了审计、试运行及制图，并独立复制到原项目之外重验这三项。82 个固定点
重算一致，11 项几何自检通过，4 页补充 PDF 逐页检查通过。另完整重算两套网格：36,960 个理论值的最大绝对差为 1.82e-12 m，11,168 行数值网格的所有字段与保存数据逐值完全一致；核验记录见 `results/package_validation.json`。
保存数据与算法公式未改动，字体或绘图库版本可造成重绘图片的像素差异。

## 继续修改代码

现有 `code/*.py` 和 `reproduce.py` 可以继续修改。试验新代码时使用
`--dev --smoke --out DIR`，完整开发实验使用 `--dev --full --out DIR`。
入口会列出源码变化，并标明开发结果不代表论文原实验；数据、结果和其他已登记文件
仍须通过校验。新增文件或修改说明后，在完整仓库运行 `python3 paper/maintain.py refresh`
更新交付清单；这不会更改历史实验来源。新输出必须位于本题目录之外。

开发模式不能与 `--audit-only` 或 `--figures` 混用。采用新实验数据后，需要同步更新
结果来源、论文统计与图件，不能只刷新文件哈希就宣称复现了原论文。
