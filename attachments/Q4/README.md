# 问题四：定向源定位、清除与连续覆盖

本附件集中提供论文所用算法、离线模拟器、230 次实验的完整动作证据、正文插图、
补充图册和复现入口，不依赖原项目的历史目录。建议先读 `DATA_SOURCES.md`，按
图表索引查看证据，再运行只读审计，最后按需重跑策略。

三次正式测试结果及官方原始日志另存于共享的 [formal-tests/](../formal-tests/README.md)，按论文案例编码查阅；本题复现入口用于离线实验。

## 文件结构

| 路径 | 评审用途 |
| --- | --- |
| `code/` | 必要算法、公共模块、场景生成、实验、动作审计、制表、绘图和六组已有专项检查；所有脚本集中一层。 |
| `data/` | 主集预先固定第一例的三代策略完整轨迹，供正文案例图直接读取；它们是冻结实验的可读摘录，实验场景本身由公开种子生成。 |
| `results/` | 冻结实验清单、230 行逐局记录、汇总、数据审计、表格数字来源及六组历史检查日志；`package_validation.json` 单独记录本次附件核验。 |
| `results/traces/` | 230 份 gzip 压缩的完整动作、回复、源参数、算法事件及退出报告。逐局表的 `trace` 字段直接指向文件。 |
| `figures/` | 五幅正文插图，各有矢量 PDF 和高清 PNG。 |
| `supplement.pdf` | 80 页完整轨迹图册：60 组三代策略、10 组消融、10 组快速策略；覆盖全部 230 次运行。 |
| `DATA_SOURCES.md` | 场景生成、种子、字段、计费和统计口径，以及论文公式、图表与证据的对应。 |
| `SOURCE_MANIFEST.json` | 文件来源、SHA256 和明确的路径适配记录；算法与模拟器保持冻结字节。 |
| `reproduce.py` | 统一入口；原始附件只读，新结果写入附件之外的指定目录。 |

本题目录和同级 `fonts/` 可一起移动；计算及审计只依赖本题目录，制图使用
`../fonts/simsun.ttc`。无需网络、在线接口、LaTeX 或 SciPy。

## 复现步骤

原始冻结实验使用 Windows、Python 3.12.14、NumPy 2.3.5。附件已在 macOS 下的
Python 3.12.14 / NumPy 2.3.5 和 Python 3.13.15 / NumPy 2.5.3 运行验证；绘图使用
Matplotlib 3.11.1。安装依赖可用：

```bash
python3 -m pip install 'numpy>=2.3,<3' 'matplotlib>=3.10,<4'
```

在本题目录执行：

```bash
# 不运行策略：检查全部压缩轨迹、独立重算动作费用、重建全部统计和置信区间。
python3 -B reproduce.py --audit-only

# 四类场景各取首例，三代策略 + 两项消融 + 三个速度档，共 17 次运行。
python3 -B reproduce.py --smoke --out ../reproduction-q4-smoke

# 从冻结数据重绘五幅正文图、80 页图册及全部表格。
python3 -B reproduce.py --figures --out ../reproduction-q4-figures

# 完整重跑 230 次实验；默认 2 个工作进程，可按机器条件调整。
python3 -B reproduce.py --full --out ../reproduction-q4-full --workers 2

# 在相同参数和输出目录继续尚未完成的实验。
python3 -B reproduce.py --full --out ../reproduction-q4-full --workers 2 --resume
```

除只读审计外，均须提供附件之外的新输出目录；脚本拒绝覆盖已有 `runs.jsonl`。
审计可选 `--out DIR` 保存 `package_audit.json`。制图输出为 `figures/`、`tables/`
和 `supplement.pdf`；表格输出是可核对的 TeX 片段，不需要编译论文。

若需检查连续覆盖的具体实现，可单独运行：

```bash
python3 -B code/p4_certificate_checks.py
python3 -B code/p4_compact_checks.py
```

其余检查入口为 `p4_homing_checks.py`、`p4_layout_v2_checks.py`、
`p4_route_v2_checks.py`、`p4_search_checks.py`。历史六组 37 项检查的日志均已包含，
源文件不必到其他文件夹查找。

## 从何处读代码

1. `p3_arena.py`、`p4_arena_ext.py`、`p4_search_bench.py`：检测规则、计费和场景生成。
2. `p4_robot.py`：论文 `grid` 策略；数据中名称为 `legacy`。
3. `p4_search.py`、`p4_certificate.py`：`joint` 策略及连续位置和朝向证书。
4. `p4_compact.py`、`p4_layout_v2.py`：最终 `compact` 策略与 21 站紧凑布局。
5. `p4_homing.py`、`p4_posterior.py`、`p4_route_v2.py`：定位兜底、后验中心和信息代价排路。
6. `run_paper_q4.py`：固定任务矩阵、参数、输出和配对统计。
7. `review_tools.py`：独立动作审计、全统计复核及补充图册；其分组明确复用主集前
   10 次 `compact`，不会把消融基准错当成额外实验。

`make_paper_figures.py`、`make_paper_tables.py` 是报告脚本；统一经 `reproduce.py`
调用，使用附件内的数据和独立的新输出目录。原始算法文件保留历史注释和可选接口，
不需要运行其开发期默认命令。

## 本次验证与复现范围

只读核验通过了全部 230 份轨迹哈希、65,229 条动作、60 组源参数配对，所有分组
统计及配对置信区间均与冻结汇总完全一致。已实际执行 17 次试运行并重新生成全部
五幅图、表格及 80 页补充图册；移出原项目后也完成独立审计和试运行。

**新运行不承诺与原 Windows 记录逐动作相同。** 本次 macOS 试运行中 17 局均正常
结束，两个严格策略的 8 局均全清并取得认证；其中 12 局完整时间与历史差异小于
`1e-6` s，另 5 局路径和虚拟时间不同。相同 Python/NumPy 版本下仍可见这些差异，
尚未把全部分支差异归因到具体平台数值运算。算法文件及配置未改动，源坐标最大
浮点差和逐局比较见 `results/package_validation.json`。评审重建论文数字应使用
只读审计和冻结图表；新运行结果作为独立复现实验保留，不覆盖论文数据。

## 继续修改代码

现有 `code/*.py` 和 `reproduce.py` 可以继续修改。试验新代码时使用
`--dev --smoke --out DIR`，完整开发实验使用 `--dev --full --out DIR`。
入口会列出源码变化，并标明开发结果不代表论文原实验；数据、结果和其他已登记文件
仍须通过校验。新增文件或修改说明后，在完整仓库运行 `python3 paper/maintain.py refresh`
更新交付清单；这不会更改历史实验来源。新输出必须位于本题目录之外。

开发模式不能与 `--audit-only` 或 `--figures` 混用。采用新实验数据后，需要同步更新
结果来源、论文统计与图件，不能只刷新文件哈希就宣称复现了原论文。
