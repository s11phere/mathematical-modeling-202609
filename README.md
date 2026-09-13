# B题论文与评审附件

当前为可继续修改的赛前工作版，主分支只维护 `paper/` 和 `attachments/`。算法的唯一维护位置是 `attachments/Q1` 至 `Q4` 的 `code/`；不再保留另一套研究工程。

```text
paper/                         论文 LaTeX、已用图片、字体、编译与维护工具
  main.pdf                     当前电子论文
  sections/                    摘要、正文、表格与附录
  reference/                   B题题面、接口说明、官方格式规范
attachments/                   可编辑、可独立运行的评审材料
  Q1/ Q2/ Q3/ Q4/              同结构的问题代码、数据、结果和图册
  formal-tests/                六份正式测试原始日志、结果汇总与来源说明
  fonts/                       共用制图字体
  reviewer-attachments.zip     由当前材料导出的评审包（生成文件，不入 Git）
```

## 日常修改

- 修改论文：编辑 `paper/sections/`，运行 `bash paper/build.sh`。排版约定见 `paper/FORMAT-GUIDE.md`。
- 修改算法：编辑对应 `attachments/Qn/code/`，使用 `reproduce.py --dev --smoke` 或 `--dev --full` 在新目录试跑。开发模式只用于新实验，不能用来证明原论文数据。
- 核对原实验：运行各题 `reproduce.py --audit-only`。普通模式检查清单及历史来源，保留旧数据，便于对照。
- 修改图件：用各题 `--figures` 生成到新目录；核对后同步相应 `attachments/Qn/figures/` 和 `paper/figures/`。问题三、四的论文目录仅留 PDF，附件另保留 PNG。

本机已保留被 Git 忽略的 Python 环境和离线 LaTeX 缓存。可直接运行：

```bash
attachments/.local/venv/bin/python -B attachments/Q1/reproduce.py --dev --smoke --out attachments/.local/q1-smoke
bash paper/build.sh
```

新机器安装 Python 3.12 或更新版本、XeLaTeX 或 Tectonic，再安装 `attachments/requirements.txt` 中的依赖。复现方法与已验证范围见各题 README。新实验集中存入 `attachments/.local/`，不会被打包或提交。

## 更新评审包

```bash
# 审核修改后更新当前文件校验值；不改变历史数据和来源哈希。
python3 paper/maintain.py refresh
# 核对四题文件清单、总哈希，以及论文和附件图片是否同步。
python3 paper/maintain.py check
# 导出附件；不包含 Python 环境、缓存或旧压缩包。
python3 paper/maintain.py pack
```

`refresh` 只记录当前文件状态，不会把修改后的代码认证为历史算法。采用新实验前，应更新对应结果、来源说明、补充图册和论文图表，再进行独立审计；不要只改论文中的数字。问题四跨平台路径差异仍保留在其复现说明中。

## 交付前

最终电子材料取 `paper/main.pdf` 和 `attachments/reviewer-attachments.zip`，不用提交整个仓库。现在保留 LaTeX、制图和算法源程序便于修改；交付时论文目录只需 PDF，评审包仍须包含可复现源码。六次正式测试的原始日志和结果集中于 `attachments/formal-tests/`；程序运行时间按系统历史记录的起止时间差计算，问题三为 6、11、5 s，问题四为 8、7、6 s，时间戳显示精度为 1 s。参考文献中的待补内容仍需完成后重新核验。

清理前完整工程保存在 Git 提交 `15bea8b`（“整理评审包”）。旧 `B_locator/`、A/C题、历史探索和多层研究归档可从该提交恢复；现有源码清单中的历史路径也相对于该提交，已不构成运行依赖。
