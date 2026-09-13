# 问题三：多源定位、清除与覆盖判定

本附件采用 2026-09-13 完整重跑的 680 次离线实验，正文、图表和逐动作证据均取自这批结果。最终策略为 `joint`；另保留四代比较策略及四项单因素消融。三次正式测试及官方原始日志见共享的 [formal-tests/](../formal-tests/README.md)，不计入离线实验。

## 文件与入口

1. `reproduce.py`：审计、试运行、完整重跑和制图的统一入口。
2. `code/`：五代策略、离线模拟器、几何和期望场模块、实验及核验脚本。
3. `data/`：九张期望场、图族参数、回退基准场及其生成参数。
4. `results/`：680 行逐局结果、统计、实验清单、动作审计和连续证书；`traces/` 保留全部 680 份动作日志，`adoption.json` 说明本批数据来源。
5. `figures/`：正文五幅 PDF 插图；全部轨迹图册可按需生成，不重复装入交付包。
6. `DATA_SOURCES.md`、`SOURCE_MANIFEST.json`：模型、输入、图表证据索引及文件完整性清单。

## 复现方式

本批实验使用 macOS arm64、Python 3.12.14、NumPy 2.3.5；制图使用 Matplotlib 3.11.2。建议使用相同 Python/NumPy 版本，依赖安装与命令如下（在本题目录执行）：

```bash
python3 -m pip install 'numpy==2.3.5' 'matplotlib>=3.10,<4'
python3 -B reproduce.py --audit-only
python3 -B reproduce.py --smoke --out ../reproduction-q3-smoke
python3 -B reproduce.py --full --out ../reproduction-q3-full
python3 -B reproduce.py --figures --out ../reproduction-q3-figures
```

`--audit-only` 重算全部动作账本、统计和覆盖证书；`--smoke` 运行同一场景的五策略和四项消融，共 9 次；`--full` 完整运行 120 组 × 5 策略 + 20 组 × 4 消融，共 680 次。所有新输出均须位于本题目录之外。完整实验支持以相同命令续跑，也可用 `--max-new-runs 20` 分批计算。

`--figures` 从保存结果生成正文图、表格和 140 页完整轨迹图册（120 页主实验、20 页消融）。附带全部动作证据，图册可随时重建；制表程序只生成数字和表格，摘要文字由论文维护。制图需要同级 `fonts/`，或增加 `--font /path/to/chinese-font.ttf`。

## 核验与代码索引

本批 680 次策略均已实际执行，并完成 680 次动作、真值访问守卫和场景配对检查；320 个连续覆盖声明通过 5 m 数值检查及独立 50 m 单元证书。统一自检 40 项、adaptive 7 项、joint 12 项均通过，记录见 `results/`。五幅正文图和全部统计表已由本批数据重新生成。

先读 `p3_arena.py` 的接口与计费，再读 `p3_robot.py`、`p3_sweep.py`、`p3_tour.py`、`p3_adaptive.py`、`p3_joint.py` 的策略递进。`p3_homing.py`、`p3_frontier.py`、`p3_coverage.py` 分别处理定位、选点与连续证书；`run_p3_paper.py` 定义实验矩阵和独立统计。

图族积分使用面积先验乘接收半径存活因子；sweep/tour 的局部补测仍以面积权重作启发式估价。两者用途及核验口径见 `DATA_SOURCES.md`，不以局部估价代替保守定位或覆盖证书。

新平台的浮点运算可能改变启发式分支、动作序列和虚拟时间；墙钟耗时也随设备和负载变化。核对论文精确数字使用 `--audit-only` 重建保存证据，`--full` 用于独立执行同一模型与实验矩阵。完整新实验已替换旧批数据，旧、新运行不混入同一汇总。

修改代码后可用 `--dev --smoke/--full` 产生另存的新实验；采用新结果时须同步论文、图表和来源说明。统一入口会检查文件和实际算法输入的 SHA256，清单更新由仓库中的 `paper/maintain.py` 负责。
