# 论文填充格式规范（供写作 / 求解 Agent 对接）

本文件是 B 题论文工程的**格式与写作约定**。任何负责往 `sections/` 里填充内容的
Agent，动手前务必通读本文，避免踩格式坑或破坏已配置好的排版。

---

## 0. 一句话原则

- **只改 `sections/` 各文件的内容**；不要动 `main.tex`、`cumcmthesis.cls` 里的排版
  设置（除非明确要调整间距）。
- 占位标记 `【待填充：…】` 就是待替换处，成文时**删除或替换为正文**，别残留。
- 每次改完，在工程根目录运行 `bash build.sh` 编译自检：**必须无报错、无 `Missing
  character`（缺字方框）**。

## 1. 文件分工（改哪、干什么）

| 文件 | 内容 | 状态 |
|---|---|---|
| `sections/00-abstract.tex` | 摘要 + 关键词（≤1 页、无需英文） | 占位，**全文定稿后写** |
| `sections/01-restate.tex` | 一、问题重述（4 问） | 占位 |
| `sections/02-analysis.tex` | 二、问题分析（总体 + 逐问） | 占位 |
| `sections/03-assumptions.tex` | 三、模型假设（条目式） | 占位 |
| `sections/04-symbols.tex` | 四、符号说明（三线表） | 占位 |
| `sections/05-model.tex` | 五、模型建立与求解（5.1~5.4 对应问题 1~4） | 占位，**核心** |
| `sections/06-evaluation.tex` | 六、模型评价与改进（灵敏度/优缺点） | 占位 |
| `sections/07-references.tex` | 七、参考文献 | 占位 |
| `sections/08-appendix.tex` | 附录：支撑材料文件列表 + 源程序 | 占位 |
| `main.tex` | 主文件、论文信息、**全部排版覆盖** | **勿改**（可改 `\title` 等） |

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

### 3.2 中文加粗
- ✅ 强调中文用黑体：`\heiti{关键词}`
- ❌ 不要用 `\textbf{中文}`：宋体无粗体字形，加粗不生效（不会报错但看起来没变化）。

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
- 格式 `jpg/png/pdf`（**勿用 bmp**）；英文命名，放 `figures/`。
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
- 支撑材料文件列表（`08-appendix.tex` 里的表）**必须与 `code/`、`figures/` 实际文件
  一一对应**。

## 4. 已配置的紧凑化排版（勿在各节重复设置）

所有间距覆盖集中在 `main.tex` 顶部「排版紧凑化」块，Agent 写正文时**不要**再
`\setlength`/`\setlist`。当前参数：

| 项 | 值 |
|---|---|
| 正文行距 | 1.25（模板默认 1.38） |
| 三线表行距 | 1.0 |
| 列表顶部间距 | 0 |
| 章节标题前后距 | 已收紧（section/subsection/subsubsection） |
| 行间公式上下距 | 8pt |
| 图表标题（caption）间距 | above 4pt / below 2pt |
| 浮动体与正文间距 | textfloatsep 8pt / floatsep 6pt / intextsep 6pt |

如需微调，改 `main.tex` 该块内带注释的数值即可，不要另起炉灶。

## 5. 章节写作约定

- 问题 1~4（`05-model.tex` 的 5.1~5.4）统一「建模思路 → 模型建立 → 算法/求解 →
  结果分析」子结构。
- `04-symbols.tex` 的符号须与正文一致；未列出的符号在**首次出现处**说明。
- 结果表/图编号连续、正文有引用（`\cref`）。

## 6. 编译与自检

```bash
cd B-paper
bash build.sh      # XeLaTeX 两遍 + 缺字/错误自检
```

自检清单：
1. 编译无报错、无 `Missing character`（方框）。
2. 首页 = 摘要页（无承诺书/编号页/身份信息）。
3. 正文页数 ≤ 30（摘要另算）。
4. 附录含支撑材料文件列表 + 源程序。
5. 最终 PDF ≤ 20MB。
