# 2026 全国大学生数学建模竞赛 B 题：测向有界误差下的干扰源定位与清除

本仓库是 2026 年 B 题的完整参赛工程：电子版论文、四问的求解与复现代码、冻结的实验数据和逐动作证据。**竞赛已结束，仓库转为公开存档**，用于结果复核与后续参考，不再作为赛前工作区继续开发。

论文只有一个算法维护位置，即 `attachments/Q1` 至 `Q4` 的 `code/`；`paper/` 只负责排版与图表引用，不放代码副本。

## 题目与结论概览

题面：在测向误差有界、干扰源数量与发射朝向均未知的条件下，用移动探测平台完成快速定位与清除。四问层层递进，共同结论是**把保守几何约束贯穿定位、清除与退出判断，使每一步决策都有可核验的空间依据**。

| 问题 | 模型 | 实验与核验规模 | 代码 |
| --- | --- | --- | --- |
| 一 | 有界区间角楔交会模型 | 5 组构造算例 + 4 组固定种子扫描，48,000 个构型完整重跑 | [Q1](attachments/Q1/README.md) |
| 二 | 期望定位区域直径布点模型 | 36,960 个理论网格点按公式独立复算，11,168 行数值网格完整重跑 | [Q2](attachments/Q2/README.md) |
| 三 | 联合覆盖、定位与清除模型 | 120 组场景 × 5 策略 + 20 组 × 4 项消融，680 次运行 | [Q3](attachments/Q3/README.md) |
| 四 | 连续位置与朝向覆盖模型 | 60 组场景 × 3 策略 + 10 组 × 2 项消融 + 3 项快速策略，230 次运行 | [Q4](attachments/Q4/README.md) |

问题一说明「以区域直径为直径的圆并不总能覆盖定位区域」（五组算例直径 10.59～25.64 m，两组越界顶点超半径约 10.6%），为后续采用保守包围半径提供依据。问题三最终策略在随机 50 组上完整任务时间均值 3067 s，较同具连续证书的前代策略减少 8.4%。问题四 60 组场景全部清除并认证，退出每源均值较 25 站联合策略降低。三次正式测试中，问题三清除 14～16 个源、每源平均定位清除时间 175.522～235.986 s，问题四清除 10～16 个源、344.622～564.812 s。

## 仓库结构

```text
paper/                        论文工程：LaTeX 源、已用图件、字体、编译与维护工具
  main.pdf                    电子版论文，50 页，首页即摘要专用页
  main.tex                    主文件，正文各章由 sections/ 载入
  sections/                   摘要、重述、建模、求解、评价、参考文献与附录
  figures/                    正文已用的 16 幅图件
  fonts/                      编译论文所需的中文字体
  reference/                  B 题题面、官方附件与格式规范（仅存档，不进交付包）
  FORMAT-GUIDE.md             排版约定
  build.sh                    编译入口，优先 XeLaTeX，否则 Tectonic
  maintain.py                 清单刷新、校验与评审包导出
attachments/                  评审附件：四问各自独立、可离线复现
  Q1/ … Q4/                   同结构：code/ data/ results/ figures/ + README、DATA_SOURCES
  formal-tests/               六份正式测试原始 .jlog、results.csv 与计时口径说明
  requirements.txt            Python 依赖
  SHA256SUMS.txt              交付包逐文件 SHA256
  VALIDATION.md               全量重跑与核验范围
  AI工具使用详情.pdf           AI 使用目的、过程与人工核验说明
B_locator/                    早期论文审查报告，历史存档，不是运行依赖
.gitattributes                固定 attachments/ 的换行符，保证跨平台校验一致
```

附件按问题分册，每册都自带入口，互不依赖：

```text
attachments/Q3/
  reproduce.py                唯一正式入口：审计 / 试跑 / 完整重跑 / 重绘
  code/                       算法、策略、制表与制图程序
  data/                       题设常数、构造输入与冻结的网格/场景
  results/                    保存的统计结果、动作账本与覆盖证书
  results/traces/             问题三、四的逐动作日志（问题一、二无此项）
  figures/                    正文图件
  README.md                   运行方式、输出清单与代码索引
  DATA_SOURCES.md             每个数字对应到论文哪张图表
  SOURCE_MANIFEST.json        交付文件的 SHA256、来源与路径适配记录
```

## 快速开始

### 1. 直接看论文

打开 `paper/main.pdf`。参考文献结束于第 30 页，附录从第 31 页开始。

### 2. 复现附件结果

需要 Python 3.12 或更新版本。计算、审计与制图全部离线完成，不需要原研究工程或在线模拟器。

```bash
cd attachments
python3 -m pip install -r requirements.txt

# 从保存的动作与输入重建论文统计，不重跑策略
python3 -B Q1/reproduce.py --audit-only

# 小规模试跑 / 完整重跑 / 按需重绘图件
python3 -B Q3/reproduce.py --smoke   --out ../reproduction-q3-smoke
python3 -B Q3/reproduce.py --full    --out ../reproduction-q3-full
python3 -B Q3/reproduce.py --figures --font /path/to/chinese-font.ttf --out ../reproduction-q3-figures
```

四种模式对 Q1～Q4 一致，把 `Q3` 换成其它题号即可。**所有新输出必须落在附件目录之外**，避免覆盖冻结证据；`--dev` 开发模式只用于新实验，不能用来证明论文中已有的数据。

完整重跑的计算量远大于试跑，`--audit-only` 与 `--smoke` 都不能替代它。问题二的 `.wl` 理论程序需要 Mathematica，Python 侧已按同一求积公式独立完成核验。

### 3. 重新编译论文

```bash
bash paper/build.sh
```

在仓库根目录或 `paper/` 内执行均可。优先使用 XeLaTeX，否则回退到 Tectonic。附录直接载入 `attachments/Qn/code/` 的实际源码，所以编译时 `paper/` 与 `attachments/` 必须保持同级。

### 4. 刷新与核对交付清单

```bash
python3 paper/maintain.py refresh   # 记录当前文件状态与哈希
python3 paper/maintain.py check     # 核对四问清单、交付哈希与论文插图是否同步
python3 paper/maintain.py pack      # 导出 attachments/reviewer-attachments.zip
```

`refresh` 只记录当前文件状态，不会把改动后的代码认证为历史算法。改动算法或图件后应先更新结果、来源说明与论文图表，再运行 `refresh` 并另行独立审计；不要只改论文里的数字。

## 数据与文件完整性

- 每题 `SOURCE_MANIFEST.json` 记录该题交付文件的 SHA256、来源路径与适配说明，并区分**历史来源哈希**与**当前交付哈希**；`attachments/SHA256SUMS.txt` 提供整包逐文件校验值。当前共核验 1070 份清单文件。
- `.gitattributes` 中的 `attachments/** -text` 禁止 Git 做换行符转换，保证任意系统检出后字节级校验一致。
- 正式测试的六份原始 `.jlog` 保留官方导出文件名和内容，集中存放于 `attachments/formal-tests/`；加密行为载荷由官方工具验核，离线入口不解密也不重跑。程序运行时间按系统历史记录的结束时间减开始时间计算（问题三 6、11、5 s，问题四 8、7、6 s，时间戳显示精度 1 s）。
- 失败与漏清实验均予保留，没有通过放宽阈值掩盖失败。

## 未随仓库发布的文件

以下内容被有意排除或已改为本地生成，`.gitignore` 已覆盖：

- **共享制图字体**（原 `attachments/fonts/simsun.ttc`）：为控制支撑材料体积并在公开仓库中避免分发第三方字体而移出。计算、审计与完整重跑都不需要字体，只有 `--figures` 制图需要用 `--font /path/to/chinese-font.ttf` 显式指定。各题清单中仍保留其 SHA256，作为当初制图所用字体的记录。`paper/fonts/` 为编译论文所需予以保留。
- **与正文 PDF 重复的 PNG**：移出交付包，保留 PDF 正文图与全部动作证据，随时可用 `--figures` 重绘；被移除文件的哈希记录在各题清单的 `previous_files_not_in_current_delivery` 中。
- **构建临时产物** `_build_deps/`、`_build_tmp/`：PDF 校对用的离线依赖解包与 wheel、日志等，曾在提交 `de7512b` 中误入库，现已从版本控制移除并加入 `.gitignore`（仍可从该提交找回）。
- **本地环境与新实验输出**：`paper/.local/`、`attachments/.local/`、`tmp/`、`simulator/`、`B_locator/out` 等。

## 已知限制

- 完整重跑环境为 macOS arm64、Python 3.12.14、NumPy 2.3.5，制图使用 Matplotlib 3.11.2。跨平台数值运算可能影响启发式分支，因此**不承诺不同平台的逐动作结果一致**；冻结动作重放与全部统计量一致。
- 问题二的理论网格完整导出依赖 Mathematica；正式 `.jlog` 的公开头部与文件完整性可离线验证，但清除数与计时由参赛队实际测试提供。
- 问题三的图族插值检查使用与图族相同的接收半径加权先验，策略实际使用的局部面积权重保持原定义，论文中已注明该近似。

## 历史版本

清理前的完整工程保留在 Git 提交 `15bea8b`（"整理评审包"）。旧 `B_locator/` 研究工程、A/C 题材料、历史探索与多层归档均可从该提交恢复；各题清单中的 `historical_source_paths` 也指向该提交，属于来源记录而非运行依赖。

## 使用与权利

仓库未附开源许可证。论文、代码与实验数据为参赛作品，供结果复核与学习参考；题面、官方附件、格式规范、竞赛模板与中文字体的权利归各自权利人，不在本仓库授权范围内。
