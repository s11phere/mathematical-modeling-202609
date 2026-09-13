# 论文修改入口

在仓库根目录执行 `bash paper/build.sh`，或在本目录执行 `bash build.sh`。优先使用 XeLaTeX，否则使用 Tectonic；本机 Tectonic 的离线缓存位于被 Git 忽略的 `.local/tectonic-cache/`。检查无缺字、编译错误和失效引用后才替换 `main.pdf`，编译日志写入系统临时目录。

## 修改位置

| 内容 | 位置 |
| --- | --- |
| 摘要、问题重述、建模分析、假设、符号表 | `sections/00-abstract.tex` 至 `04-symbols.tex`；摘要引用问题三、四摘要片段 |
| 问题一、二模型 | `sections/05-model.tex` |
| 问题三、四模型 | `sections/q3-model.tex`、`q4-model.tex` |
| 评价、文献、统一附件说明 | `sections/06-evaluation.tex` 至 `08-appendix.tex` |
| 核心代码与分题参数、统计附录 | `sections/core-code.tex`、`q3-appendix.tex`、`q4-appendix.tex` |
| 数值与表格行 | `sections/q3-*-rows.tex`、`q4-*-rows.tex`、`q3-numbers.tex`、`q4-numbers.tex` |
| 三次正式测试 | 两题 `q3-model.tex`、`q4-model.tex` 末尾；来源为 `../attachments/formal-tests/results.csv` |
| 正文图片 | `figures/`，只保留已使用的16幅图 |
| 全篇字体与间距 | `main.tex`；详细约定见 `FORMAT-GUIDE.md` |

附录 B 每题选取一段核心代码，附录 C 统一参数、概率与复现数据。附录直接载入 `../attachments/Qn/code/` 的实际源码，编译时保留 `paper/` 与 `attachments/` 同级。算法、实验、制图工具均在附件中维护，本目录不再存放代码副本或旧版全文代码清单。

正式测试原始日志及汇总统一存于 `../attachments/formal-tests/`，附录 A 列出六个原始日志名并说明计时来源。两张表按题干要求列四项指标：平均定位清除时间按测试者提供的总时间除以清除数计算，程序运行时间按系统历史记录的结束时间减开始时间计算，时间戳显示精度为 1 s。后续修订时同步 CSV、两张论文表格及来源说明。

`reference/` 只保留 B 题题面、两份官方附件及论文格式规范，用于后续核对题设和接口；不进入电子论文或评审压缩包。纸质承诺书模板和其他题目资料可从 Git 清理前提交 `15bea8b` 找回。

`maintain.py` 提供当前文件清单核验、更新和评审包导出，命令见根目录 README。它不运行算法、不修改冻结实验数据。尚在修改期，请保留全部 LaTeX、字体、已用图件及源码依赖；最后提交仅取 `main.pdf`。

AI 声明位于 `sections/06-ai-statement.tex`，在参考文献之前。`tools/build_ai_usage.py` 生成附件根目录的 `AI工具使用详情.pdf`，需 ReportLab。问题三、四全部图表与统计已切换至本次完整重跑；制表器不再生成摘要文案。
