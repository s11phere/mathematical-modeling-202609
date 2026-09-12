# Q4 论文实验复现

本文件对应本轮重新运行的 `out/paper_q4/` 数据，不读取或混用既有优化报告中的结果。实验仅调用离线 `MockArena`；没有调用在线模拟器。

论文正文为 `../paper/sections/q4-model.tex`，按“模型建立—算法实践—数据分析”组织，图文使用 `grid / joint / compact` 三个名称，分别对应数据中的 `legacy / joint_strict / compact_strict`。Q4 摘要、问题分析及复现附录一并接入整篇论文；五幅图均由实际数据或明确标注的确定性几何示例生成。

## 公式与实现对应

| 正文标签 | 内容 | 对应实现 |
|---|---|---|
| `eq:q4-reception` | 距离与发射半平面同时成立 | `src/p3_arena.py`；物理方向与存储方向相反 |
| `eq:q4-triangle` | 三角形凸组合与可接收顶点 | `src/p4_grid.py`；最远顶点上界为边长 |
| `eq:q4-cell`—`eq:q4-stop` | 整方格、连续朝向及逐频道退出证书 | `src/p4_certificate.py`、`src/p4_layout_v2.py`、`src/p4_compact.py` |
| `eq:q4-layout` | 21 站布局及自适应细分 | `src/p4_compact.py`、`src/p4_layout_v2.py` |
| `eq:q4-region`—`eq:q4-clear-cover` | 正观测外包、双侧负观测截断、28 m 清除兜底 | `src/p4_homing.py` |
| `eq:q4-posterior` | 150×9×36 射线后验近似 | `src/p4_posterior.py` |
| `eq:q4-route` | 路程与参考检测代价、翻转及移位搜索 | `src/p4_route_v2.py` |
| 主表及全部区间 | 230 次固定配对实验 | `run_paper_q4.py`、`out/paper_q4/runs.jsonl`、`summary.json` |

图表与源码展示重建：

```powershell
python B_locator/Q4/make_paper_tables.py
python B_locator/Q4/scripts/make_paper_figures.py
python B_locator/Q4/scripts/make_paper_source.py
```

三条命令读取冻结数据或源码，不重跑实验。完整源码展示材料按本地导入关系收录 25 个文件及 9600 行程序，运行源文件保持原样；Unicode 转义只用于完整 TeX 展示副本。整合后的论文附录仅直接载入 `src/p4_compact.py` 核心代码，完整源码与生成的展示材料保留在附件中。六组专项检查共37项通过，日志在 `out/paper_q4/checks/`。

## 运行

在仓库根目录使用 Python 3 和 NumPy：

```powershell
python B_locator/Q4/run_paper_q4.py --workers 6 --out B_locator/Q4/out/paper_q4_reproduce
```

本机实际使用的解释器是 `C:/Users/27045/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`。本轮原始命令为：

```powershell
& 'C:/Users/27045/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' B_locator/Q4/run_paper_q4.py --workers 6
```

脚本拒绝覆盖已有 `runs.jsonl`；断点续跑可在原命令后加 `--resume`，只重做尚无完整记录的任务。续跑前会核对全部算法代码 SHA256 和实验参数。汇总重建使用原命令加 `--summarize-only`，不重跑模拟。新复现实验建议使用新的 `--out`，保留原始论文数据。

## 固定设计

- 主集：`mixed_uniform`，30 个场景，种子 `2026091201 + 79 i`，`i = 0, …, 29`；同一场景分别运行 `legacy`、`joint_strict`、`compact_strict`，共 90 局。
- 压力集：`minrange`、`edge`、`omni` 各 10 个场景，种子分别为主集基数加 `1 000 000`、`2 000 000`、`3 000 000` 后再加 `79 i`；三个版本配对，共 90 局。
- 消融：固定主集前 10 个场景，分别只关闭 `posterior_estimate` 或 `route_information`，其余参数保持 `compact_strict` 不变，共追加 20 局。基线复用相同场景的已有 strict 结果。
- 速度档：同样固定主集前 10 个场景，追加 `compact_fast99`、`compact_fast95`、`compact_fast90`，共 30 局。档名只是配置名称，不表示理论清除率保证。
- 总计 60 个不同场景、230 次策略运行、3 002 次源暴露；无结果筛选。第一幅案例轨迹固定采用主集第一例 `2026091201`。

主集在半径 1 800 m 圆盘内按面积均匀布源，源数在 10–16 之间离散均匀抽取，频道无重复；每源以概率 0.5 为半角 90° 的定向源，定向角度均匀分布，其余为全向源；接收半径在 1 000–1 500 m 均匀抽取。这里的“50% 定向”是逐源概率，不要求每局恰好一半。

`minrange` 为全定向、均匀随机朝向、接收半径固定为 1 000 m；`edge` 的源半径在 1 750–1 800 m 均匀分布且只能从外侧半平面听到、接收半径 1 000 m；`omni` 全为全向源。`edge` 的角度严格采用代码的“测站指向源”约定，源参数为 `dir_deg = polar_angle + 180°`。位置、朝向与半径的完整精度参数均保存在轨迹文件中。

每个配对算法单独重建同一种子场景，共享完全相同的源参数及固定地点误差场。策略的 `run()` 完成并退出后才读取真值，评分用真值不回流给策略。

## 指标与统计

主指标是从 `/enter` 到 `/exit` 的完整虚拟耗时 `exit_s`。它包含最后一个源清除后继续排除未知频道的耗时。`last_s` 是最后一次成功清除的时刻；二者差额为 `tail_s`。每源指标分别先按局计算 `exit_s / cleared`、`last_s / cleared`，再对局取均值。另保留 `pooled_exit_per_cleared = sum(exit_s) / sum(cleared)`；它与局均每源指标是不同统计量。

每局动作账本按下式独立校验完整耗时：

\[
T_{\mathrm{exit}}=L/5+5N_m+N_{\mathrm{switch}}+5N_{\mathrm{success}}+3N_{\mathrm{fail}}.
\]

其中只由 `/measure` 触发频道切换，`/clear` 不切换频道。脚本逐局核对移动距离、检测次数、成功与失败清除次数、最后成功时刻以及动作 `dt` 总和；230 局全部通过，拒绝动作总数为 0。

`clearance_rate` 是所有已清源数除以总源数；`full_clear_cases` 是整局全清数。`certified` 记录策略原始返回值，`certification_mode` 区分是否请求连续证明。论文只把 `certification_mode = continuous` 且 `certified = true` 记为连续终止认证；速度档即使偶然全清，也不因此获得严格认证。

置信区间采用 10 000 次百分位 bootstrap，抽样单位为完整场景，不把同局多个源当作独立样本。版本差值使用同一种子配对重抽样；`saved_s = mean(T_before - T_after)`，`saved_fraction = saved_s / mean(T_before)`。统计种子、方法及所有区间保存在 manifest 与 summary 中。全清样本给出退化的清除率 bootstrap 区间不意味着未来总体的清除概率为 100%；理论保证依靠独立的连续覆盖证明和定位兜底。

## 本轮结果与解释边界

| 主集配置 | 完整退出 / s | 局均完整退出每源 / s | 局均最后清除每源 / s | 全清 / 连续认证 |
|---|---:|---:|---:|---:|
| legacy | 8 426.12 | 666.67 | 552.46 | 30/30；无连续认证 |
| joint strict | 6 556.92 | 520.10 | 479.93 | 30/30；30/30 |
| compact strict | 5 819.13 | 461.30 | 423.74 | 30/30；30/30 |

compact strict 相对 joint strict 的主集配对平均节省为 737.79 s，95% bootstrap 区间为 [591.83, 888.44] s，均值减少 11.25%。与 legacy 相比均值减少 30.94%。legacy 在主集恰好全清，但在 edge 压力集仅清除 128/135 个源、4/10 局全清；因此其启发式退出不能替代严格全清保证。两个严格版本在 120 局基线/压力运行中全部全清并获得连续认证。

消融仅有预先固定的 10 例：启用后验估计平均节省 452.74 s，95% 区间 [145.25, 745.91] s；启用信息排路平均节省 147.04 s，95% 区间 [-84.44, 397.81] s。后者均值改善，但此小样本尚不能单独确认稳定收益。不得把整个版本的改善全部归功于信息排路，也不得把同批消融当作独立大规模验证。

速度档在固定 10 例中分别清除 133/133、130/133、129/133 个源，整局全清 10/10、8/10、6/10；均值完整退出时间分别为 5 407.07、4 789.72、4 210.52 s。它们属于效率与覆盖的经验取舍，不能由这 10 例推断未来达到 99%、95%、90% 的置信保证。

本轮 6 个进程的整批实验及数据整理墙钟耗时约 60.65 s，单局 `run()` 最大 7.55 s；主集单局均值 legacy 约 0.09 s、joint strict 约 0.63 s、compact strict 约 4.19 s。单局 `runtime_s` 包含策略执行与本地终止认证，`setup_runtime_s` 独立记录构造和布局认证。并行调度与机器负载会改变墙钟时间，虚拟时间是题目代价且与墙钟指标不同。本轮记录的 UTC 开始/结束时间为 `2026-09-12T14:43:56.952046+00:00` / `2026-09-12T14:44:57.607688+00:00`。

## 文件说明

- `out/paper_q4/manifest.json`：全部任务、场景定义、随机种子、配置、Python/NumPy/操作系统、算法源码 SHA256、原始 JSONL SHA256。
- `out/paper_q4/runs.jsonl`：每次策略运行一行；包含完整配置、所有指标、场景参数哈希、压缩轨迹路径及 SHA256。
- `out/paper_q4/traces/*.json.gz`：230 个完整轨迹；包含所有动作及回复、真值源参数（`x`、`y`、`r_recv`、`cone_half`、`dir_deg`）、算法事件、统计、最终报告、计划站位。
- `out/paper_q4/summary.json`：按实验组汇总的均值、区间、全清与认证统计，以及配对 bootstrap 比较。
- `out/paper_q4/representative_legacy.json`、`representative_joint_strict.json`、`representative_compact_strict.json`：固定主集第一例的可直接读取轨迹。

`summary.groups` 中 `experiment` 取 `main`、`stress`、`ablation`、`speed`；消融和速度图的 strict 基准仅使用相同的前 10 例，不能用完整 30 例的 strict 均值替换。`summary.comparisons` 中消融比较方向是“关闭模块 → 完整 compact”，速度比较方向是“compact strict → 速度档”。
