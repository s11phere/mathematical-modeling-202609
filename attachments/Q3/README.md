# 问题三：多源定位、清除与覆盖判定

本附件可独立审阅、运行和制图，不依赖原项目、历史研究目录或网络服务。建议先看
`DATA_SOURCES.md` 的论文证据索引，再看 `figures/` 和 `supplement.pdf`，最后按需要
阅读 `code/`。最终策略为 `joint`；其余四代策略与四项单因素消融均保留。

## 文件结构

| 路径 | 评审用途 |
| --- | --- |
| `code/` | 全部必要算法、公共几何、模拟器、场景生成、实验、独立审计、制表、绘图和已有专项检查；所有脚本集中一层。 |
| `data/` | 实际载入的九张期望场、图族参数，以及回退基准场和其生成参数。 |
| `results/` | 论文冻结的 680 行逐局结果、汇总、实验参数、独立审计、表格数字来源及历史专项检查日志。 |
| `results/traces/` | 680 份原始逐动作证据。由逐局表中的 `trace_file` 直接定位，无需逐个寻找文件。 |
| `figures/` | 论文五幅正文图，每幅提供矢量 PDF 和高清 PNG。 |
| `supplement.pdf` | 140 页完整轨迹图册：前 120 页为五策略配对；后 20 页为完整策略与四项单因素消融配对。覆盖所有 680 次运行，基准策略的前 20 次在消融页重复展示便于比较。 |
| `DATA_SOURCES.md` | 输入来源、字段、场景种子、统计口径及论文图表与证据文件的对应。 |
| `SOURCE_MANIFEST.json` | 全部交付文件的来源和 SHA256；记录路径适配和冻结算法对应关系。 |
| `reproduce.py` | 统一复现入口。所有新结果写到附件之外，论文冻结结果始终只读。 |

本题目录与其同级 `fonts/` 一起移动即可制图。只移动本题目录时，实验与审计仍可运行；
制图增加 `--font /path/to/中文字体.ttf` 即可。所有数据均包含在本附件内。

## 复现步骤

历史冻结环境为 Python 3.12、NumPy 2.3.5；本次实际验证环境为 Python 3.13.15、
NumPy 2.5.3、Matplotlib 3.11.1，九次试运行与历史动作逐项一致。无 SciPy、网络、
在线接口或 LaTeX 编译依赖。Python 3.12 及以上环境可先安装：

```bash
python3 -m pip install 'numpy>=2.3,<3' 'matplotlib>=3.10,<4'
```

在本题目录执行以下任一命令。`--out` 可使用任意新的绝对路径或相对路径，但必须在
本题附件目录之外。以下以相邻目录为例：

```bash
# 第一步：重放 680 份动作，重算成本与覆盖证书，不运行策略。
python3 -B reproduce.py --audit-only

# 第二步：同一固定场景运行五代策略及四项消融，共 9 次。
python3 -B reproduce.py --smoke --out ../reproduction-q3-smoke

# 按论文冻结数据重绘五幅正文图、140 页补充图册和表格。
python3 -B reproduce.py --figures --out ../reproduction-q3-figures

# 完整矩阵：120 组 × 5 策略 + 20 组 × 4 消融 = 680 次。
python3 -B reproduce.py --full --out ../reproduction-q3-full
```

未指定输出目录的审计自动使用系统临时目录，并在结束时打印位置。试运行结果位于
所给目录的 `smoke/`；完整实验直接写入所给目录。完整实验支持中断续跑；相同命令
会核验参数和源码后继续缺失运行。可用 `--max-new-runs 20` 分批重跑；分批结果不得
误当作完整论文统计。

制图输出含 `figures/`、`tables/` 和 `supplement.pdf`；`tables/` 中的 TeX 片段和
`table_provenance.json` 便于核对正文数字，不需要编译论文。原始报告脚本保留其冻结
字节与历史路径注释，统一通过 `reproduce.py` 调用，由 `code/package_runtime.py`
提供便携路径，避免旧脚本的默认目录造成误写。

## 从何处读代码

1. `p3_arena.py`：检测、清除、计时规则及离线模拟器。
2. `p3_robot.py`、`p3_sweep.py`、`p3_tour.py`、`p3_adaptive.py`、`p3_joint.py`：
   五代策略的递进；其配置类默认值就是实验参数。
3. `p3_homing.py`、`p3_frontier.py`、`p3_coverage.py`：保守定位、覆盖选点及连续单元证书。
4. `p3_expect_field.py`、`p2_grid_expectation.py`、`p1_intersection.py`：期望场及共享几何。
5. `p3_adaptive_bench.py::make_scene`、`p3_bench.py`：冻结场景的生成。
6. `run_p3_paper.py`：680 次实验的定义、动作审计、覆盖复核与配对统计。
7. `make_paper_figures.py`、`make_paper_tables.py`、`make_paper_trajectory_atlas.py`、
   `render_supplement.py`：正文图、表和完整补充图册。

已有专项检查为 `p3_selftest.py`、`p3_adaptive_checks.py` 和 `p3_joint_checks.py`；
对应历史结果在 `results/selftest.txt`、`adaptive_checks.txt`、`joint_checks.txt`。
与本题实验无关的历史诊断脚本和重复源码树未纳入附件。

## 本次交付核验

实际执行了 `--audit-only`、`--smoke` 和 `--figures`。680 次动作审计、真值访问守卫与
场景配对全部通过；320 个连续覆盖声明均通过 5 m 数值检查及独立 50 m 单元证书
重建。重算后的 `summary.json` 与冻结汇总完全一致。

试运行的 9 次动作序列、源位、误差场、请求参数、有效参数及退出后真值均与同种子
冻结记录逐项相同。实际重新生成了五幅正文图、表格及 140 页补充图册；未在此次整理中
完整重跑 680 次策略，论文数据沿用已冻结且本次重新审计的记录。

## 继续修改代码

现有 `code/*.py` 和 `reproduce.py` 可以继续修改。试验新代码时使用
`--dev --smoke --out DIR`，完整开发实验使用 `--dev --full --out DIR`。
入口会列出源码变化，并标明开发结果不代表论文原实验；数据、结果和其他已登记文件
仍须通过校验。新增文件或修改说明后，在完整仓库运行 `python3 paper/maintain.py refresh`
更新交付清单；这不会更改历史实验来源。新输出必须位于本题目录之外。

开发模式不能与 `--audit-only` 或 `--figures` 混用。采用新实验数据后，需要同步更新
结果来源、论文统计与图件，不能只刷新文件哈希就宣称复现了原论文。
