# 论文写作格式规范

本文件是 B 题论文工程的**格式与写作约定**。任何往 `sections/` 里填充内容的人（或 Agent），
动手前务必通读本文，避免踩格式坑或破坏已配置好的排版。

> 首次上手请先看 **`README.md`**（怎么编译、改哪里、字体与格式现状、待填充清单）。

---

## 0. 一句话原则

- **只改 `sections/` 各文件的内容**；不要动 `main.tex`、`cumcmthesis.cls` 里的排版
  设置（除非明确要调整间距/字体）。
- 占位标记 `【待填充：…】` 就是待替换处，成文时**删除或替换为正文**，别残留。
- 每次改完，在 `paper/` 目录运行 `bash build.sh` 编译自检：**必须无报错、无 `Missing
  character`（缺字方框）**。

## 1. 文件分工（改哪、干什么）

| 文件 | 内容 | 状态 |
|---|---|---|
| `sections/00-abstract.tex` | 摘要 + 关键词（≤1 页、无需英文） | 问题一、二已写；问题三、四待填充（各留 3~4 行） |
| `sections/01-restate.tex` | 一、问题背景与重述（1.1 背景 / 1.2 重述） | 已完成 |
| `sections/02-analysis.tex` | 二、问题分析（总体 + 2.1~2.4 逐问） | 总体与问题一、二已写；问题三、四待补充 |
| `sections/03-assumptions.tex` | 三、模型假设（条目式） | 已完成 |
| `sections/04-symbols.tex` | 四、符号说明（三线表，表 1） | 已含问题二的 $S_2,\theta_2,x_{max},E[D]$ |
| `sections/05-model.tex` | 五、模型建立与求解（5.1~5.4 对应问题一~四） | **5.1、5.2 已定稿**，5.3~5.4 待填充（核心） |
| `sections/06-evaluation.tex` | 六、模型评价与改进（灵敏度/优缺点） | 待填充 |
| `sections/07-references.tex` | 七、参考文献 | 待填充 |
| `sections/08-appendix.tex` | 附录：支撑材料文件列表 + 源程序 | 附录 A/B/C 已写，附录 D（问题三、四主程序）待补 |
| `main.tex` | 主文件、论文信息、**全部排版覆盖**（含标题/题注字体、中文字体统一） | **勿改**（可改 `\title` 等论文信息） |

## 2. 格式红线（违反可能退稿 / 扣分）

1. **电子版首页必须是摘要页**，不得出现承诺书/编号页（已由 `main.tex` 的
   `withoutpreface` 处理，勿改动）。
2. **全篇匿名**：摘要、正文、附录**不得出现**学校、姓名、报名队号、赛区等身份信息。
3. **摘要 ≤ 1 页、无需英文**。
4. **正文不要目录、不超过 30 页**。
5. **附录必须包含**「支撑材料文件列表」+ 建模所用全部可运行源程序（框架已搭好
   `08-appendix.tex`，成文时如实填）。
6. 电子版为**单个 PDF、≤ 20MB、不压缩**。

## 3. 技术性排版注意点（重点，易踩坑）

### 3.1 中西文字符边界 —— 缺字变方框
XeLaTeX 下，以下字符会被交给**西文字体 Times New Roman**渲染，而它没有对应字形，
会显示成方框 `￿`（编译日志报 `Missing character`）：

- ❌ 带圈数字 `①②③…⑩`
- ❌ 罗马数字 `Ⅰ Ⅱ Ⅲ Ⅳ`
- ❌ 全角字母/数字 `Ａ Ｂ ａ ｂ １ ２`

**替代**：用 `(1)(2)(3)`、`I/II/III`、半角 `A/a/1`。写完用 `build.sh` 自检，看到
`Missing character` 就按提示替换。

### 3.2 中文加粗 / 中文字体 / 别写 Markdown
- ✅ **强调中文一律用黑体**：`{\heiti 关键词}\songti`。末尾的 `\songti` 必须写——`\heiti`
  是声明式命令，不写回来，**该处之后的文字会全部变成黑体**。示例：
  `{\heiti 针对问题一}\songti，建立{\heiti 有界区间角楔交会模型}\songti：……`
- ❌ 不要用 `\textbf{中文}`：那是宋体伪粗，与全篇黑体强调不一致（模板虽开启了
  `AutoFakeBold`，但论文的强调体例统一为黑体）。
- ❌ 不要写 `\heiti{文字}`（会被当成 `\heiti` + 普通文本 `{文字}`，多出花括号）
- ❌ **不要用 Markdown 语法**（`**加粗**`、`# 标题`、`- 列表`），LaTeX 会原样打印出来
- ❌ 不要新增任何字体声明（`\setCJKmainfont`、`\setCJKfamilyfont`、`\songti` 之外的字体）：
  全篇中文字体已统一，见第 4 节

### 3.3 表格
- 一律**三线表**：`\toprule` / `\midrule` / `\bottomrule`（booktabs，已加载）。
- 表格行距已全局收紧为 1.0，**不要再在表格内** `\renewcommand{\arraystretch}`。
- 表题 `\caption{...}` 放在 `\begin{tabular}` **之前**（模板已配 position=top）。
- 示例：
  ```latex
  \begin{table}[!htbp]
      \caption{表题}\label{tab:xx}
      \centering
      \begin{tabular}{ll}
          \toprule
          列1 & 列2 \\ \midrule
          值1 & 值2 \\
          \bottomrule
      \end{tabular}
  \end{table}
  ```

### 3.4 图片
- 格式 `jpg/png/pdf`（**勿用 bmp**）；英文命名，放 `figures/`（现有 5 张图的分工见
  `figures/README.md`）。
- 图题 `\caption{...}` 在图片**下方**（模板已配 position=bottom）。
  ```latex
  \begin{figure}[!htbp]
      \centering
      \includegraphics[width=.6\textwidth]{fig-name}
      \caption{图题}\label{fig:xx}
  \end{figure}
  ```

### 3.5 公式与交叉引用
- 行内 `$...$`；带编号行间公式用 `\begin{equation}...\label{eq:xx}\end{equation}`。
- 引用一律用 `\cref{...}`（已配 cleveref，自动生成「式(1)」「图 1」「表 1」）：
  `\cref{eq:xx}`、`\cref{fig:xx}`、`\cref{tab:xx}`。**不要手写**“式(1)/图1/表1”。
- 中文在公式内用 `\text{中文}`。

### 3.6 参考文献
- 用 `thebibliography` 环境；**不要自己写** `\section{参考文献}`（环境自带标题，
  再写会重复）。
  ```latex
  \begin{thebibliography}{9}
      \bibitem{key} 作者. 题目[J]. 期刊, 年, 卷(期): 页码.
  \end{thebibliography}
  ```
- 正文引用 `\cite{key}`。

### 3.7 宏包
- 模板已加载 `amsmath`、`booktabs`、`listings`、`caption`、`graphicx`、`enumitem`
  等，**不要重复 `\usepackage`**（会报错）。确需新宏包，先确认未加载，再加到
  `main.tex`。

### 3.8 附录源程序
- 用 `lstlisting`（已加载）：`\begin{lstlisting}[language=python, caption={...}]…\end{lstlisting}`，
  语言可设 `python/matlab/c`。
- 支撑材料文件列表（`08-appendix.tex` 里的编号清单）**必须与 `Q1/`、`code/`、`figures/` 实际文件
  一一对应**（问题一已扁平化为 `Q1/` 下的 `.py` 与 `.png`，不再有子目录）。

## 4. 已配置的排版与字体（勿在各节重复设置）

所有排版覆盖集中在 `main.tex` 顶部「排版紧凑化」块，写正文时**不要**再
`\setlength`/`\setlist`/设字体。当前参数：

| 项 | 值 |
|---|---|
| 中文正文字体 | `fonts/simsun.ttc`（宋体）；全篇只有这一种宋体 |
| 一/二/三级标题 | 黑体 `\heiti` + 编号数字加粗 |
| 论文标题、「摘要」二字 | 黑体 |
| 图题/表题 | 宋体小四、**不加粗**（与正文同字重） |
| 正文行距 | 1.25（模板默认 1.38） |
| 三线表行距 | 1.0 |
| 列表顶部间距 | 0 |
| 章节标题前后距 | 已收紧（section/subsection/subsubsection） |
| 行间公式上下距 | 8pt |
| 图表标题（caption）间距 | above 4pt / below 2pt |
| 浮动体与正文间距 | textfloatsep 8pt / floatsep 6pt / intextsep 6pt |

如需微调，改 `main.tex` 该块内带注释的数值即可，不要另起炉灶。

## 5. 章节写作约定

- 问题 1~4（`05-model.tex` 的 5.1~5.4）按「模型建立与公式推导 → 求解算法 → 结果分析与结论」组织。
  建模思路集中在第二章问题分析，第五章不再单设“建模思路”小节。
- **摘要**（`00-abstract.tex`）用「总分总」：开头总述（背景 + 总体模型/算法体系）→
  针对问题一~四（每问只强调 1~2 个关键词，讲清“遇到什么问题、用什么模型/算法、得到什么
  结果”，不要堆细节、不要写公式）→ 结尾总评（模型的优缺点与改进方向）。
  **开头总述与结尾总评必须等四问齐备后再写**：开头只谈某一问，摘要就写成了单问摘要；
  结尾的优缺点也要覆盖四问合起来的模型体系。现在这两段用 `\textrm{【待填充：…】}` 占位。
  **整篇摘要连同待填充段落必须只占一页**，按文件顶部注释的行数预算写，超了先压缩正文细节。
- **问题背景**（1.1）用自己的语言描述问题，不用数学定义、不罗列题干数据；
  **问题重述**（1.2）把官方的严谨表述转成评委易懂的描述性语言，也不要抄题干数据。
- **问题分析**（第二章）逐问分小节，每节只讲三件事：考虑到了什么、要建立什么模型、
  为什么采用最终这一做法；推导与结论细节留给第五章。
- 尚未完成的问（问题三、四与第六章）一律保留 `\textrm{【待填充：…】}` 中性占位，
  **不要预设算法、不要写未经计算的结论**。
- 已完成的问中的每个数字都要能追溯到脚本：问题一对应
  `../Q1/p1_intersection.py`（求解）与 `../Q1/p1_experiments.py`（算例生成 + 四组随机扫描），
  数值汇总在 `../Q1/results/p1_summary.json`，附录 B 粘贴的代码必须与 `../Q1/p1_intersection.py`
  逐字节一致；问题二对应 `../Q2/pysimulation/src/p2_grid_expectation.py`、
  `../Q2/pysimulation/out/p2_grid/` 与 `../Q2/MMAcode/` 中的原始程序和数据；
  改数值前先重跑脚本。
- **配图要画“怎么来的”**：图的作用是把公式里的构造画清楚（角楔怎么张开、交集怎么形成、
  直径由哪两点给出、点与点如何对应），而不是把结论多边形再抄一遍；示意图若放大了角度或
  尺量，必须在图题里写明放大倍数与真实值。
- `04-symbols.tex` 的符号须与正文一致；未列出的符号在**首次出现处**说明。
- 结果表/图编号连续、正文有引用（`\cref`）。

## 6. 编译与自检

```bash
cd B_locator/paper
bash build.sh          # XeLaTeX 两遍 + 缺字/错误自检
bash build.sh clean    # 清理编译中间文件
```

Windows/MiKTeX：用编辑器把编译器设为 XeLaTeX，连编两遍（详见 `README.md` 第 1 节）。

自检清单：
1. 编译无报错、无 `Missing character`（方框）。
2. 首页 = 摘要页（无承诺书/编号页/身份信息）。
3. 正文页数 ≤ 30（摘要另算）。
4. 附录含支撑材料文件列表 + 源程序。
5. 最终 PDF ≤ 20MB。
