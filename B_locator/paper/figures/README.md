# figures/ —— 论文插图

## 1. 当前 5 张图分别是什么

| 文件 | 用在哪 | 说明 |
|---|---|---|
| `multi_sensor_wedge_diagram.png` | **正文图 1**（`sections/05-model.tex` 5.1.2 节开头） | 多检测点角楔交会定位示意：三个检测点 $P_1,P_2,P_3$ 按真实 $\varepsilon=1^\circ$ 张成的角楔交出凸多边形 $\mathcal{R}$，右下角为 $\mathcal{R}$ 的局部放大（顶点 $V_i$、直径 $AB$ 与中点 $M$）；`.62\textwidth` |
| `p1-algorithm-flow.png` | **正文图 2**（`sections/05-model.tex` 5.1.3 节） | 问题一求解算法流程（`\includegraphics[width=.61\textwidth]`） |
| `p1-coverage-contrast.png` | **正文图 3**（`sections/05-model.tex` 5.1.4 节） | 直径圆覆盖判定成立/失败对照，(a) $A_1$、(b) $A_2$ 双面板（`.88\textwidth`），图内已标出越界顶点 $P$ 与 $|PM|>D/2$ |
| `p2-wedge-geometry.png` | **正文图 4**（5.2.2 节） | 两探测束交会与定位区域直径构造：$P_1,P_2$ 的探测束相交出 $ABCD$、直径由 $BD$ 给出、视线交角 $\alpha$ 与 $r_{2S}$；半张角放大到 $2^\circ$ 示意，右上角局部放大（`.72\textwidth`） |
| `p2-expected-diameter.png` | **正文图 5**（5.2.4 节） | (a) 期望定位区域直径 $E[D](a,b)$ 的非线性色标等值图；(b) 第二个检测点的候选区域（深色 $\le1.05E[D]_{\min}$、浅色 $\le1.20E[D]_{\min}$），标出 $P_1$、视线 $\psi_1$ 与示意源点 $S$（`.92\textwidth`） |

> 5 张图全部进正文，均为支撑材料（附录 A 清单里的 `figures/` 下文件），**不要删除或移动**；
> 其中 3 张问题一插图在扁平的 `../Q1/` 下各有一份同名副本（交付用），改动后两份须同步。
> 问题二的原始材料（`Q2modeling.md` 里的参考热力图 `Q2_expected_diameter_heatmap.png`、
> `wedge_diagram.png` 及 Mathematica 脚本）保留在 `../Q2/`；其中 Mathematica 脚本与其导出的
> 数据、图表统一存放于 `../Q2/MMAcode/`，正文用的是上面两张重绘图。

## 2. 怎么生成

**问题一的 3 张图已定版**，其生成脚本不再随支撑材料交付（需要时可用
`git log --diff-filter=D --name-only -- B_locator/Q1/` 从历史中取回）。三张图的数据来源：
图 1 为按 $\varepsilon=1^\circ$ 绘制的示意图，不依赖数值；图 2 为算法流程图；图 3 由
`../Q1/cases/p1_case01.csv`、`p1_case02.csv` 经 `../Q1/p1_intersection.py` 求解后绘出
（数值汇总见 `../Q1/p1_summary.json`）。

问题二的两张图仍由脚本生成：

| 脚本 | 输出 |
|---|---|
| `../Q2/figures/make_q2_wedge_figure.py` | `p2-wedge-geometry.png`（**图 4**） |
| `../Q2/figures/make_q2_figures.py` | `p2-expected-diameter.png`（**图 5**） |

运行方式（仓库根目录下，用隔离环境，避免污染系统 Python；需 Python 3 + matplotlib + numpy）：

```bash
MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q2/src/q2_solution.py
MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q2/figures/make_q2_wedge_figure.py
MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q2/figures/make_q2_figures.py
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
