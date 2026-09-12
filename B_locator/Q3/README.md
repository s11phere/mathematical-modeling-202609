# B 题问题三：多源定位与清除

本目录汇集 `problem_b` 分支中已提交的问题三内容，默认策略为 `joint`。新分支以 `main` 为基础，原有 `B_locator/Q1`、`Q2` 和 `paper` 完整保留。

## 来源与目录

- 基础版本：`main`，提交 `417998c`。
- 问题三来源：`problem_b`，提交 `b9c57f1`。
- 共迁入 122 个源文件；逐文件来源、Git blob 与路径适配记录见 [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)。

| 目录 / 文件 | 内容 |
| --- | --- |
| `src/p3_*.py` | 全部 57 个问题三模块，包括策略、模拟器、基准实验、诊断、绘图和自检 |
| `src/p1_intersection.py`、`src/p2_grid_expectation.py` | 问题三所需的公共几何与期望场模块，使用 `problem_b` 版本 |
| `scripts/`、`tests/` | 运行、自检入口和共享算例生成器 |
| `data/` | 三组问题三扫描数据与真值；`MANIFEST.json` 仅列本目录的问题三数据 |
| `out/p3/`、`out/p3_family/` | 已入库的实验结果、图及九组先验外径基准场 |
| `out/p2_grid/` | 问题三默认加载的期望场及其来源结果 |
| `review/` | 问题三设计说明、实测记录、研究脚本及对应输出 |
| [Q3-notes.md](Q3-notes.md) | 源 README 的完整问题三章节，运行示例路径已适配 |
| `docs/source/` | 原 README、根目录分析、共享数据清单，以及六份涉及问题三的论文章节快照 |

混合文档保留原文上下文，因此来源快照和共享生成器也包含其他问题的内容。论文章节快照用于查阅；主论文仍在 `B_locator/paper`。

## 运行

核心计算和自检依赖 NumPy；绘图、报告需要 Matplotlib，`p3_verify_paths.py` 的覆盖审计还需要 SciPy。以下命令从仓库根目录执行：

```bash
# 默认 joint 策略，离线运行一局，结果写入独立目录
python3 B_locator/Q3/scripts/run_p3.py --mode mock --cases 1 --out B_locator/Q3/out/p3_smoke

# 快速自检，使用独立日志，保留迁入的历史自检结果
python3 B_locator/Q3/tests/selftest_p3.py --quick --out B_locator/Q3/out/p3_quick_selftest.txt

# 当前默认策略的专项检查
python3 B_locator/Q3/src/p3_joint_checks.py
```

原 `src/`、`data/`、`out/`、`review/` 相对结构已保留；四个实验脚本的默认输出路径改为相对于脚本定位到本目录，运行示例也已更新为 `B_locator/Q3/`。算法与数值结果沿用源分支。

共享 `scripts/b_testdata.py` 会重新生成多问数据与清单；如需使用，请通过 `--out` 指向另一个目录，以保留本次迁入的数据。

迁入验证（2026-09-12）：快速自检 28/28 项、`joint` 专项检查 12/12 项通过；默认入口离线一局清除 10/10 个目标，零拒动。所有 Python 文件通过语法解析，114 个源文件保持字节一致，另 8 个文件仅作上述路径适配。绘图和完整批量实验未重新运行。

## 源分支未入库的内容

源 README 引用了 `review/p3-adaptive-design.md`、`review/P3-adaptive-verification.md` 和 `review/p3-joint-design.md`，以及 `out/p3_verify/`、`out/p3_paths*`、在线逐局轨迹等产物。这些文件不在 `problem_b` 的提交中，本次按已提交内容整理，未重新生成历史实验。对应的报告、绘图和验证代码已收录在 `src/`。

原文中的运行记录、ACL 说明及待办是源分支的历史记录；运行示例以本文件为准。
