# figures/ —— 论文插图

## 1. 当前 6 张图分别是什么

| 文件 | 用在哪 | 说明 |
|---|---|---|
| `p1-algorithm-flow.png` | **正文图 1**（`sections/05-model.tex` 5.1.3 节） | 问题一求解算法流程（`\includegraphics[width=.58\textwidth]`） |
| `p1-coverage-contrast.png` | **正文图 2**（`sections/05-model.tex` 5.1.4 节） | 直径圆覆盖判定成立/失败对照，(a) $A_1$、(b) $A_2$ 双面板（`.88\textwidth`），图内已标出越界顶点 $P$ 与 $|PM|>D/2$ |
| `p1-wedge-intersection.png` | 正文未引用（**备选**） | 角楔交会与直径测量：(a) 两个检测点的 ±ε 角楔（半张角按 5:1 放大示意）交出区域 $\mathcal{R}$，最远顶点对 $A,B$ 给出直径、$M$ 为其中点；(b) 真实算例 $A_2$ 的覆盖失效 |
| `p1-region-bounded.png` | 正文未引用 | 定位区域 + 顶点 + 直径端点 + 直径圆（带标题与图例版） |
| `p1-region-bounded-plain.png` | 正文未引用 | 同上，「简版」（无标题/图例） |
| `p1-unbounded.png` | 正文未引用 | 无界情形示意图（两示向度近似同向） |

> 未进正文的 4 张**属于支撑材料**（附录 A 表里的 `figures/p1-*.png`），**不要删除或移动**。

## 2. 怎么生成

生成脚本在 `../Q1/figures/`：

| 脚本 | 输出 |
|---|---|
| `make_p1_flowchart.py` | `p1-algorithm-flow.png`（**图 1**） |
| `make_p1_figures.py` | `p1-coverage-contrast.png`（**图 2**）、`p1-region-bounded(-plain).png`、`p1-unbounded.png` |
| `make_p1_wedge_figure.py` | `p1-wedge-intersection.png`（备选图） |

`make_p1_wedge_figure.py` 末尾带断言自检：示意构图的四个顶点必须共圆、直径必须等于 $2R$，
不满足即报错退出（避免画出"多个顶点到 M 距离不等"的矛盾图）。
`make_p1_flowchart.py` 亦自带排版自检（文字不越框、流程图"是/否"不与框重叠、内容不出画布）。

运行方式（仓库根目录下，用隔离环境，避免污染系统 Python）：

```bash
MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q1/figures/make_p1_wedge_figure.py
MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q1/figures/make_p1_flowchart.py
MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q1/figures/make_p1_figures.py
```

需要 Python 3 + matplotlib + numpy。**只想改论文文字的人不需要跑这些脚本。**

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
