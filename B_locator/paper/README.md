# B 题论文工程

在仓库根目录运行 `bash B_locator/paper/build.sh`。脚本优先使用 XeLaTeX，也可使用 Tectonic；检查字体、交叉引用和编译错误后，生成本目录的 `main.pdf`。

正文位于 `sections/`，插图位于 `figures/`。保留 `B_locator/` 的目录结构即可编译。正文宋体、楷体使用 `fonts/` 中的字体；黑体使用 Heiti SC、SimHei 或 FandolHei。

问题一输入位于 `../Q1/cases/`，结果位于 `../Q1/results/`，运行说明见 `../Q1/README.md`。附录直接载入问题一的求解、实验和绘图源码。

问题二保留原论文、原代码及原始导出结构：Mathematica notebook 和网格数据位于 `../Q2/MMAcode/`；Python 程序位于 `../Q2/pysimulation/src/p2_grid_expectation.py`，数据位于 `../Q2/pysimulation/out/p2_grid/`。正文图由 `../Q2/make_q2_paper_figures.py` 使用上述数据生成。

问题二此次按原稿恢复，公式与程序对应关系的审查记录放在仓库 `tmp/q2-restoration/`，不作为论文内容。问题三正文位于 `sections/q3-model.tex`，问题四正文位于 `sections/q4-model.tex`，均附可复现数据和程序。问题四按照“模型建立—算法实践—数据分析”展开，包含定向接收、连续无源证书、三版策略演进、双侧定位推导、21站布局及230次统一实验，配五幅矢量插图。复现说明见 `../Q4/PAPER_REPRODUCE.md`。

Q4摘要和问题分析已回填，摘要总述与结尾已衔接四问。第六章已补充参数敏感性与稳健性、模型优点、模型局限及改进方向，依据四问已有推导和离线实验评价，篇幅不超过两页。参考文献中的原有占位及正式模拟器测试记录仍需后续完善；本轮离线实验不作为正式测试结果。
