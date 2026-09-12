# B 题问题四：三角形格网覆盖扫描 + 定向源定位清除

## 论文完成与新实验（2026-09-12）

现行论文以 `compact + strict` 为最终策略，旧格网实现作为演进对照。正文见 `../paper/sections/q4-model.tex`，数据、公式和算法依据见 [PAPER_REPRODUCE.md](PAPER_REPRODUCE.md)。本轮重新运行 230 次配对实验，最终严格版在 60 个场景中清除全部 779 源并取得连续证书；随机主集完整退出时间 5819.1 s，较上一版严格策略降低 11.25%。五幅插图、公式推导、消融与核心源码附录已接入论文；完整源码保留在本目录。

以下迁入记录保留原状。历史 `P4-design.md` 中的最远顶点距离及径向两遍覆盖论证存在过度推断；论文使用当前连续位置与朝向证书，性能数值只取本轮冻结数据。

本目录汇集 `problem_b` 分支中已提交的问题四内容，默认策略为 `compact`（21 站严格布局）、默认档位 `strict`。新分支以 `codex/b-locator-q3` 为基础，原有 `B_locator/Q1`、`Q2`、`Q3` 与 `paper` 完整保留。

## 来源与目录

- 基础版本：`codex/b-locator-q3`，提交 `5dbf748`。
- 问题四来源：`problem_b`，提交 `c223510`。
- 共迁入 68 个源文件（`src/` 66 + `review/` 2）；逐文件来源、Git blob、路径适配记录见 [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)。

| 目录 / 文件 | 内容 |
| --- | --- |
| `src/p4_*.py` | 全部 60 个问题四模块：三角形格网与覆盖判据、统一航路策略（边扫描边清理）、定向/全向混合案例生成、离线演练与真机入口、A/B 与参数扫描、几何设计报告、自检 |
| `src/p3_robot.py`、`src/p3_arena.py`、`src/p3_httpstub.py`、`src/p3_expect_field.py`、`src/p2_grid_expectation.py`、`src/p1_intersection.py` | 问题四所需的共享模块（问题三的机器狗 / 靶场 / HTTP 桩，以及公共几何与期望场）。此处使用 `problem_b` 版本：`p4_httpstub.py` 依赖的 `p3_httpstub.serve()` 只存在于该版本 |
| `scripts/run_p4.py` | 运行入口的转发脚本（实现放在 `src/p4_run.py`，与问题三同约定） |
| `tests/selftest_p4.py` | 自检转发入口（实现放在 `src/p4_selftest.py`） |
| `out/` | 运行产物输出目录（默认写入 `out/p4`、`out/p4_search_validation` 等），当前仅有占位文件 |
| `review/` | 问题四设计说明 `P4-design.md`、紧凑布局与搜索设计报告、半平面约定语义脚本、L6 布局输出 |

## 运行

核心计算与自检依赖 NumPy；绘图、报告需要 Matplotlib。以下命令从仓库根目录执行：

```bash
# 几何自检：三角形格网覆盖半径与定向盲区（不跑模拟器）
python3 B_locator/Q4/src/p4_run.py --geometry

# 离线演练（默认 compact + strict；正式测试只有 3 次机会，调参都在这里做）
python3 B_locator/Q4/src/p4_run.py --mode mock --cases 10 --scenario directed --verbose
python3 B_locator/Q4/src/p4_run.py --mode mock --cases 30 --scenario omni        # 全向对照

# 快速自检
python3 B_locator/Q4/tests/selftest_p4.py --quick

# 本地 HTTP 桩 + 真实 --mode live 入口联调（不消耗任何测试次数）
python3 B_locator/Q4/src/p4_httpstub.py --scenario directed --seed 20260914 --port 2028 --delay-open 6
python3 B_locator/Q4/src/p4_run.py --mode live --url http://127.0.0.1:2028 --robot-id TEST0001 \
        --out B_locator/Q4/out/p4_preflight
```

`src/`、`out/`、`review/` 相对结构沿用源分支。输出路径分两类：

- `p4_run.py`、`p4_paths.py` 原本就按脚本位置定默认值（`_ROOT = _HERE/..`），迁入本目录后自动指向 `B_locator/Q4/out/`，与工作目录无关；
- 另外 15 个开发 / 报告脚本写死了 `B_locator/src|out/...`，本次改为 `B_locator/Q4/src|out/...`，仍需在仓库根目录运行（与源分支用法一致）。逐文件记录见 `SOURCE_MANIFEST.json` 的 `adapted` 字段。

算法与数值结果沿用源分支，未做任何逻辑改动。

迁入验证（2026-09-12）：

| 项目 | 结果 |
| --- | --- |
| 语法解析（66 + 2 个 Python 文件） | 全部通过 |
| `src/p4_selftest.py --quick` | 8/8 项通过（快速模式不含端到端演练） |
| `src/p4_run.py --geometry` | 正常退出 |
| `src/p4_run.py --mode mock --cases 1 --scenario directed` | 一局跑通：14/14 源清除，清除率 1.000，拒动 0，墙钟 2.1 s |
| `scripts/run_p4.py --help` 转发入口 | 正常 |

完整批量实验、绘图与出报告未重新运行。

## 源分支未入库的内容

`problem_b` 的 `.gitignore` 排除了 `B_locator/out/` 与 `B_locator/review/`，因此问题四的逐局轨迹、`out/p4_search_validation/`、`out/p4_compact_validation/` 等产物均未入库，本次未重新生成。其中 `review/p4-compact-design.md`、`review/p4-search-design.md`（两份报告由 `src/p4_compact_report.py`、`src/p4_search_report.py` 生成）以及 `review/p4_dir_semantics.py`、`review/out_p4_l6.txt` 是源分支工作区中的现存文件，随本次迁入一并收录，来源标注为 `worktree`。

`review/P4-design.md` 记录的离线验收（每场景 20 局、100 局复验清除率 1.0000、自检 10/10）是源分支的实测结论，本次未复跑，仅供参考；该文件按源分支字节原样收录，其中 `src/...` 形式的路径在本目录下依然成立。

原文中的运行记录与待办属于源分支历史，运行示例以本文件为准。
