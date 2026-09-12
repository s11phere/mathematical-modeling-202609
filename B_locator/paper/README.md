# B 题论文工程

在仓库根目录运行 `bash B_locator/paper/build.sh`。脚本优先使用 XeLaTeX，也可使用 Tectonic；检查字体、交叉引用和编译错误后，生成本目录的 `main.pdf`。

正文位于 `sections/`，插图位于 `figures/`。保留 `B_locator/` 的目录结构即可编译。正文宋体、楷体使用 `fonts/` 中的字体；黑体使用 Heiti SC、SimHei 或 FandolHei。

问题一输入位于 `../Q1/cases/`，结果位于 `../Q1/results/`，运行说明见 `../Q1/README.md`。附录直接载入问题一的求解、实验和绘图源码。

问题二保留原论文、原代码及原始导出结构：Mathematica notebook 和网格数据位于 `../Q2/MMAcode/`；Python 程序位于 `../Q2/pysimulation/src/p2_grid_expectation.py`，数据位于 `../Q2/pysimulation/out/p2_grid/`。正文图由 `../Q2/make_q2_paper_figures.py` 使用上述数据生成。

问题三正文位于 `sections/q3-*.tex`，附件位于 `../Q3/`，包含代码、冻结实验数据、结果与复现入口，运行说明见 `../Q3/README.md`。

问题四正文位于 `sections/q4-model.tex`，附件位于 `../Q4/`，采用 `compact + strict` 最终策略，包含五幅正文图、230 次配对实验及核心代码附录（完整源码保留在 Q4 附件中），复现说明见 `../Q4/PAPER_REPRODUCE.md`。摘要总述、结尾与关键词以及第六章模型评价与改进已接入四问内容。

本次整合保持 main 中问题一、二、三的正文、程序、数据、插图和附录不变。问题一、二插图不放置同名 PDF，以免 LaTeX 优先读取旧图。正式模拟器测试记录与参考文献中的原有占位仍需后续完善；离线实验不作为正式测试结果。
