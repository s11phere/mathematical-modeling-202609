# B 题论文工程 —— 人工修改 & 手动编译指南

> 题目：**无线电干扰源的快速自动定位与清除模型**（2026 全国大学生数学建模竞赛 B 题）
> 当前状态：**问题一（5.1 节）、问题二（5.2 节）均已定稿且数据已对齐**：问题一的全部数值、
> 图表与附录 B 粘贴的代码，均由 `B_locator/Q1/p1_intersection.py`（求解）与
> `p1_experiments.py`（算例生成 + 逐例求解 + 四组随机扫描：理想构型、实际构型各两组）的运行结果产出，汇总见
> `B_locator/Q1/p1_summary.json`；正文改数值前请先重跑该脚本并同步附录 B。
> 摘要、问题背景与重述、问题分析、5.1、5.2 已按“语言精修”重新校订；
> 问题三、四与模型评价章尚有 **9 处 `【待填充：…】`** 待补（清单见第 5 节）。
> 格式（字体 / 间距 / 图表）已定稿，**改文字不会影响排版**。

---

## 1. 怎么编译（两种方式，任选其一）

**必须用 XeLaTeX，不能用 pdfLaTeX**（模板会在 pdfLaTeX 下直接报错）。

### macOS / Linux
```bash
cd B_locator/paper
bash build.sh          # XeLaTeX 连跑两遍 + 缺字/报错自检；等价于 xelatex main.tex 跑两次
bash build.sh clean    # 只清理编译中间文件（*.aux *.log *.out *.toc …）
```

### Windows / MiKTeX
1. 在 TeXworks / TeXstudio / WinEdt 里打开 `main.tex`，把编译器设为 **XeLaTeX**（不是 pdfLaTeX），
   点两次编译（第一遍生成交叉引用，第二遍才正确）。
2. 首次编译若弹窗提示安装缺失宏包，选「允许 / Install」。
3. 命令行等价写法（在 `paper` 目录下）：
   ```bat
   xelatex -interaction=nonstopmode main.tex
   xelatex -interaction=nonstopmode main.tex
   ```

产物就是本目录的 **`main.pdf`**。编译后请确认两点：**没有 `Missing character`（缺字方框）**、**没有报错**。

### 没有 XeLaTeX 时的应急编译（tectonic）
仓库 `tmp/` 下自带 tectonic 与缓存，可在**不改动本目录任何文件**的前提下产出一份可阅览的
PDF（在 `tmp/paper-build/bld/` 里搭影子目录；`cumcmthesis.cls`、`fonts/`、`figures/`、`code/`
以符号链接引用，`sections/` 与 `main.tex` 复制后只做两处 tectonic 兼容补丁：临时指定
等宽中文字体、把 `\AtBeginDocument` 内联为等效的 `\setlength`）：

```bash
bash tmp/paper-build/build-pdf.sh      # 产物 tmp/paper-build/bld/main.pdf，并打印缺字/报错/页数自检
```

应急产物与 XeLaTeX 结果版式一致（同样的类文件、字体、体例），但**正式交付仍以
XeLaTeX + `build.sh` 的结果为准**。

**本机已用这条路子产出一份 `main.pdf`（21 页、无缺字、无报错），并已回填为 `paper/main.pdf`。**
之后改完正文要重新出 `main.pdf`，直接跑仓库里现成的脚本即可（`tmp/` 不入库，本机工具链）：

```bash
cd /path/to/repo
bash tmp/paper-build/regen-main-pdf.sh            # 出 PDF 并回填 B_locator/paper/main.pdf
bash tmp/paper-build/regen-main-pdf.sh --no-install   # 只出 tmp/paper-build/canon/main.pdf
```

脚本与 `build-pdf.sh` 同源（影子目录 + 符号链接 + 复制 `main.tex`/`sections/`），
但**只做一处补丁**：把 `\AtBeginDocument{...}` 外壳去掉并内联等价的 `\setlength`
（tectonic 不允许在正文里再执行 preamble 命令），公式上下距仍是原文的 8pt；
自检包含缺字、报错、页数，以及 PDF 元数据与正文**无身份信息**。
**不要**再补 `\setCJKmonofont`：加了以后附录代码清单行距变小，与 XeLaTeX 结果不一致（当前差异就在这里）。

> 目录必须是 `paper`（`build.sh` 会自动 `cd` 到脚本所在目录）。字体、图片、章节都是相对本目录引用的，
> 换目录编译会因为找不到 `fonts/`、`sections/` 而失败。

---

## 2. 目录结构（每个文件是什么）

```
B_locator/paper/
├── main.tex            # ★ 主文件：论文信息（\title 等）+ 全部排版/字体设置；正文用 \input 引入
├── sections/           # ★ 论文正文，按章节拆分（人工改内容只需动这里）
│   ├── 00-abstract.tex     摘要 + 关键词（≤1 页，无需英文）
│   ├── 01-restate.tex      一、问题重述
│   ├── 02-analysis.tex     二、问题分析
│   ├── 03-assumptions.tex  三、模型假设
│   ├── 04-symbols.tex      四、符号说明（三线表）
│   ├── 05-model.tex        五、模型建立与求解（5.1~5.4 对应问题一~四）★ 篇幅最大
│   ├── 06-evaluation.tex   六、模型评价与改进
│   ├── 07-references.tex   七、参考文献
│   └── 08-appendix.tex     附录：支撑材料文件列表 + 源程序
├── figures/            # 论文插图（png）+ 其用法说明，见 figures/README.md
├── fonts/              # 中文字体 simsun.ttc（宋体）/ simkai.ttf（楷体）—— 模板依赖，勿删勿改名
├── code/               # 附录 B 引用的问题一源码副本（与 Q1/ 下同名文件一致）+ main.py（问题三、四）
├── cumcmthesis.cls     # 竞赛论文模板类（只改过两处字体路径，其余勿动）
├── FORMAT-GUIDE.md     # 格式红线与写作约定（改内容前建议先读第 3 节以外的部分）
├── build.sh            # 一键编译/自检/清理脚本
├── main.pdf            # 编译产物（同时是交付文件）
└── 纸质版/承诺书与编号页.tex   # 打印版承诺书+编号页，电子版不使用
```

问题一、问题二的建模材料与 `paper/` 同级，正文的图与数字都出自这里：

```
B_locator/Q1/           # 问题一（扁平）：p1_intersection.py（求解）、p1_experiments.py（算例生成+四组扫描）、
                        #   p1_selftest.py（自检）、4 个插图脚本、p1_case*.csv 算例、p1_*.json 结果、7 张 png
B_locator/Q2/           # 问题二：src/q2_solution.py（求解）、figures/（两张插图脚本）、
                        #         src/results/q2_summary.json（正文表 3 的数值来源）
```

---

## 3. 改论文去哪改（论文结构 ↔ 源文件对照）

| 论文里看到的内容 | 打开这个文件 | 备注 |
|---|---|---|
| 标题、摘要、关键词 | `sections/00-abstract.tex` | 论文标题在 `main.tex` 的 `\title{...}`；摘要开头/结尾两段留待四问齐备后再写 |
| 一、问题背景与重述 | `sections/01-restate.tex` | 1.1 背景（描述性语言）/ 1.2 重述（不抄题干数据） |
| 二、问题分析 | `sections/02-analysis.tex` | 逐问分小节，每节只讲“考虑什么、建什么模型、为何这样选” |
| 三、模型假设 | `sections/03-assumptions.tex` | |
| 四、符号说明（表 1） | `sections/04-symbols.tex` | 三线表 |
| 五、5.1 问题一：建模思路 | `sections/05-model.tex` 第 8 行起 | 已定稿 |
| 　  5.1.2 模型建立（式 1~3、**图 1** 角楔交会示意） | `sections/05-model.tex` 第 9~55 行 | 图在 `figures/multi_sensor_wedge_diagram.png`（`.62\textwidth`） |
| 　  5.1.3 模型求解算法（**图 2** 流程图） | `sections/05-model.tex` 第 57~93 行 | 图在 `figures/p1-algorithm-flow.png`（`.61\textwidth`） |
| 　  5.1.4 求解结果与分析（**表 2**、**图 3**） | `sections/05-model.tex` 第 95~142 行 | 图在 `figures/p1-coverage-contrast.png` |
| 　  5.2 问题二（式 4~21、**图 4**、**图 5**、**表 3**） | `sections/05-model.tex` 第 144 行起 | 已定稿；图在 `figures/p2-wedge-geometry.png`、`figures/p2-expected-diameter.png` |
| 　  5.3 问题三 | `sections/05-model.tex` 第 388 行起 | **待填充** |
| 　  5.4 问题四 | `sections/05-model.tex` 第 396 行起 | **待填充** |
| 六、模型评价与改进 | `sections/06-evaluation.tex` | **待填充** |
| 七、参考文献 | `sections/07-references.tex` | |
| 附录 A 文件列表 / 附录 B、C 源程序 | `sections/08-appendix.tex` | 附录 A、B、C 已写，附录 D（问题三、四主程序）待补 |
| 页边距、行距、标题字体、图表题注字体 | `main.tex` 顶部「排版紧凑化」块 | 见第 6 节 |

---

## 4. 可以改 vs 不要动

**可以放心改**
- `sections/*.tex` 里的正文文字、公式、表格、图题；
- `main.tex` 里的论文信息：`\title{...}`、`\tihao`、日期等；
- `figures/` 里的图片（新增图放在这里，用英文名，如 `p3-flow.png`）。

**不要动（一动排版就变或直接编译失败）**
- `cumcmthesis.cls`、`fonts/`：模板与字体，路径写在模板里；
- `main.tex` 顶部「排版紧凑化」整块：标题黑体、图表题注宋体、中文字体统一都在这里，
  已在全篇生效，**不要在各节里再设字体或行距**；
- `build.sh`、`figures/`、`sections/`、`code/` 的**文件名**（`main.tex` 与附录按名字引用）。

---

## 5. 还没写的地方（9 处 `【待填充：…】`）

在 `paper/` 目录下用一条命令列出最新清单：

```bash
grep -rn "待填充" sections/
```

当前清单（文件:行）：

| 文件 | 待写内容 |
|---|---|
| `00-abstract.tex` | 开头总述、问题三/四的结论句（各留 3~4 行版面）、结尾总评 |
| `02-analysis.tex` | 问题三、四的补充分析 |
| `05-model.tex` | 5.3 问题三：思路 / 模型 / 结果 |
| `05-model.tex` | 5.4 问题四：思路 / 模型 / 结果 |
| `06-evaluation.tex` | 灵敏度分析 / 优点 / 缺点 / 改进方向 |
| `07-references.tex` | 参考文献条目 |
| `08-appendix.tex` | 附录 D：问题三、四主程序 |

占位文字用 `\textrm{【待填充：…】}` 包裹是有意为之（保证占位也按正文字体显示），替换时整块删掉即可。
问题三、四的具体算法一律留空，**不要按论文里残留的提示去预设方法**；摘要的**开头总述与结尾
总评**必须等四问齐备后再写，否则会把摘要写成只讲问题一的摘要。

> 问题二已定稿，其数值口径与自检见 `../Q2/src/q2_solution.py`（运行后刷新
> `../Q2/src/results/q2_summary.json`）；正文表 3、图 5 的数字与之一一对应。

---

## 6. 字体与格式现状（已定稿，改文字不会破坏）

全部排版覆盖集中在 `main.tex` 顶部，按需在那一处微调：

| 项目 | 现状 |
|---|---|
| 中文正文字体 | `fonts/simsun.ttc`（宋体），**全篇只有这一种宋体** |
| 一级/二级/三级标题 | 黑体（`\heiti`）+ 编号数字加粗 |
| 论文标题、「摘要」二字 | 黑体 |
| 图题/表题 | 宋体小四、不加粗（与正文同字重） |
| 正文行距 | 1.25（模板默认 1.38） |
| 三线表行距 / 列表间距 / 公式上下距 | 1.0 / 0 / 8pt |
| 图 1 宽度 | `.62\textwidth`（`multi_sensor_wedge_diagram.png`，2004×2126 px） |
| 图 2 宽度 | `.61\textwidth`（`p1-algorithm-flow.png`，277.8×167.1 pt 设计、1:1 插入） |
| 图 3 宽度 | `.88\textwidth`（`p1-coverage-contrast.png`，(a)(b) 双面板） |

**四条容易踩的坑**（都已在全篇处理，手改时别破坏）：
1. **缺字方框**：`①②③`、`Ⅰ Ⅱ Ⅲ`、全角字母数字会被交给 Times New Roman，显示成方框。
   用 `(1)(2)(3)`、`I/II/III`、半角写法替代；`build.sh` 会自检 `Missing character`。
2. **不要在正文里用 Markdown 语法**：`**加粗**`、`#` 标题、`-` 列表在 LaTeX 里会**原样打印**。
3. **强调中文一律用黑体**：写成 `{\heiti 关键词}\songti`——末尾的 `\songti` 必须写，
   把字体切回宋体，否则该处之后的文字会全部变成黑体。例：`{\heiti 针对问题一}\songti，……`。
   不要用 `\textbf`（宋体伪粗，与全篇黑体强调不一致）。
4. **不要再引入第二种宋体**：`\songti`、正文、题注都已统一到 `fonts/simsun.ttc`，
   新写内容不要加 `\setCJKfamilyfont` 之类的字体声明。

---

## 7. 图从哪来 / 怎么重新生成

- 图 1（多检测点角楔交会定位示意）由 `../Q1/illustration_plot_Q1.py` 生成，为按真实
  $\varepsilon=1^\circ$ 绘制的示意图，含区域局部放大，不依赖数值。
- 图 2（算法流程图）由 `../Q1/make_p1_flowchart.py` 生成；图 3（覆盖判定对照）由
  `../Q1/make_p1_figures.py` 生成，数据来自算例 `../Q1/p1_case01~05.csv`，由
  `../Q1/p1_intersection.py` 求解（数值汇总见 `../Q1/p1_summary.json`）。
- 图 4（两探测束交会与定位区域直径）由 `../Q2/figures/make_q2_wedge_figure.py` 生成，为示意
  构图（半张角放大到 $2^\circ$），不依赖数值；图 5（期望直径等值图 + 候选区域）由
  `../Q2/figures/make_q2_figures.py` 生成，数值来自 `../Q2/src/q2_solution.py`。
- `p1-wedge-intersection.png`（**备选图，正文未引用**）由 `../Q1/make_p1_wedge_figure.py`
  生成：(a) 用示意构图（两站分居两侧、半张角按 5:1 放大）画“角楔 → 交集多边形 → 直径测量”，
  (b) 用真实算例 $A_2$ 画覆盖失效；脚本末尾带断言（四顶点必须共圆、直径必须等于 $2R$）。
  若将来要用它替 5.1.2 节的文字描述，把它插进该节并调整图号即可；当前正文不使用。
- 重新生成需要 Python + matplotlib + numpy；本机已有隔离环境（仓库根目录 `tmp/venv`）：
  ```bash
  cd /path/to/repo
  MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q1/make_p1_wedge_figure.py
  MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q1/make_p1_flowchart.py
  MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q1/make_p1_figures.py
  MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q2/src/q2_solution.py
  MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q2/figures/make_q2_figures.py
  MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q2/figures/make_q2_wedge_figure.py
  ```
- 只想改论文文字时**完全不需要** Python，改 `sections/*.tex` 后重新编译即可。
- 仓库根的 `tmp/` 是本机编译/验证工具链（venv、tectonic、缓存，约 390MB，已在 `.gitignore` 中）；
  删除它不影响论文与手动编译，只影响本机重新生成插图。

---

## 8. 竞赛格式要点（已配置，仅供核对）

| 要点 | 处理 |
|---|---|
| 电子版第一页 = 摘要页 | `\documentclass[withoutpreface]{cumcmthesis}` |
| 承诺书 / 编号页不得出现 | `withoutpreface` 已去除（纸质版另见 `纸质版/`） |
| 摘要 ≤1 页、无需英文 | 见 `00-abstract.tex`（开头总述、问题二~四、结尾总评三段待补） |
| 正文不要目录、≤30 页 | 未加目录，当前 11 页 |
| 附录含支撑材料清单 + 全部源程序 | 见 `08-appendix.tex` |
| 全篇匿名 | 不得出现学校/姓名/队号等身份信息 |
| 电子版单个 PDF ≤20MB、不压缩 | 当前约 0.6MB |

更细的写作约定（三线表、公式与交叉引用、参考文献写法、`lstlisting` 用法等）见 **`FORMAT-GUIDE.md`**。
