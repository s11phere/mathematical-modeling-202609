# 参考文献核对说明

核对日期：2026-09-13。输入为用户保存的 <code>B_locator/paper/references</code> 中 7 条候选记录及论文现有 5 条经典文献。主要采用 Crossref 出版商登记元数据核对书目信息；Toussaint 1983 另查作者本人主页和公开论文。未检索到不等于断言文献不存在，但在缺少可靠出处时不纳入正式参考文献。

## 1. 用户提供的 7 条候选文献

| 输入条目 | 核对结论及处理 | 核对依据 |
|---|---|---|
| Torrieri, 1984, *Statistical theory of passive location systems* | 已核实，纳入。作者 Don J. Torrieri；正式卷号采用 AES-20，期号 2，页码 183–198。用于被动定位误差与测站几何的研究背景。 | [Crossref 登记](https://api.crossref.org/works/10.1109/TAES.1984.310439)；[IEEE 原文入口](https://ieeexplore.ieee.org/document/4103919/) |
| Toussaint, 1983, *Solving geometric problems with the rotating calipers* | 已核实，与现有参考文献重复，保留一条。作者页面确认 IEEE MELECON'83、Athens、May 1983；公开稿共 8 页，其内部页号不能直接当作会议录页码。因此删除尚未核实的“83: A10”与原稿中“1–8”的会议页码。 | [作者说明页](https://www-cgrl.cs.mcgill.ca/~godfried/research/calipers.html)；[作者公开稿](https://www-cgrl.cs.mcgill.ca/~godfried/publications/calipers.pdf) |
| Bishop et al., 2010, *Optimal geometry analysis for bearing-only localization in 2D*, 46(2): 378–384 | 输入题名及期页不匹配。同一作者组实际论文为 *Optimality analysis of sensor-target localization geometries*, **Automatica, 2010, 46(3): 479–492**，纳入更正后的真实记录。完整作者为 Adrian N. Bishop、Barış Fidan、Brian D. O. Anderson、Kutluyıl Doğançay、Pubudu N. Pathirana。用于定位几何与精度的背景说明，不作为本文期望直径公式或最优位置数值的直接出处。 | [Crossref 登记](https://api.crossref.org/works/10.1016/j.automatica.2009.12.003)；[DOI 入口](https://doi.org/10.1016/j.automatica.2009.12.003) |
| Galceran & Carreras, 2013, *A survey on coverage path planning for robotics* | 已核实，纳入。第二作者是 **Marc Carreras**，应写 Carreras M，而非 Carreras P。卷期页码 61(12): 1258–1276 正确。用于覆盖路径规划背景，不代替本文的无源证书证明。 | [Crossref 登记](https://api.crossref.org/works/10.1016/j.robot.2013.09.004)；[DOI 入口](https://doi.org/10.1016/j.robot.2013.09.004) |
| Carlsson & Jia, 2020, *Coordinated search and target tracking with uncertain sensing ranges*, INFORMS Journal on Computing | **无法核实，暂不纳入。** 完整题名检索没有返回同题记录；作者、题名及期刊联合检索也未找到匹配记录。输入没有卷、期、页码或 DOI，现有证据不足以恢复确定出处。未擅自用主题近似论文替代。 | [完整题名检索](https://api.crossref.org/works?query.title=Coordinated%20search%20and%20target%20tracking%20with%20uncertain%20sensing%20ranges&rows=5)；[作者、题名、期刊限定检索](https://api.crossref.org/works?query.author=Carlsson%20Jia&query.title=Coordinated%20search%20target%20tracking%20uncertain%20sensing%20ranges&filter=issn%3A1091-9856&rows=10) |
| Choset, 2000, *Coverage of known spaces: The Boustrophedon cellular decomposition* | 已核实，纳入；9(3): 247–253 正确。仅支持胞腔分解这一空间覆盖思路。本文采用闭方格覆盖、尺寸余量和观测相容性判据，并未实现 Boustrophedon 分解，不能写成直接采用该算法，也不能把本文连续无源证明归于该文。 | [Crossref 登记](https://api.crossref.org/works/10.1023/A:1008958800904)；[Springer 入口](https://link.springer.com/article/10.1023/A:1008958800904) |
| Song & Zhang, 2019, *Bearing-only target localization and path planning for directional signal sources*, IEEE TSP, 67(15): 3910–3922 | **无法核实且页码存在冲突，暂不纳入。** 完整题名及作者/期刊/年份限定检索均未返回该文。同一期的 **3922–3937** 页实际登记为 Soldi、Meyer、Braca、Hlawatsch 的 *Self-Tuning Algorithms for Multisensor-Multitarget Tracking Using Belief Propagation*，其起始页与候选记录末页冲突，进一步表明该记录不可靠。未用该无关论文替换引用。 | [完整题名检索](https://api.crossref.org/works?query.title=Bearing-only%20target%20localization%20and%20path%20planning%20for%20directional%20signal%20sources&rows=5)；[作者、题名、期刊、年份限定检索](https://api.crossref.org/works?query.author=Song%20Zhang&query.title=Bearing-only%20target%20localization%20path%20planning%20directional%20signal%20sources&filter=issn%3A1053-587X%2Cfrom-pub-date%3A2019-01-01%2Cuntil-pub-date%3A2019-12-31&rows=5)；[3922–3937 页真实记录](https://api.crossref.org/works/10.1109/TSP.2019.2916764) |

Toussaint 的说明页明确写明，凸多边形直径的旋转卡壳思想由 Michael Shamos 在 1978 年博士论文中提出；Toussaint 命名并推广了该方法。因此不采用候选文件中“旋转卡壳算法原创论文”的绝对归属表述。

## 2. 保留的经典方法文献

原有 5 条全部保留，并核实如下：

| 文献键 | 书目信息 | 证据 |
|---|---|---|
| andrew1979 | Andrew A M. *Another efficient algorithm for convex hulls in two dimensions*. Information Processing Letters, 1979, 9(5): 216–219. | [Crossref](https://api.crossref.org/works/10.1016/0020-0190%2879%2990072-3) |
| toussaint1983 | 见上表；作者公开页面与论文确认。 | [作者页面](https://www-cgrl.cs.mcgill.ca/~godfried/research/calipers.html) |
| sutherland1974 | Sutherland I E, Hodgman G W. *Reentrant polygon clipping*. Communications of the ACM, 1974, 17(1): 32–42. | [Crossref](https://api.crossref.org/works/10.1145/360767.360802) |
| croes1958 | Croes G A. *A method for solving traveling-salesman problems*. Operations Research, 1958, 6(6): 791–812. | [Crossref](https://api.crossref.org/works/10.1287/opre.6.6.791) |
| efron1993 | Efron B, Tibshirani R J. *An Introduction to the Bootstrap*. New York: Chapman & Hall, 1993. | [1993 年版本 Crossref](https://api.crossref.org/works/10.1007/978-1-4899-4541-9) |

## 3. 正文插入点及引用顺序

正文已在以下位置加入背景与方法引用，参考文献按首次出现顺序排列。Andrew、Toussaint、Sutherland–Hodgman、2-opt、bootstrap 的方法引用亦已落实。下列句子说明引用所支持的内容，最终措辞以 LaTeX 正文为准。

1. **问题一模型建立开头**，在“设第 i 个检测点”前加入：  
   被动定位的误差分析需要考虑测量误差与测站几何<code>\cite{torrieri1984}</code>。本文依据题设误差界构造角楔，并用其交集描述可行源位。
2. **问题二模型建立开头**，在“记号与概率描述”之后、坐标定义之前加入：  
   测站与目标的相对几何关系会影响仅测向定位的精度<code>\cite{bishop2010}</code>。本问以定位区域直径评价布点，并在下文给定的先验和近似条件下求取其期望。
3. **问题三 5.3.1(c) 连续覆盖与任务完成判据开头**加入：  
   覆盖路径规划研究如何以有限路径实现连续空间覆盖<code>\cite{galceran2013}</code>，胞腔分解是组织覆盖的一类经典方法<code>\cite{choset2000}</code>。本问采用闭方格及尺寸余量，将实际负观测转化为整格排除依据。

按此方案，首次引用顺序为：

| 编号 | 文献键 | 首次引用位置 |
|---:|---|---|
| 1 | torrieri1984 | 问题一模型建立开头 |
| 2 | andrew1979 | 问题一 Andrew 单调链 |
| 3 | toussaint1983 | 问题一旋转卡壳 |
| 4 | sutherland1974 | 问题一裁剪交叉核验 |
| 5 | bishop2010 | 问题二模型建立开头 |
| 6 | galceran2013 | 问题三连续覆盖小节 |
| 7 | choset2000 | 紧接覆盖综述 |
| 8 | croes1958 | 问题三首次 2-opt |
| 9 | efron1993 | 问题三首次 bootstrap |

## 4. 核对边界

Crossref 的作者、题名、期刊和 DOI 记录为本次主要书目证据。尝试直接访问 Elsevier 出版商页面时得到 HTTP 403；Springer 文章页返回 JavaScript 检查页面，因此没有将这些页面标记为已阅读全文。正文引用仅用于可从可靠记录确认的研究主题和经典方法，不声称已核验付费全文中的具体定理。Toussaint 的作者页面及公开稿已实际读取。

本次候选处理结果为：4 条按可靠出处新增（Torrieri、Bishop 更正记录、Galceran、Choset），1 条与原表重复并合并（Toussaint），2 条无法核实而排除（Carlsson–Jia、Song–Zhang）。最终参考文献共 9 条。
