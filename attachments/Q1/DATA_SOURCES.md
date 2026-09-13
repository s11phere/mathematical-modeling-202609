# 问题一数据来源与论文索引

这里的数据为依据题设自行构造的几何算例与固定种子数值实验，不是现场实测数据。
题设提供测向误差界等物理规则，具体检测点与示向度由 `code/p1_experiments.py` 生成。
原始来源路径只用于追溯；运行时全部输入均在本题目录内。

| 附件文件 | 原始来源 | 生成与作用 |
| --- | --- | --- |
| `data/p1_case01.csv` 至 `p1_case05.csv` | `B_locator/Q1/cases/` 同名文件 | 种子 20260901，五组分别含 6、5、4、5、6 个检测点。 |
| `data/*.truth.json` | 同上 | 对应真源位置、接收半径与几何统计，只作校验。 |
| `results/p1_results.jsonl` | `B_locator/Q1/results/p1_results.jsonl` | 每行一组：求得顶点、直径端点、圆心、覆盖结果。 |
| `results/p1_summary.json` | `B_locator/Q1/results/p1_summary.json` | 五组汇总、四组扫描、随机种子及交叉校验结果。 |
| `figures/*.png` | `B_locator/paper/figures/` 同名文件 | 论文实际使用的三幅图。 |
| `supplement.pdf` | `code/review_figures.py` 从上述输入和汇总生成 | 全部五组区域及四组扫描，不新增随机实验。 |

## 输入字段与单位

坐标、距离单位为 m；示向度单位为度，从正东逆时针计量。求解器仅读取 CSV 的
`x_m,y_m,svd_deg`；`det_id` 为点编号。`true_svd_deg,true_az_err_deg,dist_m`
及 `.truth.json` 为生成器的真值记录，不参与定位。误差界为 1°。

覆盖判定采用完整精度，JSON 中部分几何量已作显示舍入；不要用舍入后的圆心和顶点
重新判定相切是否成立。`--audit-only` 从未改动的原始输入重算后再比较结果。

## 论文内容与结果字段

以下键均位于 `results/p1_summary.json`。

| 论文内容 | 结果位置 |
| --- | --- |
| 五组算例结果表 | `per_case` 的 `diameter_m,circle_radius_m,max_vertex_dist_m,ratio,coverage`。检测点数与顶点数同时见逐例 JSONL。 |
| 直径范围 10.59 至 25.64 m，2 组圆未覆盖 | `cases_summary.diameter_m_range,n_diameter_circle_misses`。 |
| 算例 A2、A3 的越界程度 | `per_case[1]`、`per_case[2]` 的 `excess_m,excess_pct,worst_vertex_angle_deg`。 |
| 四组随机扫描表 | `sweeps.two_point,two_point_err,well_conditioned,well_conditioned_err`。 |
| 独立算法核验 | `validation.max_vertex_difference_m,max_diameter_difference_m`；前者为顶点枚举与半平面裁剪差值，后者为枚举与旋转卡壳直径差值。 |
| 多检测点交会示意图 | `code/make_figures.py::wedge_diagram` 的固定构造，仅说明几何关系。 |
| 流程图与覆盖对照图 | `code/make_figures.py::flowchart,coverage`；后者采用算例 A1、A2。 |

两测点扫描 20000 次，种子 17；3 至 6 测点扫描 4000 次，种子 5。每类各有理想示向度
与加入误差两组，共 48000 次；误差随机流的种子为构型种子加 900001，理想与含误差组
共用检测点构型。两测点距离范围为 150 至 1800 m，多测点为 300 至 1500 m。

| 扫描 | 有界有效数 | 直径圆未覆盖数 | 未覆盖比例 |
| --- | ---: | ---: | ---: |
| 两测点理想示向度 | 20000 | 231 | 1.1550% |
| 两测点含误差 | 19996 | 246 | 1.2302% |
| 多测点理想示向度 | 3472 | 113 | 3.2546% |
| 多测点含误差 | 3472 | 993 | 28.6002% |

比例以非空有界构型为分母；两组多测点各有 528 次未满足方位间隔条件而被筛除，
两测点含误差组另有 4 次无界。`worst_config` 保留最坏构型的完整输入。这些扫描检验
角楔几何性质，未按接收半径筛选检测点，不能将其比例解释为任意现场布点的失败概率。

全部原算法、输入、结果与正文图均保持源文件字节不变；逐文件 SHA256 见
`SOURCE_MANIFEST.json`。复现步骤及本次实际执行范围见 `README.md`。
