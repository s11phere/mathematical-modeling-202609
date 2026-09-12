# 问题一：示向度交会定位

在附件根目录 `B_locator/` 执行：

```bash
python Q1/p1_experiments.py
python Q1/make_figures.py
```

依赖 Python 3、NumPy、Matplotlib。脚本也可用绝对路径从其他目录运行；默认输出均按脚本位置定位。
第一条命令重建算例、正文数值和几何校验量，第二条重绘三幅正文图。
单个算例可用 `python Q1/p1_intersection.py Q1/cases/p1_case02.csv` 求解。

| 文件 | 用途 |
|---|---|
| `p1_intersection.py` | 角楔交集、直径和覆盖判定；可直接求解 CSV |
| `p1_experiments.py` | 五组算例、四组扫描及独立几何校验 |
| `make_figures.py` | 从求解结果绘图，输出至 `../paper/figures/` |
| `cases/p1_case01.csv` 至 `p1_case05.csv` | 五组输入；求解只读 `x_m,y_m,svd_deg` 三列 |
| `cases/*.truth.json` | 生成算例的真值，仅用于误差核验 |
| `results/p1_results.jsonl` | 每行一组算例，含顶点、直径端点、圆心及最远顶点 |
| `results/p1_summary.json` | 正文表格、扫描统计、参数和校验数值 |

CSV 中 `true_svd_deg,true_az_err_deg,dist_m` 是生成器记录的真值，不参与定位。
坐标单位为 m，角度单位为度，从正东逆时针量取；误差界为 1°。
结果文件为展示而舍入，覆盖判定使用求解时的完整精度，不能用舍入后的顶点重算相切判据。

## 正文数值索引

以下键均位于 `results/p1_summary.json`，`A1` 至 `A5` 与正文算例一一对应。

| 正文内容 | JSON 来源 |
|---|---|
| 五组算例结果表 | `per_case`：`n_bearings,n_vertices,diameter_m,circle_radius_m,max_vertex_dist_m,ratio,coverage` |
| 直径范围 10.59–25.64 m、2 组不覆盖 | `cases_summary.diameter_m_range,n_diameter_circle_misses` |
| A2 越界 0.9819 m（10.5518%）、张角 84.21° | `per_case[1].excess_m,excess_pct,worst_vertex_angle_deg` |
| A3 越界 0.9259 m（7.2215%） | `per_case[2].excess_m,excess_pct` |
| 方位张角 179.97–249.03°、最小间隔 25.11° | `validation.azimuth_span_deg_range,min_azimuth_gap_deg` |
| 检测点至源点距离 159.668–1294.151 m | `validation.source_distance_m_range` |
| 顶点枚举与裁剪最大偏差 6.44×10⁻¹⁰ m | `validation.max_vertex_difference_m` |
| 枚举直径与旋转卡壳差值为 0 | `validation.max_diameter_difference_m` |
| 半平面/覆盖容差 10⁻⁶ m / 10⁻⁹ m | `meta.halfplane_tolerance_m,coverage_tolerance_m` |

| 扫描 | JSON 键（`sweeps` 下） | 尝试数 | 有界数 | 失败数 | 失败率 | 最坏半径比 |
|---|---|---:|---:|---:|---:|---:|
| 两测点，无误差 | `two_point` | 20000 | 20000 | 231 | 1.1550% | 1.033554 |
| 3–6 测点，无误差 | `well_conditioned` | 4000 | 3472 | 113 | 3.2546% | 1.030373 |
| 两测点，含误差 | `two_point_err` | 20000 | 19996 | 246 | 1.2302% | 1.034573 |
| 3–6 测点，含误差 | `well_conditioned_err` | 4000 | 3472 | 993 | 28.6002% | 1.687604 |

失败率的分母为有界构型数。两组 3–6 测点扫描各有 528 次因方位间隔不大于 3° 被筛除，记录于
`n_rejected_geometry`；两测点含误差组另有 4 次无界，记录于 `n_unbounded`。
`worst_ratio` 为最远顶点距圆心与半直径之比，固定圆心扩大半径的幅度为该比值减 1。
最坏构型的完整精度输入保存在 `worst_config`，可调用 `solve_full()` 单独复算。
按检测点数的失败率见 `sweeps.well_conditioned_err.per_m`，依次为 16.98%、28.29%、34.45%、36.93%。

算例种子为 20260901；两测点扫描种子为 17，3–6 测点扫描种子为 5；误差流种子在扫描种子上加 900001。
同组有误差、无误差扫描使用相同检测点构型，误差独立服从 [-1°,1°] 均匀分布。
两测点扫描距离为 150–1800 m，3–6 测点为 300–1500 m；这些扫描考察角楔几何性质，不模拟接收半径筛选。
因此失败率只描述这些采样分布，不能直接解释为任意现场布点的失败概率。

## 运行与核验

完整运行会重新生成固定种子算例，逐例检查真值可行性，并用大框半平面裁剪和旋转卡壳交叉核验。
裁剪只用于有界算例校验，外框不能作为无界判据。
主算法先构造可行顶点，排除空集后再检查公共延伸方向；无公共方向但顶点不足 3 个时返回退化状态。

使用 `--out /绝对路径` 可另存重跑结果；`--skip-sweep` 仅输出算例和
`results/p1_cases_only.json`，不会覆盖已有的完整扫描汇总。三张图只在 `paper/figures/` 保留一份。
