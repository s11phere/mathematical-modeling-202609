# figures/ —— 论文插图

## 1. 各图分别是什么

| 文件 | 用在哪 | 说明 |
|---|---|---|
| `multi_sensor_wedge_diagram.png` | **正文图 1**（`sections/05-model.tex` 5.1.2 节开头） | 多检测点角楔交会定位示意：三个检测点 $P_1,P_2,P_3$ 按真实 $\varepsilon=1^\circ$ 张成的角楔交出凸多边形 $\mathcal{R}$，右下角为 $\mathcal{R}$ 的局部放大（顶点 $V_i$、直径 $AB$ 与中点 $M$）；`.62\textwidth` |
| `p1-algorithm-flow.png` | **正文图 2**（`sections/05-model.tex` 5.1.3 节） | 问题一求解算法流程（`\includegraphics[width=.61\textwidth]`） |
| `p1-coverage-contrast.png` | **正文图 3**（`sections/05-model.tex` 5.1.4 节） | 直径圆覆盖判定成立/失败对照，(a) $A_1$、(b) $A_2$ 双面板（`.88\textwidth`），图内已标出越界顶点 $P$ 与 $|PM|>D/2$ |
| `p2-wedge-geometry.png` | **正文图 4**（5.2.2 节） | 两探测束交会与定位区域直径构造：两探测束相交出 $ABCD$、直径由对角线给出、视线交角 $\alpha$ 与 $r_{2T}$；右上角为交会区域局部放大（`.72\textwidth`） |
| `p2-mma-vs-pysim.png` | **正文图 5**（5.2.4 节） | 期望定位区域直径 $E[D]$ 的并排对比：(a) 理论闭式解（Mathematica，15 m 网格）；(b) 数值模拟（Python，30 m 网格）。两图共用同一坐标系、非线性色标与极小值标注，吻合度可目视直接比对（`\textwidth`） |
| `p2-contour60.png` | **正文图 6**（5.2.4 节） | $E[D]\le60$ m 等值线围出的第二检测点待选区域，浅蓝填充，两条闭合回路关于视线方向对称（`.58\textwidth`） |
| `p2-mma-heatmap.png` | 备用（未进正文） | 正文图 5(a) 的单幅版本（5.3 in 见方） |
| `p2-pysim-heatmap.png` | 备用（未进正文） | 正文图 5(b) 的单幅版本（5.3 in 见方） |

> **进正文的 6 张图不要删除或移动**，均为支撑材料（附录 A 清单里的 `figures/` 下文件）；
> 其中 3 张问题一插图在扁平的 `../Q1/` 下各有一份同名副本（交付用），改动后两份须同步。
> 问题二的原始材料（`Q2modeling.md` 里的参考热力图 `Q2_expected_diameter_heatmap.png`、
> `wedge_diagram.png` 及 Mathematica 脚本）保留在 `../Q2/`；其中 Mathematica 脚本与其导出的
> 数据、图表统一存放于 `../Q2/MMAcode/`。
>
> `p2-expected-diameter.png` 是问题二旧版结果图（含 `\bar D` 记号的单幅等值图 + 容差候选区域），
> 自 5.2.4 节改为「MMA 与 Python 并排 + 60 m 等值线」后不再被正文与附录引用，可自行决定删除。

## 2. 怎么生成

**问题一的 3 张图已定版**，其生成脚本不再随支撑材料交付（需要时可用
`git log --diff-filter=D --name-only -- B_locator/Q1/` 从历史中取回）。三张图的数据来源：
图 1 为按 $\varepsilon=1^\circ$ 绘制的示意图，不依赖数值；图 2 为算法流程图；图 3 由
`../Q1/cases/p1_case01.csv`、`p1_case02.csv` 经 `../Q1/p1_intersection.py` 求解后绘出
（数值汇总见 `../Q1/p1_summary.json`）。

问题二图 4 仍由脚本生成；图 5、图 6 及两张备用单幅图由同一个脚本从两份原始数据出图：

| 脚本 | 输出 |
|---|---|
| `../Q2/illustration_plot_Q2.py` | `p2-wedge-geometry.png`（**图 4**） |
| `../Q2/make_q2_paper_figures.py` | `p2-mma-vs-pysim.png`（**图 5**）、`p2-contour60.png`（**图 6**）、`p2-mma-heatmap.png`、`p2-pysim-heatmap.png` |

数据来源：图 5(a)/图 6 取 `../Q2/MMAcode/Q2_expected_diameter_data.csv`（Mathematica
导出的 15 m 网格闭式解）；图 5(b) 取 `../Q2/pysimulation/out/p2_grid/p2_grid_map.csv`
（Python 数值模拟的 30 m 网格结果）。脚本会自动把生成的 png 同时写入
`../Q2/figures/` 与本目录。

运行方式（需 Python 3 + matplotlib + numpy）：

```bash
python B_locator/Q2/make_q2_paper_figures.py
python B_locator/Q2/illustration_plot_Q2.py
```

**只想改论文文字的人不需要跑这些脚本。**

## 3. 新增插图的约定

1. **命名**：英文/数字，见名知意（如 `p3-flow.png`），不要用 `1.png` 这类序号名、不要用中文名。
2. **格式**：位图用 `png`（论文正文插图统一 400dpi）；矢量图用 `pdf`（推荐）/`eps`；**不要用 bmp**。
3. **字号与字体**：图内中文用宋体（`../fonts/simsun.ttc`，脚本里用
   `font_manager.fontManager.addfont(SIMSUN)` 注册后再由 `rcParams["font.serif"]` 命中），
   拉丁用 Times New Roman，数学符号用 Computer Modern，与正文一致；流程图等按 1:1 设计尺寸
   插入（图内字号 = 最终字号）。
4. **插入写法**（图题在图下方，模板已配 `position=bottom`）：
   ```latex
   \begin{figure}[!htbp]
       \centering
       \includegraphics[width=.6\textwidth]{fig-name}   % 不含扩展名，自动找 figures/
       \caption{图题}\label{fig:xx}
   \end{figure}
   ```
   正文引用一律用 `\cref{fig:xx}`（自动生成「图 1」），不要手写编号。
5. **图要说明"怎么来的"**：画构造过程（射线、交集、关键点、线段），不要只抄结论图形；
   若放大了角度/尺量，图题里必须写明放大倍数与真实值。
6. 新增图片后，记得同步附录 A 的「支撑材料文件列表」。
