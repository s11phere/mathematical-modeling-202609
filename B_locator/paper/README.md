# B 题论文工程

在仓库根目录运行 `bash B_locator/paper/build.sh`。脚本优先使用 XeLaTeX，也可使用 Tectonic；检查字体、交叉引用和编译错误后，生成本目录的 `main.pdf`。

正文位于 `sections/`，插图位于 `figures/`。保留 `B_locator/` 的目录结构即可编译。正文宋体、楷体使用 `fonts/` 中的字体；黑体使用 Heiti SC、SimHei 或 FandolHei。

问题一输入位于 `../Q1/cases/`，结果位于 `../Q1/results/`，运行说明见 `../Q1/README.md`。附录直接载入问题一的求解、实验和绘图源码。

问题二保留原论文、原代码及原始导出结构：Mathematica notebook 和网格数据位于 `../Q2/MMAcode/`；Python 程序位于 `../Q2/pysimulation/src/p2_grid_expectation.py`，数据位于 `../Q2/pysimulation/out/p2_grid/`。正文图由 `../Q2/make_q2_paper_figures.py` 使用上述数据生成。

问题三正文位于 `sections/q3-*.tex`，附件位于 `../Q3/`，包含代码、冻结实验数据、结果与复现入口，运行说明见 `../Q3/README.md`。

本次整合保留 main 中问题一、二的正文、程序、数据和 PNG 插图，合入问题三正文与附件。问题一、二插图不放置同名 PDF，以免 LaTeX 优先读取旧图。问题三正式测试、问题四和总评等尚未完成部分仍保留待补占位。
