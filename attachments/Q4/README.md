# 问题四：定向源定位、清除与连续覆盖

本题提供完整算法、230 次离线实验、逐动作证据和五幅正文 PDF。当前论文采用 2026-09-13 全量重跑结果；三次正式测试单独保存在 [formal-tests](../formal-tests/README.md)。建议先阅读 `DATA_SOURCES.md`，再运行审计或完整实验。

## 文件列表

1. `reproduce.py`、`README.md`、`DATA_SOURCES.md`、`SOURCE_MANIFEST.json`：入口、来源和文件校验。
2. `code/`：三代策略、连续覆盖、定位清除、后验中心、信息航路、模拟器、实验与检查程序。
3. `data/representative_*.json`：随机主集第一例的三代策略轨迹；它们是结果摘录，场景由公开种子生成。
4. `results/`：`runs.jsonl`、`summary.json`、`manifest.json`、`audit.json`、`table_provenance.json`、`adoption.json`、`package_validation.json` 及专项检查；`traces/` 含 230 份完整 gzip 日志。
5. `figures/`：五幅正文矢量 PDF。80 页完整图册及 PNG 可按需由 `--figures` 生成，不重复收入提交包。

## 环境与复现

本批计算环境为 macOS、Python 3.12.14、NumPy 2.3.5，两个工作进程。Python 3.12 以上环境安装附件根目录的 `requirements.txt`；制图共用 `../fonts/simsun.ttc`。计算无需网络服务、LaTeX 或原研究目录。

在本题目录运行：

```bash
# 由全部动作重建成本、分组统计和配对区间。
python3 -B reproduce.py --audit-only
# 17 次小规模试运行。
python3 -B reproduce.py --smoke --out ../reproduction-q4-smoke
# 重绘正文图、表格和完整图册。
python3 -B reproduce.py --figures --out ../reproduction-q4-figures
# 完整重跑 230 次实验；同参数续跑时增加 --resume。
python3 -B reproduce.py --full --out ../reproduction-q4-full --workers 2
```

新输出须在本题目录之外。`--audit-only --out DIR` 可保存独立审计；其余模式必须指定新目录。制图输出 `figures/`、`tables/` 和 `supplement.pdf`，不改写论文文案。跨平台浮点差异可能影响启发式选择，完整重跑不保证逐动作相同；保存动作的统计可独立精确重建。

## 代码阅读与核验

- `p3_arena.py`、`p4_arena_ext.py`、`p4_search_bench.py`：观测、计费和场景。
- `p4_robot.py`、`p4_search.py`、`p4_compact.py`：`grid`、`joint`、`compact` 三代策略。
- `p4_certificate.py`、`p4_layout_v2.py`：连续位置与朝向证书、21 站布局。
- `p4_homing.py`、`p4_posterior.py`、`p4_route_v2.py`：补测清除、后验估计和航路。
- `run_paper_q4.py`：任务矩阵与统计；`review_tools.py`：逐动作独立审计及补图。

本次完整 230 次实验均正常结束；两个严格策略共 120 次全清并通过连续认证。230 份日志、65173 条动作账本、60 组场景配对以及全部分组和置信区间审计通过；五幅正文图及全部表格已从当前结果重新生成。六组专项检查共 37 项通过，记录见 `results/`。

开发实验可使用 `--dev --smoke` 或 `--dev --full`，在新目录保存输出；采用新结果时需同时更新论文与图表，不能仅刷新文件校验值。普通入口严格核验算法与本批实验源码。旧 Windows 批次只在本地归档保留，不进入提交包或当前统计。
