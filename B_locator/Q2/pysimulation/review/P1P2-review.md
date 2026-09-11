# B 题 问题 1、2 建模路线 + 问题 1 现有实现审核

> 审核对象：`B_locator/src/p1_intersection.py`（含 `scripts/b_testdata.py`、`tests/selftest_p1.py`）
> 审核方式：两个**独立参考实现**交叉验证 + 1800 组随机/病态算例回归 + 最小反例复现
> 结论：**建模路线正确；代码在"良态有界"算例上结果正确（已发布的 5 个算例数值一字不差），
> 但存在 2 个真实缺陷，会在常见几何下给出错误结果——一个会"少算直径甚至不给结果"，
> 一个会"把无界区域当成有界并报出有限直径"。**已给出最小修补（`review/p1_fixed.py`，回归 0 失败）。

---

## 0. 一页速览

| 项 | 结论 |
|---|---|
| 问题 1 建模路线 | ✅ 正确：示向度 ±1° 角楔 → 半平面交集 → 凸多边形 → 凸包直径 |
| 问题 1 实现（良态算例） | ✅ 正确，且与独立实现数值一致（相对误差 < 1e-5） |
| 问题 1 实现（一般情形） | ❌ 2 个真 bug（见 §2.2、§2.3），1600 组非退化随机算例中 **810 组结果不一致** |
| 已发布的 5 个算例 | ✅ 修复前后完全一致（D、面积、状态都不变），表格可信 |
| 自检脚本 I1–I5 | ⚠️ 太弱：I1 近乎恒真，I2–I4 是"同一份代码的自洽性"，无法发现算错/漏算 |
| 第 1 问第二小问 | 答案"不能保证覆盖"正确；应补：**判定定理（Thales）+ 解析反例 + 最小包围圆修正** |
| 第 2 问 | 建议写成**带约束的最优实验设计**：可行域=扇环；目标=定位区域直径/面积（或等价的 RMS）；约束=移动预算+可检测性+有界性；结论可闭式给出 |

回归汇总（`review/out_orig.txt` / `out_fixed.txt`）：

| 指标 | 原实现 | 修复后 (`p1_fixed.py`) |
|---|---|---|
| 状态/数值不一致算例 | **810 / 1600** | 0（188 组"重合检测点"人为歧义除外） |
| 把无界区域报成有界（假有限直径） | **155** | 0 |
| 有界算例直径最大相对误差 | 33.5% | 5.9e-6（仅来自输出保留 4 位小数） |
| 有界算例面积最大相对误差 | 87.9% | 7.3e-6 |

---

## 1. 问题 1 应该怎么做

### 1.1 定位区域的严格定义

设检测点 $S_i=(x_i,y_i)$，该点测得示向度 $\theta_i$（由 $x$ 轴正向逆时针到 $S_i\to G$ 的角度，$[0^\circ,360^\circ)$），
示向度误差界 $\varepsilon=1^\circ$（附录 2 图 2：两条实线与相邻虚线夹角均为 $1^\circ$）。则**真源必在**

$$
\mathcal{R}=\bigcap_{i=1}^{k} W_i,\qquad
W_i=\{\,X:\ |\operatorname{ang}(X-S_i)-\theta_i|\le\varepsilon\,\}
$$

$W_i$ 是以 $S_i$ 为顶点、张角 $2\varepsilon$ 的**角楔**。它等价于**两个半平面的交**（取 $\theta_i\pm\varepsilon$ 两条边界直线）：

$$
W_i=\{\,X:\ \operatorname{cross}(d_i^-,\,X-S_i)\ge 0\}\ \cap\ \{\,X:\ \operatorname{cross}(d_i^+,\,X-S_i)\le 0\},\quad
d_i^\pm=(\cos(\theta_i\pm\varepsilon),\sin(\theta_i\pm\varepsilon))
$$

于是 $\mathcal{R}$ 是 **$2k$ 个半平面的交 → 凸多边形**（题面称"多边形定位区域"，与图 2 的红色四边形一致）。

> 题面隐含假设：示向度是**有向方位角**（不是无向直线），故不存在 $180^\circ$ 前后模糊。
> 若要把"读数保留两位小数"也作为误差来源，保守做法是把半角取 $1.005^\circ$（面积只大 1%，可忽略）。

### 1.2 三种等价算法（论文里建议都提，实现选一种）

| 算法 | 做法 | 复杂度 | 说明 |
|---|---|---|---|
| 半平面裁剪（Sutherland–Hodgman） | 从一个大框出发，逐个半平面裁多边形 | $O(k^2)$ | 稳健、直接得到按序顶点；本次审核的参考实现 |
| 顶点枚举（现实现） | 枚举 $2k$ 条边界直线的 $O(k^2)$ 个交点，用"落在所有楔内"筛选，再求凸包 | $O(k^3)$（$k\le20$ 时约 $10^4$ 次运算，可忽略） | 精确：凸集的顶点必在两边界直线交点上（可证） |
| 线性规划 / 极值点 | 用 LP 或对偶求支撑函数 | 多项式 | 便于"有界性/可行性"判定，不便于直接出顶点 |

**直径**：区域顶点数 $n\le 2k\le40$，暴力枚举 $O(n^2)$ 与旋转卡壳 $O(n)$ 均可；建议主算法用旋转卡壳，
再用暴力枚举做一致性校验（现实现正是如此，二者一致）。

### 1.3 必须写进论文的退化/异常情形（现实现有一半没处理）

| 情形 | 判据 | 正确输出 |
|---|---|---|
| **无公共交集** | 顶点枚举为空 / LP 不可行 | "数据不一致"（误差可能超出 $\pm1^\circ$），不给直径 |
| **区域无界** $\Rightarrow$ 直径 $=+\infty$ | 存在方向 $d$ 使得 $\lvert\operatorname{ang}(d)-\theta_i\rvert\le\varepsilon\ \forall i$ ⟺ **所有示向度两两夹角 $\le 2\varepsilon$** | 必须显式报"无界"，不能报有限直径 |
| **退化为点/线段** | 交集维数 < 2 | 报退化，并给出该点/线段 |
| **检测点落在其它楔内** | 该点是 $\mathcal{R}$ 的**顶点**（两个起作用约束非平行 $\Rightarrow$ 必为极点） | **必须保留为顶点** |

两点补充，很适合写进论文体现建模深度：

1. **"有界"不等于"有用"**。即使张角刚过 $2^\circ$，直径也可能极大：算例
   $S_1=(0,0),\theta_1=45^\circ$、$S_2=(500,300),\theta_2=47.6^\circ$ 得 $D=12807$ m，
   而靶区直径才 3600 m、清除半径 20 m。所以实践中应再加"直径阈值 $D\le D_{\max}$"作为**有效性判据**。
2. **物理可容许区域**。叠加"距离 $\le$ 有效接收半径 1500 m"（圆盘）与靶区圆域后，区域必有界；
   检测点沿视线排布时（机器人沿示向度方向逼近干扰源就是这种几何），
   纯几何区域无界，物理区域直径仍可达 **1050–1300 m**（见 `review/out_extra.txt`）。

### 1.4 第二小问：以直径为直径的圆能否覆盖定位区域？

**答案：不能保证覆盖。** 论文建议写成一个"判定 + 反例 + 修正"的三段式：

**(a) 判定定理（Thales，$O(n)$）**
以直径 $AB$ 为直径的圆记为 $C$。$\forall V\in\mathcal{R}$，

$$
V\in C\iff \angle AVB\ge 90^\circ \iff |V-c|\le D/2,\quad c=\tfrac12(A+B)
$$

因此只需检查所有顶点到 $c$ 的距离；这也说明"判定覆盖"不需要求交，只需求一次直径。

**(b) 解析反例：等边三角形。** 边长为 $D$ 的等边三角形，其直径为边长，第三顶点处张角 $60^\circ<90^\circ$，
到直径中点距离 $\tfrac{\sqrt3}{2}D>\tfrac12D$（比值 $1.732$）。此反例在本题**可实现**：
`review/out_triangle.txt` 给出了一组真实交会算例（3 个检测点 + 示向度），其定位区域恰为三角形，
第三个顶点处张角 $74.3^\circ<90^\circ$，直径圆不覆盖。

**(c) 定量结论**（1850 组随机良态区域的统计，`out_orig.txt` C6 段）

| 量 | 数值 |
|---|---|
| 直径圆不覆盖的比例 | 296/1850 ≈ **16%** |
| 最小包围圆半径比 $r^\*/(D/2)$ | 均值 1.0019，最大 1.137 |
| 理论上界（Jung 定理，平面） | $r^\*\le D/\sqrt3$，比值 $\le 2/\sqrt3\approx1.1547$，等号仅等边三角形 |

**(d) 修正方案。** 实际使用（问题 3/4 的搜索/清除）应当用**最小包围圆**而不是直径圆：
半径 $r^\*\in[D/2,\ D/\sqrt3]$，用"枚举 2 点/3 点候选圆 + 包含性检验"（Welzl 算法）$O(n)$ 求出，并给出圆心作为搜索中心。

**论文图表建议**：图 2–3 个算例（一个覆盖、一个不覆盖）、一张 $r^\*/(D/2)$ 直方图、
一张"示向度夹角 vs $D$"曲线（说明 $D\sim 1/\sin\gamma$ 的放大效应）。

---

## 2. 现有实现审核（`src/p1_intersection.py`）

### 2.1 正确的部分（已验证）

* 角楔 $\to$ 半平面 $\to$ 凸包路线正确；顶点枚举法的**完备性**可证（凸集顶点必为两起作用约束边界交点），
  实测与半平面裁剪参考实现一致：有界算例直径/面积相对误差 $<10^{-5}$（含输出四舍五入）。
* 直径用"暴力枚举 + （大 $n$ 时）旋转卡壳"，$n\le2k$，稳健。
* 覆盖判定 `max_vertex_dist <= D/2` 与 Thales 判据等价，实现正确。
* 空集、点/线段退化分支存在。
* **已发布的 5 个算例（`data/p1_case01..05`）在修复前后完全一致**，也与 README 表格数字一致
  （17.6414/93.0212、18.6112/168.3203、25.6424/287.5678、21.1168/111.9497、10.5912/42.9558）——
  所以**当前论文表格不用改**，问题出在覆盖率上（见 §2.4）。

### 2.2 Bug 1（严重）：检测点本身可以是定位区域顶点，却被丢弃

`region_from_bearings()` 第 79–82 行：

```python
for p, th in zip(pts, svds):
    d = math.hypot(X[0] - p[0], X[1] - p[1])
    if d < 1e-9:            # ← 把"候选顶点正好落在检测点上"直接判为不可行
        good = False; break
```

**为什么错**：当检测点 $S_i$ 落在**其它所有楔**内时，$S_i$ 同时是 $W_i$ 两条边界直线的交点，
即两个起作用约束的交点，必为 $\mathcal{R}$ 的**极点**（反证：若 $S_i=\frac{Y+Z}{2}$，$Y,Z\in\mathcal{R}$，
则两个约束在 $Y,Z$ 上取等，只能 $Y=Z=S_i$）。这种几何很常见：**干扰源大致落在基线延长线上/检测点沿视线排列**时就会出现。

**复现**（`review/out_repro.txt`，两检测点、源在两检测点之间，完全物理可实现）：

```
S1=(0,0) θ=0°, S2=(600,0) θ=180°
原实现: status=degenerate  D=None            ← 完全没有结果
真值  : status=bounded     D=600.00 m  area=3141.9 m²   （区域=以基线为长的"透镜"）
修复后: status=bounded     D=600.00 m
```

**影响面**（`review/out_weight.txt`，4000 组真实场景：源在靶区内、2–5 个能收到信号的检测点）：

| 量 | 数值 |
|---|---|
| 有界算例数 | 3478 |
| 其中"某检测点是真顶点" | 48（**1.38%**） |
| 这些算例里原实现出错 | **48/48**：44 例返回 `degenerate`（无直径），4 例直径**偏小**（中位误差 68%，最大 86%） |
| 修复后出错 | 0 |

**危害**：返回"无直径"会让下游（问题 3/4 的搜索半径）直接失效；直径偏小则会**漏搜**干扰源。
这正是"机器人沿示向度方向逼近干扰源后再测一次"的典型几何（`out_extra.txt`：物理区域直径实为 1050–1300 m，
原实现却报 `degenerate`）。

**修复**：把可行性判据改成半平面形式（在顶点处无角度奇异），并去掉 `d < 1e-9` 特判：

```python
# 预处理：H = [(a, b), ...] 表示 a·X + b <= 0
if all(float(a @ X + b) <= tol for (a, b) in H):
    cand.append(X)
```

### 2.3 Bug 2（严重）：无界区域被报成"有界"或"空集"

`region_from_bearings()` 只枚举**边界直线交点**。当所有示向度两两夹角 $\le2\varepsilon$ 时，
$\mathcal{R}$ 是**无界**楔形区域：

* 若它还有 $\ge3$ 个有限顶点（如 3 个近平行检测点），代码会把这些顶点的凸包当成整个区域 →
  **报出一个有限的、毫无意义的直径**（`out_repro.txt` 情形 c：报 $D=3639.34$ m，真值 $+\infty$）；
* 若没有有限顶点（单点单示向度），代码报 `"empty"`，**错标为"无数据一致性"**（情形 e；真值是无界楔）。

**正确判据（建议直接写进论文）**：$\mathcal{R}$ 无界 $\iff$ 存在方向 $d$ 与所有示向度夹角 $\le\varepsilon$
$\iff$ 所有示向度两两夹角 $\le 2\varepsilon$。

**修复**（$O(k^2)$，$k\le20$）：把每个示向度的两个端点 $\theta_i\pm\varepsilon$ 作为候选方向逐一检验：

```python
rec = None
for th in svds:
    for d in ((th - err) % 360.0, (th + err) % 360.0):
        if all(abs(ang_diff(d, t)) <= err + 1e-9 for t in svds):
            rec = d; break
    if rec is not None: break
# rec is not None  ->  status = "unbounded"（直径记 +inf，另报 recession 方向与已知有限顶点）
```

注意：**有界判据只在区域非空时才可用**。反例：$S_1=(0,0),\theta_1=0^\circ$、$S_2=(0,10),\theta_2=2.05^\circ$
时两楔夹角 $>2^\circ$ 但区域其实为空（两个楔"错开"了）。因此正确顺序是：先判空 → 再判无界。

### 2.4 其它问题

1. **自检不变量太弱**（`tests/selftest_p1.py`）：
   * I1"真值在区域内"**近乎恒真**：算例生成时示向度=真方位角+$\pm1^\circ$ 内误差，真值天然落在交集里；
     它无法发现"区域被算大了"（例如把半角误写成 $2^\circ$，I1 依然通过）。
   * I2/I3/I4 都是**同一份代码的自洽性**（凸性、直径=暴力枚举、覆盖=定义），发现不了漏顶点、漏区域。
   * I5 只允许 $0<D<200$ m，会把"合法但很大"的区域误判为失败。
   * 生成器强制"良态"（方位间隔 $\ge25^\circ$、张角 $\le140^\circ$），**两个 bug 恰好都在它不生成的区域里**。
   * 建议补：与独立实现（半平面裁剪）逐算例对比；对抗算例集（近平行 / 源在基线 / 检测点沿视线 / 单点 / 数据不一致）。
2. `clip_halfplane()` 是**死代码**（函数头注释却说用半平面裁剪），且 `if i + 1 >= n: break` 是空判断。
   建议二选一：真用裁剪做实现，或删掉该函数并改注释。
3. `"empty"` 的提示语把"无交集"和"无界"混在一起（§2.3）。
4. `truth_inside_region` 复用的是角楔判据而非点在多边形内（凸性下等价，可用），但它检验的是**生成器**而非算法。
5. 精度：输出统一 `round(...,4)`，与暴力枚举比较时容差取 `1e-3` 是合理的；但内部比较请用全精度（现实现已如此）。
6. 建议补一列 `min_enclosing_radius_m`（最小包围圆半径）与 `covered_by_diameter_circle`，
   供问题 3/4 直接调用（搜索半径应该用 $r^\*$）。

### 2.5 最小修补清单（**已实施，见 §6**）

| # | 位置 | 改动 |
|---|---|---|
| 1 | `region_from_bearings` 可行性判据 | 角度判据 → 半平面判据 `a@X + b <= tol`；删除 `if d < 1e-9` 特判 |
| 2 | `region_from_bearings` 开头 | 增加 recession 方向判据，返回 `"unbounded"` |
| 3 | `analyse()` | 新增 `unbounded` 分支（报 $+\infty$、recession 方向、已知有限顶点，不给直径） |
| 4 | `analyse()` 返回值 | 增加最小包围圆半径/圆心 |
| 5 | `selftest_p1.py` | 增加独立参考实现对比 + 对抗算例集 |

实施方式：`src/p1_intersection.py` 已按 1–4 重写（并补上 `region_by_clipping` 独立实现、
旋转卡壳直径、最小包围圆）；自检逻辑在 `src/p1_selftest.py`（`tests/selftest_p1.py` 为入口）。
`review/p1_fixed.py` 保留为当时的补丁快照，`P1_MODULE=p1_fixed python verify_p1.py` 仍可复算。

---

## 3. 问题 2 应该怎么做

### 3.1 信息结构：一次检测之后，"候选区域"是扇环

设第一个检测点 $S_1$，测得示向度 $\theta_1$（误 $\le1^\circ$）。由附录 2(2)(9)（有效接收半径 $R\in[1000,1500]$ m、
近场 5 m）与靶区（半径 1800 m）可得真源的**可行域**：

$$
\mathcal{A}=\Big\{\,S_1+t\,(\cos\delta,\sin\delta):\
\ t\in[t_{\min},t_{\max}],\ |\delta-\theta_1|\le1^\circ\,\Big\}
$$

其中 $t_{\max}=\min(1500,\ \text{靶区边界})\)，$t_{\min}=5$ m。**这就是"第一个检测点给出的候选区域"**（扇环），
也决定了第二个检测点的取址必须对 $t$ **稳健**。

### 3.2 用什么度量"定位效果好"？三个度量及其闭式关系

设 $d_1=|S_1G|,\ d_2=|S_2G|$，$\gamma$ 为在**干扰源处**两射线的夹角（交会角），
$\Delta\theta=\theta_2-\theta_1$（两条**读数**之差）。

| 度量 | 闭式 | 校验 |
|---|---|---|
| 线性化定位 RMS（delta 法，$\sigma_\theta$ 为示向度标准差） | $\displaystyle \mathrm{RMS}=\sigma_\theta\frac{\sqrt{d_1^2+d_2^2}}{\lvert\sin\Delta\theta\rvert}$ | 有限差分 Jacobian、蒙特卡洛（2 万次）、解析三法一致（1% 内） |
| 定位区域面积 | $\displaystyle S\approx\frac{4\tan^2\varepsilon\; d_1d_2}{\lvert\sin\gamma\rvert}$ | 与精确多边形面积误差 < 1% |
| 定位区域直径 | $\displaystyle D\approx\frac{2\tan\varepsilon\ \sqrt{d_1^2+d_2^2+2d_1d_2\lvert\cos\gamma\rvert}}{\lvert\sin\gamma\rvert}$ | 误差 < 1% |

> 注意两个常见错误（我们实测过）：
> ① 用 $\sigma_\theta d_2/\lvert\sin\phi\rvert$（$\phi$ 为 $S_1$ 处视视角）会**低估 2–3 倍**（`out_formula.txt`）；
> ② 用"面积 $\propto d_1d_2/\sin\gamma$"虽然对，但**面积最优与直径最优不完全等价**，论文里要说明选哪个作为目标。

**推荐**：主目标取 **定位区域直径 $D$**（它直接决定搜索/清除代价，且与问题 1 的结论无缝衔接），
以 RMS/面积作为对照指标——我们的数值实验显示两种准则给出的最优视角只差 5–10°，结论稳健（§3.5）。

### 3.3 目标函数与约束：为什么**必须**加约束

若只写 $\min_{S_2} J(S_2)$，问题**不适定**（`out_wellposed.txt`）：

* 已知源距 $t$ 时，RMS 随基线 $b=|S_1S_2|$ 单调下降（$b=100,200,400,800$ m 时最优 RMS
  $=90.7,44.6,20.8,8.06$ m，最优视角 $\phi^*=79^\circ,69^\circ,49^\circ,1^\circ$）——
  $b=t,\ \phi\to0$ 即"S2 直接站到干扰源上"，是**退化最优解**；
* 源距未知、对 $t\in[300,1500]$ 取最坏情形时，最坏 RMS 仍然随 $b$ 单调下降（$b=200\to1200$：159→21 m）。

**因此必须显式写出约束**（这本身是本题的建模内容，也是拉开差距的地方）：

| 约束 | 形式 | 依据 |
|---|---|---|
| C1 移动预算 | $\lvert S_1S_2\rvert\le B=v\,T_{\text{剩余}}-\Delta_{\text{保留}}$ | 5 m/s；问题 3/4 有 20 min 现实预算 |
| C2 可检测性 | $d(S_2,\hat G)\le R_{\min}=1000$ m（保守）；或"$S_2$ 取在可行域内侧"使 $d_2\le d_1$（因 $R\ge d_1$，则必有信号） | $R\in[1000,1500]$ 未知且接口不返回 |
| C3 有界性/良态性（硬） | $\lvert\Delta\theta\rvert>2^\circ$，工程上取 $\ge20^\circ\sim30^\circ$ | 否则定位区域无界（§1.3） |
| C4 靶区 | $S_2$ 在半径 1800 m 圆域内 | 题面 |
| C5（问题 4 扩展） | 避开已知干扰源/已清除区域、考虑定向源覆盖角 | 附录 |

**最优解的结构**：C1 通常起作用（取等号），此时视角 $\phi^*$（$S_1\to G$ 与 $S_1\to S_2$ 的夹角）随 $B$ 变化：

| $B$ (m) | 200 | 400 | 600 | 800 | 1000 | 1200 |
|---|---|---|---|---|---|---|
| 极小极大准则 $\phi^*$（RMS） | 79° | 67° | 57° | 46° | 36° | 26° |
| 极小极大准则 $\phi^*$（区域直径 $D$） | 75°(b=300) | 65°(b=500) | 55°(b=700) | 40°(b=900) | 30°(b=1100) | 30°(b=1300) |
| 最坏 RMS (m) | 159 | 78 | 50 | 36 | 27 | 21 |

**可写进论文的规则**：

* 若对源距有估计 $\hat t$（例如 $\hat t=(t_{\min}+t_{\max})/2$ 或第一次检测后的最小二乘估计），
  经典最优是**正交交会** $\gamma\approx90^\circ\iff b\cos\phi\approx t$；
* 源距完全未知时用极小极大：把上表拟合成 $\phi^*(B)\approx\arccos(\hat t/B)$（$\hat t$ 取最坏端 1500 m 时退化为表中数值），
  或直接查表；
* **绝对不要**沿示向度方向逼近后再测（$\Delta\theta\to0$，区域无界/退化）——这是 §2.2 的几何，
  也是"机器人直觉上最自然、但数学上最差"的做法。

### 3.4 候选区域的几何描述

在 $S_1$ 的局部极坐标下（$\theta_1$ 方向为 $0^\circ$），第二检测点候选区域是**两个对称的"翼状"扇环**：

$$
\Omega=\Big\{\,S_1+r\,(\cos(\theta_1\pm\varphi),\ \sin(\theta_1\pm\varphi)):\
r\in[r_{\min},B],\ \varphi\in[\varphi_{\min},\varphi_{\max}]\,\Big\}
\ \cap\ \text{靶区}\ \cap\ \{d(S_2,\hat G)\le1000\}
$$

* 排除**前/后窄锥**（数值上 $b=700$ m 时 $|\varphi|\lesssim10^\circ$ 或 $\gtrsim168^\circ$ 会出现
  $J_{\max}=+\infty$：存在某个可能的源位置/误差组合使两次示向度互不相容或定位区域无界）；
* 由 $J_{\max}$ 数值图（`out_q2.txt`）可见：$b=700$ m 时 $\varphi\in[30^\circ,90^\circ]$ 内
  $J_{\max}$ 只在 **234–298 m** 的很窄区间内浮动（存在很宽的最优平台），而 $\varphi=10^\circ$ 时 1248 m、
  $\varphi=145^\circ$ 时 994 m——**故工程上可把 $\Omega$ 取成 $\varphi\in[30^\circ,75^\circ]$（左右对称），稳健、易实现**；
* 若要"严格最优集合"，取水平集 $\Omega_\epsilon=\{S_2: J(S_2)\le(1+\epsilon)J^*\}$（`review/q2_design.py` 已实现）。
* 推荐单点（若只能给一个）：$r=B$、$\varphi=\varphi^*(B)$，取左/右两侧中使 $\hat t$ 更接近 $b\cos\varphi$ 的一侧。

### 3.5 序贯版本与问题 3/4 的衔接

1. 第一次检测得 $\theta_1$ → 按 §3.4 选 $S_2$（**横向平移**，不要沿 $\theta_1$ 逼近）；
2. 在 $S_2$ 检测：若 `no_signal` → 源在有效接收半径外（Q4 还可能是定向覆盖角外），
   沿 $\theta_1$ 前移一个步长重测；若 `near` → 直接 `/clear`；若 `direction` → 用问题 1 的算法求区域直径/最小包围圆；
3. 搜索/清除半径用**最小包围圆半径 $r^\*$**（不是 $D/2$），搜索中心用区域重心；
4. 每条频道只定位一次；未收敛的频道留给后续航路（信息驱动的 TSP/在线决策）；
5. Q4 中"测不到信号"有三种原因（无该频道 / 超接收半径 / 不在定向覆盖角内），
   而 §1.3 的"有界性判据"和 §3.2 的度量可直接复用来判定"这次测量是否有效"。

---

## 4. 论文写作建议（问题 1、2 部分）

* 问题 1：给出**定义 → 等价半平面表示 → 两种算法与复杂度 → 退化情形判据 → 直径算法 → 覆盖判定定理 → 反例 → 最小包围圆修正**。
  一张"示向度夹角 vs 定位区域直径"的图（体现病态放大），一张覆盖/不覆盖对比图。
* 问题 2：给出**可行域（扇环）→ 度量（RMS/面积/直径三式，含推导或数值校验）→ 目标与约束（说明为何必须加约束）→ 最优性条件（$\gamma\approx90^\circ$、$\lvert\Delta\theta\rvert>2^\circ$）→ 候选区域（翼状扇环 + 水平集）→ 数值算例表 → 与问题 3/4 的接口**。
* 明确写出"误差有界（$\pm1^\circ$）而非高斯"这一点：它使**区域尺寸**成为比 GDOP 更可靠的度量
  （我们实测线性化 GDOP 与真实蒙特卡洛 RMS 比值 1.75–3.5，见 `out_weight.txt`）。

---

## 5. 复现方式与文件清单

```powershell
cd F:\project\Mathemetical_modeling_202609\B_locator\review

python verify_p1.py                    # 原实现 vs 半平面裁剪参考（1800 组算例）→ 退出码 1 表示发现不一致
$env:P1_MODULE='p1_fixed'; python verify_p1.py    # 修复版回归 → 应为 0
python repro_min.py                    # 两类 bug 的最小复现（5 个手算算例）
python bug_weight.py                   # bug 命中率 + GDOP 适用性
python extra_checks.py                 # 已发布 5 算例不受影响 + 物理可容许区域尺寸
python counterexample_q1.py            # 第二小问：对称三点反例
python triangle_search.py              # 第二小问：定位区域为三角形的实用反例（Thales 检验）
python q2_design.py                    # 问题 2：J_max/J_avg 网格、闭式近似检验、无界性判据
python q2_formula.py                   # 问题 2：精度公式三重校验 + 最优视角表
python q2_wellposed.py                 # 问题 2：无约束时最优解发散（说明必须加约束）
```

| 文件 | 内容 |
|---|---|
| `p1_fixed.py` | 修复版问题 1 实现（接口兼容，可直接替换 `src/p1_intersection.py`） |
| `verify_p1.py` | 独立参考实现（半平面裁剪 + scipy 仲裁）与回归测试 |
| `repro_min.py` / `out_repro.txt` | 两类 bug 的最小复现 |
| `bug_weight.py` / `out_weight.txt` | bug 在真实场景中的命中率、GDOP 适用性 |
| `extra_checks.py` / `out_extra.txt` | 已发布算例不变性 + 物理区域尺寸 |
| `counterexample_q1.py`, `triangle_search.py` / `out_counterexample.txt`, `out_triangle.txt` | 第二小问反例 |
| `q2_design.py`, `q2_formula.py`, `q2_wellposed.py` / `out_q2.txt`, `out_formula.txt`, `out_wellposed.txt` | 问题 2 的数值支撑 |
| `debug_p1.py` | 失败算例的分case诊断（含 scipy `HalfspaceIntersection` 第三方仲裁） |

> 环境备注：本机 `B_locator\data`、`B_locator\scripts`、`B_locator\tests`（以及 `A_drying\docs` 等）
> 在**子进程**里枚举/读取会被拒绝（`Get-ChildItem` / `os.path.exists` 均失败），
> 因此 `extra_checks.py` 把 5 个已发布算例的数据内嵌；这不影响算法结论，但建议检查这些目录的 ACL。

---

## 6. 已实施的修改（本次交付）

### 6.1 问题 1

| 文件 | 变更 |
|---|---|
| `src/p1_intersection.py` | 重写。① 顶点可行性改用半平面判据（`wedge_halfplanes` + `a·X+b≤0`），删除 `d<1e-9` 特判 → 修 Bug 1；② 新增 `region_is_unbounded()` 精确判据，`analyse()` 新增 `unbounded` 分支 → 修 Bug 2；③ 新增 `region_by_clipping()` 独立实现（含正确的 Sutherland–Hodgman 交叉判据）、`rotating_calipers()`（与暴力枚举互相校验）、`min_enclosing_circle()`（Jung 界），`analyse()` 增出 `min_enclosing_center/radius_m`、`min_circle_over_half_diameter`；④ `main()` 汇总增加 `n_unbounded/n_degenerate/n_empty` 等 |
| `src/p1_selftest.py`（新） | 自检主体：T1 直径三法一致；T2 两套独立区域算法逐算例对比；T3 覆盖判定 == Thales == 顶点最大距离；T4 有界性判据 vs 裁剪参考；T5 对抗算例期望状态/直径（含"检测点作顶点"与"对称三点不覆盖"）；T6 最小包围圆（含等边三角形取到 Jung 上界）；T7 真值必须落在区域内（点在凸多边形内测试）；T8 已发布 5 算例回归（数据内嵌）；T9 生成器→命令行→结果文件全流程 |
| `tests/selftest_p1.py` | 改为入口薄封装（转发到 `src/p1_selftest.py`） |
| `README.md` | 更新问题 1 的模型、两条理论判据、第二小问结论、对抗算例表、问题 2 的设计流程与结果表、运行命令与输出清单 |

### 6.2 问题 2

| 文件 | 内容 |
|---|---|
| `src/p2_siting.py`（新） | 可行域扇环 `sector_bounds/feasible_samples`；三种度量 `rms_linear/area_closed/diam_closed`（附 `geometry()`）；候选点评价 `evaluate_candidate`（C1–C4 约束 + 最坏情形/均值目标）；设计器 `design_second_point`（粗网格 + 局部细化）；候选区域 `candidate_region`（连通域包络 + 全部水平集 + 每条半径的可用视角带）；禁入锥 `no_go_cone`；闭式规则 `analytic_phi_star`；`--selfcheck`（公式/约束/流程，7 项全通过）；`--table`（论文用表）；3 张图输出到 `out/p2/` |

### 6.3 本次回归证据

| 命令 | 结果 |
|---|---|
| `python src/p1_intersection.py <dir>` | 已发布 5 算例 D/面积/覆盖判定与旧版**完全一致**（见 `out_newmodule.txt` 与 README 表） |
| `python review/verify_p1.py`（模块 = 新的 `src/p1_intersection.py`） | **failures: 0**，1797 组算例；假有限直径 0 例；有界算例 D/A 最大相对误差 5.9e-6 / 7.3e-6（仅输出四舍五入）→ `review/out_newmodule.txt` |
| `python src/p1_selftest.py` | 通过 12，失败 0，跳过 1（T9 因沙箱禁止子进程读 `scripts/`；正常环境可跑）→ `review/out_selftest.txt` |
| `python src/p2_siting.py --selfcheck` | 7 项全通过（面积公式误差 ≤0.71%、直径 ≤0.42%、RMS vs 蒙特卡洛 ≤1.8%）→ `review/out_p2_selfcheck.txt` |
| `python src/p2_siting.py --table` | 两种指标的最优视角一致（见表）→ `review/out_p2_table.txt` |
| `python src/p2_siting.py --x1 0 --y1 0 --theta1 30 --budget 700 --out out/p2` | $S_2=(644.4,-273.5)$，$\varphi^\*=-53^\circ$，$J^\*=233.7$ m，候选 $\varphi\in[-75^\circ,75^\circ]$（$r=700$ m），禁入锥 $\lvert\varphi\rvert\le5^\circ$ / $\lvert\varphi\rvert\ge155^\circ$ → `review/out_p2_run.txt` + 3 张图 |

### 6.4 追加：把"走多远"内生化（时间最优）——修正 §3.3 的"硬预算"写法

§3.3 把移动距离写成硬上界 $B$，导致最优解永远贴在 $B$ 上，"距离"其实没有被建模。
追加的实现把时间当资源，直接对**总耗时**极小化（`metric="time"`，`budget=None`）：

$$T(r,\varphi)=\frac{r}{v}+5+\frac{|S_2-c|}{v}+\frac{\pi r^{*2}/(2R_{\text{clear}})}{v}+5$$

其中 $r^\*$ 是定位区域的最小包围圆半径（问题 1 的算法给出），行距 $2R_{\text{clear}}=40$ m
保证圆域内任一点到最近航迹 ≤ 20 m。评价仍对可行域样本 $G$ 与 $e_2$ 取最坏/平均。

| 结论 | 数值（S1=(0,0)、θ1=30°、源距未知 5–1500 m、r ≤ 1400 m） |
|---|---|
| 时间 min-max 最优 | $r^\*=1060$ m，$\varphi^\*=-29^\circ$，$T^\*=448$ s（内点最优） |
| 时间 mean 最优 | $r^\*=720$ m，$\varphi^\*=+27^\circ$，$E[T]=313$ s（最坏情形 711 s） |
| 纯几何（最坏直径 / RMS） | $r^\*=1400$ / 1336 m（顶到物理上界：该模型里走路不花时间） |
| 走满预算的旧做法 | B=300/500/700/1000 m → 最坏耗时 2864/967/**619**/451 s（比 448 s 差 38%） |
| $T(r)$ 形状 | $\varphi=-29^\circ$ 时在 $r\approx1050$ m 取 445.5 s；$r=150$ m 爆炸、$r=1500$ m 回升到 642.8 s |
| 源距下限灵敏度 | 下限 5→200 m 时 $r^\*$ 恒为 1060 m；400 m 时 1145 m（最坏情形由"近源"切到"远源"） |
| 搜索效率灵敏度 | $\eta=0.5/0.75/1.0$ 下 $r^\*$ 均为 1060 m（只有总耗时变化） |
| 与"单条示向度搜索"对照 | 走廊搜索 610 s vs 两测点 448 s → 第二次测量净省 **27%** |
| 问题 3 含义 | 每目标 75–120 s 时两测点方案不可行（全网格最小 450 s）→ 必须复用粗扫多点交会 |

证据：`review/out_time_study.txt`、`review/out_time_floor.txt`、`out/p2_time/p2_time_optimal_curve.png`；
脚本 `review/study_time_optimal.py`、`review/study_time_floor.py`；
命令行 `python src/p2_siting.py --metric time --budget -1 --r-max 1400`（新增 `--r-max/--reduce/--search-eff/--t-floor`）。
