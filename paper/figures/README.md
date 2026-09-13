# 正文插图

这里只保留论文实际使用的16幅图。问题一、二用 PNG，问题三、四用矢量 PDF；对应附件 `figures/` 保留交付版本，补充图件集中在各题 `supplement.pdf`。

| 问题 | 正文图片文件名（不含扩展名） | 程序与数据来源 |
| --- | --- | --- |
| 一 | `multi_sensor_wedge_diagram`、`p1-algorithm-flow`、`p1-coverage-contrast` | `attachments/Q1/` |
| 二 | `p2-wedge-geometry`、`p2-mma-vs-pysim`、`p2-contour60` | `attachments/Q2/` |
| 三 | `q3-geometry-certificate`、`q3-route-field-sweep-tour`、`q3-route-tour-adaptive-joint`、`q3-time-cost-clearance`、`q3-scenarios-ablation` | `attachments/Q3/` |
| 四 | `q4-geometry-certificate`、`q4-homing-posterior`、`q4-route-generations`、`q4-results-cost`、`q4-ablation-tradeoff` | `attachments/Q4/` |

路径相对仓库根目录。每题 `DATA_SOURCES.md` 给出图件、公式和保存数据的对应关系；几何示意与实验结果有明确区分。

在仓库根目录运行（将 `Q1` 改为需要的题号）：

```bash
python3 -B attachments/Q1/reproduce.py --figures --out attachments/.local/q1-figures
```

先查看新图，再将采用的版本同步到本目录及对应附件 `figures/`。不要保留同名旧 PDF 与新 PNG 竞争加载；LaTeX 会优先读取 PDF。`python3 paper/maintain.py check` 会检查论文与附件图件的字节是否一致。

问题四单独重绘指定结果时，可用 `python attachments/Q4/code/make_paper_figures.py --data <结果目录> --out <图件目录>`；轨迹图也从该目录读取对应压缩轨迹。直接调用制表器时，设置 `Q4_REVIEW_OUT` 为输出目录，另用 `Q4_REVIEW_DATA` 选择输入目录；输入默认仍为冻结结果。`--audit-only` 仅核验，不生成图件。本次重绘的问题三、四结果图在对应附件中同时保留 PDF 和高清 PNG。

中文、拉丁与数学字体及交叉引用规则见 `../FORMAT-GUIDE.md`。调整数据时须同时更新对应统计、来源说明和补充图册，避免只替换图片。
