# 问题一：数据清单与复现说明

> 本文件列出论文摘要与 5.1 节引用的**全部数值**、它们在附件中的来源字段，以及一键复现方法。
> 评审若对某个数字有疑问，按“来源”一列重跑即可得到同一结果（脚本使用固定种子，
> 重跑产物与仓库内文件**逐字节一致**）。
>
> 覆盖范围：问题一（摘要问题一段 + 5.1 节）。文中路径均相对仓库根目录。

---

## §0 复现环境与命令

- 依赖：**Python 3 + NumPy**。全过程离线，不需要网络。
- 全部数值由下面两条命令产出，均在 `B_locator/Q1/` 目录下执行：

```bash
cd B_locator/Q1
python p1_experiments.py     # 重建 5 组算例 + 逐例求解 + 四组随机扫描 → p1_summary.json
python p1_selftest.py        # 自检 I1–I8（含“算例逐字节可复现”“四组扫描可复现”）
```

- 固定种子（写在 `p1_experiments.py` 顶部）：

| 用途 | 种子 | 说明 |
|---|---|---|
| 五组算例生成 | `DEFAULT_SEED = 20260901` | `gen_cases()`；同种子逐字节复现 |
| 两测点扫描 | `SWEEP_TWO_POINT['seed'] = 17` | 20000 次 |
| 3~6 测点扫描 | `SWEEP_WELL_COND['seed'] = 5` | 4000 次 |
| 测向误差随机流 | 扫描种子 $+\,900001$ | 与构型随机流分离，保证“理想/实际”两组**逐例配对、只差误差取法** |

- 问题一目录中的关键文件：`p1_intersection.py`（求解库）、`p1_experiments.py`（算例与扫描）、
  `p1_selftest.py`（自检）、`cases/p1_case01~05.csv`（算例）、`cases/p1_case01~05.truth.json`
  （真值，仅自检用）、`p1_results.jsonl`（逐例全字段）、`p1_summary.json`
  （汇总，**本文数据的唯一落盘文件**）、`multi_sensor_wedge_diagram.png` 等 3 张定版插图。

---

## §1 数据清单

### 1.1 表 2（5.1.4 节“问题一算例的计算结果”）

来源：`B_locator/Q1/p1_summary.json` → `per_case[*]`（复现：跑 `p1_experiments.py`）。

| 算例 | 字段 | 值 | JSON 字段 |
|---|---|---|---|
| $A_1$ | 检测点数 / 顶点数 / $D$ / $D/2$ / $\max\|P-M\|$ / 比值 / 覆盖 | 6 / 6 / 17.64 / 8.82 / 8.82 / 1.0000 / 是 | `n_bearings` `n_vertices` `diameter_m` `circle_radius_m` `max_vertex_dist_m` `ratio` `coverage` |
| $A_2$ | 同上 | 5 / 5 / 18.61 / 9.31 / 10.29 / 1.1055 / 否 | 同上 |
| $A_3$ | 同上 | 4 / 5 / 25.64 / 12.82 / 13.75 / 1.0722 / 否 | 同上 |
| $A_4$ | 同上 | 5 / 4 / 21.12 / 10.56 / 10.56 / 1.0000 / 是 | 同上 |
| $A_5$ | 同上 | 6 / 5 / 10.59 / 5.30 / 5.30 / 1.0000 / 是 | 同上 |

### 1.2 5.1.4 节正文中的其余数字

| 论文位置 | 数据 | 值 | 来源 |
|---|---|---|---|
| 5.1.4 开头 | 五组算例方位张角范围 | $180^\circ\sim249^\circ$ | `cases/p1_case0*.truth.json` → `azimuth_span_deg`（179.97 / 205.71 / 204.49 / 229.72 / 249.03） |
| 5.1.4 开头 | 最小方位间隔 | $\ge 25^\circ$ | 同上 → `min_azimuth_gap_deg`（25.11~30.36） |
| 5.1.4 开头 | 检测点到源点距离 | $160\sim1300$ m | `cases/p1_case0*.csv` → `dist_m`（最小 159.7 m，最大 1294.2 m） |
| 5.1.4 开头 | 五组直径范围 | $10.59\sim25.64$ m | `cases_summary.diameter_m_range` |
| 5.1.4 第 2 段 | $A_2$、$A_3$ 越界超出量 | $0.98$ m、$0.93$ m | `per_case[A2/A3].excess_m`（0.9819 / 0.9259） |
| 5.1.4 第 2 段 | $A_2$、$A_3$ 超出比例 | $10.55\%$、$7.22\%$ | `per_case[A2/A3].excess_pct`（10.5518 / 7.2215） |
| 5.1.4 第 2 段 | $A_2$ 越界顶点处张角 | $84.2^\circ$ | `per_case[A2].worst_vertex_angle_deg`（84.21） |
| 摘要问题一段 | 两组失败中的最远越界比例 | 约 $10.6\%$ | `per_case[A2].excess_pct`（10.5518 → 约 10.6%） |
| 图 3 | 判据与曲线 | — | 由 `cases/p1_case01.csv`、`cases/p1_case02.csv` 经 `p1_intersection.py` 求解后绘出（插图为定版成果） |

### 1.3 表 3（5.1.4 节“四组随机扫描的覆盖失败统计”）

来源：`p1_summary.json` → `sweeps.*`（复现：跑 `p1_experiments.py`）。
“需放大约”＝最坏比值 $-1$，正文与表中均按 0.1% 取整。

| 构型 | 检测点数 | 试验数 | 有界数 | 失败数 | 失败率 | 最坏比值 | 需放大约 | JSON 键 |
|---|---|---|---|---|---|---|---|---|
| 理想（各示向度精确指向源点） | 2 | 20000 | 20000 | 231 | 1.16% | 1.0336 | 3.4% | `sweeps.two_point` |
| 理想 | $3\sim6$ | 4000 | 3472 | 113 | 3.25% | 1.0304 | 3.0% | `sweeps.well_conditioned` |
| 实际（同批构型 + $\pm1^\circ$ 误差） | 2 | 20000 | 19996 | 246 | 1.23% | 1.0346 | 3.5% | `sweeps.two_point_err` |
| 实际 | $3\sim6$ | 4000 | 3472 | 993 | 28.60% | 1.6876 | 68.8% | `sweeps.well_conditioned_err` |

各键下的字段：`n_trials`、`n_bounded`、`n_fail`、`fail_pct`、`worst_ratio`、
`n_unbounded`、`n_empty`、`n_degenerate`（后三者记录被跳过的构型数）。

**按检测点数的失败率明细**（实际构型；论文正文未列，供复核）：

| $m$ | 有界构型 | 失败 | 失败率 |
|---|---|---|---|
| 3 | 966 | 164 | 16.98% |
| 4 | 859 | 243 | 28.29% |
| 5 | 897 | 309 | 34.45% |
| 6 | 750 | 277 | 36.93% |

来源：`sweeps.well_conditioned_err.per_m['3'~'6']`。理想构型对应值为 3.11% / 2.79% / 3.46% / 3.73%。

### 1.4 算法参数

| 论文位置 | 数据 | 值 | 来源 |
|---|---|---|---|
| 5.1.2 / 5.1.3 | 示向度误差界 $\varepsilon$ | $1^\circ$ | `p1_intersection.py` → `BEARING_ERR = 1.0` |
| 5.1.3 第四步 | 覆盖判定绝对容差 $\tau$ | $10^{-9}$ m | `p1_intersection.py` → `analyse()` 中 `maxr <= D/2 + 1e-9`（`p1_experiments.py` 的 `solve_full()` 同） |
| 5.1.3 末段 | 两套区域实现的顶点最大偏差 | $\le 10^{-9}$ m | `p1_selftest.py` → 不变量 I6（五组算例实测 $\le 6.4\times10^{-10}$ m） |
| 5.1.3 状态名 | `unbounded` / `empty` / `degenerate` | — | `p1_intersection.py` → `analyse()` 与 `_dedup_hull()`；原因字符串亦在该处 |

---

## §2 自检说明（“重跑即复现”的依据）

`python p1_selftest.py` 全部通过时给出 8 类不变量：

- **I1–I6**（逐例）：真值落在区域内、顶点为逆时针凸序、直径三算法一致、`analyse()` 与全精度
  覆盖判定一致、直径量级合理、两套独立区域实现顶点逐点一致。
- **I7**：五组算例及其真值文件可由固定种子**逐字节复现**。
- **I8a–I8e**：两组理想扫描与两组实际扫描的 `n_bounded / n_fail / worst_ratio`
  与 `p1_summary.json` 完全一致；汇总表中逐例比值与覆盖判定可复现。

若怀疑某个数字“偏大”（例如实际构型 $3\sim6$ 测点 $28.60\%$ 的失败率）：

1. 跑 `python p1_experiments.py`，看终端打印的“随机扫描”四行与 `p1_summary.json` 是否一致；
2. 若只想看该数字的来源：`python -c "import json;d=json.load(open('p1_summary.json'));print(d['sweeps']['well_conditioned_err'])"`；
3. 该失败率并非个例：把它与论文表 2 中五组算例（带 $\pm1^\circ$ 误差、$2/5$ 失败）对照，
   或用 `B_locator/Q1/cases/p1_case02.csv`（$A_2$，比值 1.1055）复算——覆盖失败在带误差的构型中
   是常见现象，其成因是各示向度误差方向不一致使定位区域偏离以源点为公共交点的对称形状。

---
