# B 题论文工程 —— 人工修改 & 手动编译指南

> 题目：**无线电干扰源的快速自动定位与清除模型**（2026 全国大学生数学建模竞赛 B 题）
> 当前状态：**问题一（5.1 节）已定稿**，编译产物 `main.pdf` 共 10 页；
> 问题二~四、模型评价章共 **17 处 `【待填充：…】`** 待补（清单见第 5 节）。
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
├── code/               # 附录引用的源程序（p1_locator.py / main.py）
├── cumcmthesis.cls     # 竞赛论文模板类（只改过两处字体路径，其余勿动）
├── FORMAT-GUIDE.md     # 格式红线与写作约定（改内容前建议先读第 3 节以外的部分）
├── build.sh            # 一键编译/自检/清理脚本
├── main.pdf            # 编译产物（同时是交付文件）
└── 纸质版/承诺书与编号页.tex   # 打印版承诺书+编号页，电子版不使用
```

---

## 3. 改论文去哪改（论文结构 ↔ 源文件对照）

| 论文里看到的内容 | 打开这个文件 | 备注 |
|---|---|---|
| 标题、摘要、关键词 | `sections/00-abstract.tex` | 论文标题在 `main.tex` 的 `\title{...}` |
| 一、问题重述 | `sections/01-restate.tex` | |
| 二、问题分析 | `sections/02-analysis.tex` | |
| 三、模型假设 | `sections/03-assumptions.tex` | |
| 四、符号说明（表 1） | `sections/04-symbols.tex` | 三线表 |
| 五、5.1 问题一：建模思路 | `sections/05-model.tex` 第 8~13 行 | 已定稿 |
| 　  5.1.2 模型建立（式 1~3） | `sections/05-model.tex` 第 14~46 行 | 已定稿 |
| 　  5.1.3 模型求解算法（**图 1** 流程图） | `sections/05-model.tex` 第 47~72 行 | 图在 `figures/p1-algorithm-flow.png` |
| 　  5.1.4 求解结果与分析（**表 2**、**图 2**） | `sections/05-model.tex` 第 73~116 行 | 图在 `figures/p1-coverage-contrast.png` |
| 　  5.2 问题二 | `sections/05-model.tex` 第 117~127 行 | **待填充** |
| 　  5.3 问题三 | `sections/05-model.tex` 第 128~138 行 | **待填充** |
| 　  5.4 问题四 | `sections/05-model.tex` 第 139~147 行 | **待填充** |
| 六、模型评价与改进 | `sections/06-evaluation.tex` | **待填充** |
| 七、参考文献 | `sections/07-references.tex` | |
| 附录 A 文件列表 / 附录 B、C 源程序 | `sections/08-appendix.tex` | 附录 C 待补 |
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

## 5. 还没写的地方（17 处 `【待填充：…】`）

在 `paper/` 目录下用一条命令列出最新清单：

```bash
grep -rn "待填充" sections/
```

当前清单（文件:行）：

| 文件 | 行号 | 待写内容 |
|---|---|---|
| `00-abstract.tex` | 14 / 16 / 18 | 摘要里问题二、三、四的结论句 |
| `02-analysis.tex` | 24 | 问题二、三、四的具体分析 |
| `05-model.tex` | 119 / 122 / 125 | 5.2 问题二：思路 / 模型 / 结果 |
| `05-model.tex` | 130 / 133 / 136 | 5.3 问题三：思路 / 模型 / 结果 |
| `05-model.tex` | 141 / 144 / 147 | 5.4 问题四：思路 / 模型 / 结果 |
| `06-evaluation.tex` | 7 / 14 / 17 / 20 | 灵敏度分析 / 优点 / 缺点 / 改进方向 |
| `07-references.tex` | 10 | 参考文献条目 |
| `08-appendix.tex` | 150 起 | 附录 C：问题三、四主程序 |

占位文字用 `\textrm{【待填充：…】}` 包裹是有意为之（保证占位也按正文字体显示），替换时整块删掉即可。

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
| 图 1 宽度 | `.58\textwidth`（图 1 为 265×171 pt 设计、1:1 插入） |
| 图 2 宽度 | `.88\textwidth` |

**三条容易踩的坑**（都已在全篇处理，手改时别破坏）：
1. **缺字方框**：`①②③`、`Ⅰ Ⅱ Ⅲ`、全角字母数字会被交给 Times New Roman，显示成方框。
   用 `(1)(2)(3)`、`I/II/III`、半角写法替代；`build.sh` 会自检 `Missing character`。
2. **不要再引入第二种宋体**：`\songti`、正文、题注都已统一到 `fonts/simsun.ttc`，
   新写内容不要加 `\setCJKfamilyfont` 之类的字体声明。
3. **中文强调用黑体**：写 `{\heiti 文字}`，不要写 `\textbf{文字}`（宋体没有粗体字形）、
   也不要写 `\heiti{文字}`（`\heiti` 是声明式命令，不接收参数）。

---

## 7. 图从哪来 / 怎么重新生成

- 图 1（算法流程图）、图 2（覆盖判定对照）由 `../Q1/figures/make_p1_figures.py` 与
  `make_p1_flowchart.py` 生成，数据来自 `../Q1/src/p1_solution.py`。
- 重新生成需要 Python + matplotlib + numpy；本机已有隔离环境（仓库根目录 `tmp/venv`）：
  ```bash
  cd /path/to/repo
  MPLCONFIGDIR=$PWD/tmp/mplconfig tmp/venv/bin/python B_locator/Q1/figures/make_p1_flowchart.py
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
| 摘要 ≤1 页、无需英文 | 见 `00-abstract.tex` |
| 正文不要目录、≤30 页 | 未加目录，当前 10 页 |
| 附录含支撑材料清单 + 全部源程序 | 见 `08-appendix.tex` |
| 全篇匿名 | 不得出现学校/姓名/队号等身份信息 |
| 电子版单个 PDF ≤20MB、不压缩 | 当前约 0.6MB |

更细的写作约定（三线表、公式与交叉引用、参考文献写法、`lstlisting` 用法等）见 **`FORMAT-GUIDE.md`**。
