# A 题工作状态（最终）

> 本文档为 A 题工作的**交接与验收说明**。相关文档：
> `CONVENTIONS.md`（工作规范）、`MODEL.md`（模型推导）、
> `EXPERIMENT_LOG.md`（实验与决策记录）。

---

## 1. 完成情况总览

| 目标项 | 状态 | 证据 |
|---|---|---|
| 两阶段耦合传热传质模型（含移动边界） | **完成** | `docs/MODEL.md`、`src/mol_solver.py` |
| 有限体积求解器 | **完成** | `src/mol_solver.py` |
| 解析解验证 | **完成** | `scripts/verify.py`（均匀热源稳态 + Bessel 瞬态，一阶收敛） |
| 网格/时间步收敛验证 | **完成** | 网格 N=10→160 误差逐次减半；零通量/常通量控制实验精确 |
| result1.xlsx | **完成** | `out/result1.xlsx`，1801×21 |
| result2.xlsx | **完成** | `out/result2.xlsx`，全流程 1 s 输出 |
| result3.xlsx | **完成** | `out/result3.xlsx`，**t_end = 44.55 h** |
| result4.xlsx | **完成** | `out/result4.xlsx`，**t_end = 84.32 h**，R: 2.0→1.198 cm |
| 论文表格数据 | **完成** | `out/tables.md`、`out/tables.json`（表 1–6） |
| 灵敏度分析 | **完成** | `scripts/sensitivity2.py`、`out/sensitivity2.json`（表 7） |
| 中文竞赛论文 | **完成** | `paper/A题_药材的烘干问题.md` |
| 工作区文档 | **完成** | `docs/` 四份文档 |
| git 分支提交 | **完成** | 分支 `feat/a-drying-solution` |

**核心结果**

| 问题 | 结果 |
|---|---|
| 1 | 1800 s：中心 28.00→30.23 °C，表面 28.00→32.21 °C；表面 $C$: 2.5500→2.4041 |
| 2 | 3 h：中心 43.65 °C，表面 43.82 °C；表面 $C$: 2.5500→1.8135 |
| 3 | **烘干时间 44.55 h（约 1.86 天）**，由中心含水率决定 |
| 4 | **烘干时间 84.32 h（约 3.51 天）**，半径 2.0→1.198 cm |

---

## 2. 本题最有价值的三个建模发现

### 2.1 附件 1 的"水分浓度"是烘房空气的绝对湿度

**不是**药材含水率。校验：28 °C、$Y=0.01963$ ⇒ RH = 85%；
50 °C、$Y=0.05$ ⇒ RH = 61%。两者皆为合理烘房工况。
二者量纲相同（kg/kg）而对象完全不同，混用会产生数量级错误。

### 2.2 附件 2 的收缩数据与附录 4 的密度公式严格自洽

由干物质守恒 $\rho_d R^2=\text{const}$ 得

$$\frac{\rho_d(t_f)}{\rho_d(0)}
=\frac{760+90C(t_f)}{760+90C(0)}\cdot\frac{1+C(0)}{1+C(t_f)}=2.774,
\qquad
\left(\frac{R_0}{R_f}\right)^2=\left(\frac{2.0}{1.198}\right)^2=2.788$$

**相差 0.5%**。这既验证了数据，也证明问题 4 必须以干物质守恒写方程、
且必须用附录 4 的密度式（附录 3 的 $\rho=650+128C$ 给出 1.05，与附件 2 不相容）。

### 2.3 附录 2 的 $h$ 与 $h_m$ 互相矛盾 $3\times10^4$ 倍（最重要）

$h=25$ W/(m²·K) 与 $h_m=8\times10^{-7}$ m/s 按 Chilton–Colburn 类比应有

$$h_m^{\rm Lewis}=\frac{h}{\rho_a c_{p,a}Le^{2/3}}=2.41\times10^{-2}\ \text{m/s}$$

**定量后果**（表 7 第 2 行）：直接采用给定 $h_m$ 时，模型收敛到
$C_{\max}\to2.52$ 的平衡含水率，**结构上永远无法达到 0.15**。

**本文处理**：采用供热控制（湿球）闭合
$j_w=h(T_\infty-T_{\rm wb})/L_w$，并把给定的 $h$ 用在正确位置。
该闭合与题述"2–3 天"及附件 2 的 72 h 收缩过程相容。

---

## 3. 求解器的验证证据

| 检验 | 结果 | 脚本 |
|---|---|---|
| 离散水量收支 $\rho_d\sum_i V_i\dot C_i=-F_Nj_w$ | $\le1.8\times10^{-16}$ | `check_water_convention.py` |
| 离散能量收支 $\sum_i V_i\rho c_p\dot T_i=F_Nq_{in}$ | $\le6.6\times10^{-15}$ | `check_budget_exact.py` |
| 零通量控制 $j_w\equiv0$ | $\Delta W=0$ 精确 | `diag_const_flux.py` |
| 常通量控制 $j_w=10^{-5}$ | 失水量/$(2\pi Rj_wt)=1.000000$ | 同上 |
| 均匀热源稳态解析解 $\Delta T=Q_0R^2/4k$ | 一阶收敛：2.71→1.37→0.69→0.35→0.17 K | `verify.py 1` |
| 圆柱瞬态 Bessel 级数（347.111 K） | 一阶收敛 | `verify.py 2` |

### 3.1 修复过的两个实质性错误

1. **圆柱扩散算子面积因子错误**（曾使热扩散慢 50 倍）。
   症状：均匀热源稳态解的中心-表面温差收敛到 $50\times$ 解析值。
   根因：面面积数组少因子 2。改用显式物理几何后修复。
2. **干基水量的 $\rho_d$ 记账不一致**（曾使水分流失多算 $\rho_d\approx231$ 倍）。
   症状：失水量与表面通量积分之比恒为 231.0。
   根因：边界项用 $F_Nj_w/V$，而水存量用 $\rho_d V C$。
   统一为 $\rho_d V_i\dot C_i=-F_Nj_w$ 后修复（常通量控制实验比值 1.000000）。

---

## 4. 灵敏度分析结论（表 7）

| 假设 | 变体 | $t_{\rm end}$/h | 相对基准 |
|---|---|---|---|
| **基准**（供热控制，$h=25$） | — | **45.0** | 1.00 |
| 表面传质闭合 | 给定 $h_m=8\times10^{-7}$ | **永不达标** | — |
| 对流换热系数 | $h=15$ | 71.0 | ×1.58 |
| 对流换热系数 | $h=40$ | 30.0 | ×0.67 |
| 烘房外推 | 4 h 后缓升至 55 °C | 34.0 | ×0.76 |
| 相变切换 | 1200 s / 2400 s | 44.8 / 44.7 | ×1.00 / ×0.99 |

**结论**：表面传质闭合最敏感；烘干时间与 $h$ 近似成反比（供热控制）；
环境外推影响 −24%；切换时刻几乎无影响（<1%）。

---

## 5. 已知局限（已写入论文 §8）

1. 一维径向假设忽略轴向与端面效应（长径比 12.5 时端面散热约占 8%）。
2. 表面吸附等温线用线性可用度 $\phi=C_s/C_{\rm sat}$ 近似，未用实测等温线，
   会略微高估降速期速率。
3. 2–3 天的环境条件需外推（附件 1 仅 4 h）。
4. 附录 4 的 $D$ 指前因子极大（$4.2\times10^{-4}$ m²/s），使水分扩散时间尺度
   远小于过程时长，干燥实际由**供热与外部传质**控制；这一点已在论文中说明。
5. 汽化潜热取常数（50 °C 时真实值约低 2%）。

---

## 6. 目录与复现

```
workspace/A_drying/
├── docs/            CONVENTIONS.md  MODEL.md  EXPERIMENT_LOG.md  STATUS.md
├── src/             mol_solver.py  model_problems.py  write_result.py
├── scripts/         final_produce.py  produce_p2/p3/p4.py  verify.py
│                    check_*.py  diag_*.py  sensitivity2.py  make_tables.py
├── tests/           test_mol_solver.py
├── data/            attachment1_ambient.csv  attachment2_radius.csv
└── out/             result1..4.xlsx  p1..p4.npz  tables.md  sensitivity2.json
paper/A题_药材的烘干问题.md
```

**复现全部结果**：

```powershell
cd F:\project\Mathemetical_modeling_202609\workspace\A_drying
$env:PYTHONPATH='src'
python scripts\verify.py 1          # 稳态解析解验证
python scripts\check_water_convention.py
python scripts\produce_p2.py        # result2
python scripts\produce_p3.py        # result3
python scripts\produce_p4.py        # result4
python scripts\sensitivity2.py      # 灵敏度
python scripts\make_tables.py       # 论文表 1-6
```

---

## 7. 技术债

`src/` 下仍有四个早期迭代求解器（`drying_solver.py`、`solver.py`、
`robust_solver.py`、`final_solver.py`），**已不使用**，应删除以免误用；
`scripts/` 下的 `probe_*.py`、`_patch_*.py` 等一次性探针可移入 `scripts/dev/`。
