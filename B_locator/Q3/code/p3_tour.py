"""B 题问题 3：**统一滚动航路**策略（Tour）——"绕圈"与"清除"合成一条动态航路。

为什么需要它（旧两套策略的实测缺陷，详见 `review/p3-tour-design.md`）
------------------------------------------------------------------
* `P3Robot`（期望场贪心）：虚拟时间 5270 s，其中 **29% 是清完源之后的空转**，
  检测 186 次、行程 20.5 km。
* `SweepRobot`（覆盖扫圈）：虚拟时间降到 4243 s，但结构是**"先绕完一圈、再统一清除"**：
  绕圈的 6.4 km 和清除的 5.2 km 是两段互不重叠的路，实测行程 16.8 km，
  是"已知全部源位后的最优航路"（8.8 km）的 **1.92 倍**，其中折返（转角 >120°）
  1.5 km/局。按题目的"平均定位清除时间 = 定位清除总时间 ÷ 清除个数"口径，
  这一半行程全是白走的。

本模块把扫描与清除合成**一条滚动时域的统一航路**：

```
每个决策点重算一次航路，只执行第一个停点，然后重规划
  航路 = ① 环带骨架停点（保证"没有残留源"的可证明完备性，按角向单调推进）
         ↑ 目标（清除 / 定位）用"最便宜插入"插进骨架的空隙里
  目标 = 已定位频道的最新定位区域中心（clear）
         只有一条方位 / 区域无界 / 区域过大的频道（locate，用第二问的 E[D] 代价模型）
```

于是航线天然就是用户描述的**锯齿状一圈**：从原点出发 →（期望场）选第二个检测点、
顺手清掉靠内圈的目标 → 就近切入环带 → 沿一个方向绕一圈、边走边清 →
走完一圈即收工。不会出现"绕完再回头"的长距离折返。

相对旧实现的六个关键修正
------------------------
1. **不再分"绕圈/清除"两个阶段**：骨架停点与目标一起排序，清完一个就地重规划。
2. **环带骨架按角向单调推进**（锁定方向 + 角向游标）：这是"不折返"的结构性保证；
   旧实现每一步都重新贪心选点，导致航路在角向上来回横跳（实测折返 2.5 km/局）。
3. **覆盖判据按频道算**：某点是否值得测，取决于"这个频道在那里是否还可能有
   没被听到的源"，用该频道**真实测过的位置**（`rec.meas_pts`）判定 ——
   清除绕行时顺带做的检测会自动抵扣掉后面的骨架停点，不重复走。
4. **修掉 `visit_stop` 的 gap 判定 bug**：旧实现用"上一个动作的位置"而不是
   "本停点坐标"判断"这个频道在这儿测过没有"，导致整站漏测（实测有源因为
   连续漏测而**永远没被听到**）。
5. **"只有一条方位"的频道不再无脑重测**：只有当"本停点相对上一条视线的张角"
   落在 25°–155° 时才测（否则交会角接近 0，纯属浪费 6 s）。
6. **清除子过程可迭代**：区域无界 / 区域半径过大不再被永久跳过（旧实现在
   `clear_targets()` 里把 r*>600 m 的目标过滤掉，是清除率只有 0.978 的主因），
   而是"逼近中心补方位 → 区域压小 → 覆盖式试探"循环，直到成功或用尽预算。
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from p3_arena import (  # noqa: E402
    ArenaError, R_ARENA, R_CLEAR, R_RECV_MIN, T_CLEAR_FAIL, T_MEASURE, T_SWITCH,
    V_ROBOT,
)
from p3_expect_field import best_refine_point, ray_source_samples  # noqa: E402
from p3_sweep import SweepConfig, SweepRobot  # noqa: E402


# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------
@dataclass
class TourConfig(SweepConfig):
    """在 `SweepConfig`（含 `P3Config` 全部字段）之上追加"统一航路"参数。"""

    # ---- 环带骨架 ----
    cover_rings: tuple = ((1000.0, 8),)
    """骨架候选停点的同心环 ``(半径 m, 点数)``。

    为什么是"小半径 + 稀疏停点"：原点那一次全频道检测已经把 r<=1000 的内圈覆盖了，
    只剩环带 r∈[1000,1800] 要覆盖；半径 ρ 的停点最多覆盖到
    ``1800² + ρ² - 2·1800·ρ·cosΔ <= 1000²`` 的角向半宽 Δ（Δ 越大，环上可以越稀），
    于是

    | 配置 | 环带最大未覆盖 | 覆盖余量 | 单圈弦长 | 含进入段 | 每圈要测的频道数 |
    |---|---|---|---|---|---|
    | 7 点 r=1050 | 968 m | 32 m | 6378 m | 7428 m | 7×N |
    | **8 点 r=1000（默认）** | **943 m** | **57 m** | **6123 m** | **7123 m** | 8×N |
    | 9 点 r=950 | 964 m | 36 m | 5849 m | 6799 m | 9×N |
    | 13 点 r=880 | 969 m | 31 m | 5476 m | 6356 m | 13×N |

    半径越小弦长越短，但停点越多、每站都要把"从没听到过"的频道整批测一遍
    （6 s/频道）。四批共 150 局实测（`python src/p3_tour_sweep.py --rings ...`）：

    | 配置 | 全清局数 | T/N 均值 |
    |---|---|---|
    | 7 点 r=1050 | 146/150 | 333.2 s |
    | **8 点 r=1000（默认）** | **149/150** | **332.5 s** |
    | 9 点 r=950 | 149/150 | 333.3 s |

    r=1000/8 点同时拿到最好的清除率、最低的 T/N，以及最大的覆盖余量（57 m），故为默认。
    """
    cover_grid_step_m: float = 25.0     # 覆盖度评估网格步长
    cover_slack_m: float = 0.0          # 覆盖判据余量（>0 更保守）
    ring_min_advance_rad: float = 0.06  # 角向单调推进的最小步长（约 50 m）
    entry_tie_m: float = 0.0
    """入口选择的"并列"阈值：航路长度相差不超过它就算并列，此时才按信息方向挑。

    取 0 的含义是"**优先就近进入**；只有长度**完全相等**（机器狗正停在原点、
    8 个入口一样远）时，才用信息方向打破僵局" —— 这正好对应用户指出的现象：
    进场位置之所以"固定"，就是因为原点扫描之后机器狗还在原点，
    `atan2(0,0)` 恒为 0。阈值放大到 250/400 m 会把"信息方向"的权重放大成
    主导项，实测反而变差（常规随机 327.8 → 327.9 → 332.2）。"""
    entry_select: bool = True           # 消融对照：False = 旧行为（用当前位置极角当游标）
    cover_duty_frac: float = 0.95       # 目标停点半径 >= 骨架半径×它时，代劳覆盖检测

    # ---- 路点合并与排序 ----
    merge_radius_m: float = 250.0       # 目标这么近的骨架停点直接省掉
    route_mode: str = "polish"          # insert（只做最便宜插入）| polish（+2-opt，骨架不倒序）
                                        # | tsp（完全自由 NN+2-opt，消融对照）
    locate_max_detour_m: float = 260.0  # 定位路点的绕行超过它就本轮不排（等航路自己给方位）
    locate_force_after: int = 2         # 连续跳过这么多轮之后强制排入（避免永远排不进）
    clear_max_detour_m: float = 1e18    # **清除路点一律排进航路**（这个上限只是记录用）
    """清除目标绝不允许"因为绕行太远就不排"。

    实测（`p3_paths` 场景 C）：ch6 在环带 (0,-1000) 处就拿到了第二条方位、
    $r^*=42$ m，完全可以就地清掉；但当时"最便宜插入"的额外代价是 2382 m，
    超过了旧的 1500 m 硬上限，于是它被踢出航路，一直留到收尾阶段的
    `clear_leftovers` —— 那时机器人已经跑到场地另一头（1051,1295），
    再横穿 3.4 km 回去清它。**"绕行大"只应该影响排序，绝不能变成"不清"**。
    """

    # ---- 期望场（第二问 E[D] 模型）作为可选项 ----
    field_min_pending: int = 1
    """只有"待定（只有一条方位的）频道数 >= 它"时才动用期望场/批量合并定位。

    期望场的好处是"一次移动定住好几个源"，也**顺带把"走多远拉基线"与
    "定位精度差要多扫多少面积"放在同一个代价里权衡**（`best_refine_point`
    的 cost 里含 $\\pi(E[D]/2+20)^2/(2R_{clear})/v$）。所以它不是"为了精度可以
    无限跑远"—— 只是因为"基线短 ⇒ $r^*$ 大 ⇒ 后面搜索面积按平方增长"，
    权衡下来它的最优点常常在几百米到 1 km 之间。

    待定频道很少时改用 `_cheap_locate_point`（候选半径压到
    ``short_locate_cap_m``）这一档**实测是亏的**（四类情景 T/N 全部更差：
    常规随机 330.0→344.4、外圈环带 359.6→371.7、在线真源 394.6→426.3），
    所以默认取 1（= 始终允许期望场）。真正解决"为单个目标跑很远"的是
    `locate_patience_stops`（环形航路本来会给的方位就先等着）与
    `locate_max_detour_m`（绕行太大的定位点本轮不排）。
    """

    # ---- 主动"防过期"补测（默认关闭：实测在 4 类情景上都略亏，见 §"清除时机"）----
    risk_locate: bool = False
    risk_lookahead: int = 3             # 往后看几个骨架停点
    risk_min_lost: float = 0.5          # 先验里有这么大比例的源位"往后几个站都听不到"就该补测
    risk_step_m: float = 300.0          # 补测只走这么远（小步）
    risk_max_per_stop: int = 1
    sector_clear_m: float = 0.0
    """"刚走过的扇区里已经能清的目标"的就地清除半径（0 = 关闭）。

    这两个机制（`risk_locate` / `sector_clear`）是照"每个角度只经过一次、
    所以覆盖到的目标要尽快清"的思路写的，但四类情景实测都是**略亏**
    （常规随机 T/N 334.6 → 327.5、外圈环带 4575 s → 4085 s、行程 16.1 km → 13.4 km
    都是关掉更好）。真正解决"该清没清"的是 `offroute_clear`（见下）。"""

    # ---- "不在行进方向上就地补测并清除" ----
    offroute_clear: bool = True
    wait_angle_min_deg: float = 30.0
    """夹角粗筛：第一条方位与"本站->下一站"方向的夹角小于它就直接等下一站。

    用户的直觉（"夹角小就等、夹角大就立刻走一小步定位清除"）方向完全正确，
    但**只按夹角判太粗**：夹角大其实是常态，而"拐回来清"到底多花多少，
    取决于源离哪一站更近。所以夹角在这里只当粗筛，真正的判据是
    `offroute_clear` 里用射线先验直接算的"两种做法的额外绕行"
    （实测：只用夹角判 → 常规随机 330 → 350、外圈环带 4085 → 5238 s；
    换成绕行比较之后才真正有收益）。
    """
    offroute_step_m: float = 320.0      # 就地补测只走这么远
    offroute_margin_m: float = 60.0     # "现在清"要比"等下一站"至少省这么多米才做
    offroute_max_thi_m: float = 900.0
    """射线先验外径超过它就放弃判断。

    判断依赖"源大致在哪"，而 ``t_hi``（射线在靶区内的长度）越长，先验越摊得开、
    估计越不可靠 —— 实测不加这条闸门时，常规随机会从 330 掉到 350 s
    （对着一堆"其实在 1.4 km 外"的源白跑 320 m 的补测步）。
    ``t_hi`` 小（源被靶区边界卡住、不可能远）时判断才可信。
    """
    offroute_max_per_stop: int = 1
    offroute_max_dist_m: float = 450.0
    """源位先验的加权平均距离超过它就放弃"现在清"。

    单条方位对源距几乎没有分辨力（只有射线先验），源越远估计越不可靠；
    而且"现在清"的价值来自"顺手"，源太远时顺手也顺不了。
    """

    # ---- 清除 ----
    probe_enter_r_m: float = 110.0      # r* 小到它就进入覆盖式试探
    probe_max_radius_m: float = 300.0   # 试探圆域半径上限（区域更大就先补方位）
    probe_max_points: int = 150
    clear_max_iters: int = 6
    approach_eps_m: float = 25.0        # 与既有测量点的最小间隔
    fail_cooldown: int = 2              # 清除失败后冷却几个停点
    big_r_m: float = 1200.0             # r* 超过它就不"去区域中心"，改用横向定位点
                                        # （两条近似平行的方位会把最小包围圆撑到几公里，
                                        #   中心甚至落在靶区外 —— 旧实现会真的走过去，
                                        #   实测有一局为此多走 13.5 km、多花 2700 s）

    # ---- 定位路点（"只有一条方位"的频道）----
    locate_mode: str = "stale"          # always | stale | never
    locate_stale_stops: int = 3
    locate_patience_stops: int = 6
    """只有一条方位的频道，最多"等"环形航路几个停点。

    环形航路每个角度只经过一次，所以一条只有单方位的频道**通常会在它所在扇区的
    下一个骨架停点上拿到第二条方位** —— 白等就行，专门跑一趟是纯浪费
    （实测 `p3_paths` 场景 D 里那些"偏离预定路线的尖锐拐角"就是这么来的：
    为了给 ch9 补方位，从 (−1716,58) 往靶区里折了 1020 m，而环形航路本来
    就会在 (1000,0) 给它第二条方位）。
    因此：先按 `_lost_fraction` 判断"环形航路还会不会再听到它"，
    只有确实听不到了、或者已经等了 `locate_patience_stops` 站，才专门去定位。
    """
    locate_travel_cap_m: float = 1100.0
    locate_bearing_cap_m: float = 700.0  # "回到上一条方位的检测点附近横向补测"的半径上限
    locate_radii: tuple = (150.0, 300.0, 500.0, 750.0, 1000.0)
    short_locate_cap_m: float = 420.0
    """`_cheap_locate_point` 的候选半径上限（"单点定位只走一小步"）。"""
    cheap_locate_angles: tuple = (55.0, 80.0, 105.0)  # 小步横向补测的候选夹角（度）
    min_cross_deg: float = 25.0         # 单方位频道：张角小于它就不值得重测

    # ---- 开场定点（期望场第二检测点）----
    initial_rounds: int = 3             # 原点附近最多做几轮"合并定位 + 顺手清除"
    initial_move_growth: float = 2.0    # 每轮把移动上限放宽这么多倍
    initial_locate_max_move_m: float = 350.0   # 单轮定位最多走多远
    """开场定点单轮的最远移动距离。

    第二问的 E[D] 代价模型用的是"源位沿射线、按面积均匀"的先验，其**中位源距约 1 km**，
    于是对"其实就在原点附近"的那些源，它会给出一个 1 km 开外的第二检测点。
    实测（30 局 × 3 种情景）把它从 1300 m 收到 350 m：

    | 情景 | 1300 m | **350 m** |
    |---|---|---|
    | 常规随机（新种子批） | T/N 324.4 | **312.5** |
    | 中心密集 12 源 | T/N 282.1（还漏 1 局） | **224.9（30/30 全清）** |
    | 外圈环带 12 源 | T/N 364.2 | 365.5（打平） |

    原因：近处的源只要在 300–400 m 外测一条方位就能定得很准；跑 1 km 去测既费时，
    又把它后面的清除路线拉乱（"先清较靠近原点的目标"靠的是**顺路**，不是专门跑一趟）。
    """
    initial_clear_radius_m: float = 900.0      # 开场顺手清除的半径（"先清近处的源"）

    # ---- 结束 ----
    max_stops: int = 80
    min_stop_budget_s: float = 15.0


# --------------------------------------------------------------------------
# 机器狗
# --------------------------------------------------------------------------
class TourRobot(SweepRobot):
    """统一滚动航路（环带骨架 + 目标最便宜插入 + 逐站重规划）。"""

    def __init__(self, arena, cfg: TourConfig | None = None, base=None, log=None):
        super().__init__(arena, cfg or TourConfig(), base=base, log=log)
        self._ag = None                 # 环带评估网格缓存
        self._unsafe_cache = {}         # (ch, len(meas_pts)) -> 未排除掩码
        self._ring = None               # 骨架（(角度, 半径) 按角度排序）
        self.ring_dir = 0.0             # 锁定的绕行方向 ±1
        self.ring_cursor_a = None       # 角向游标（上一个骨架停点的极角）
        self.ring_served = set()        # 已经被"顶替并完成覆盖职责"的骨架停点（角度键）
        self.stop_seq = 0
        self.last_stop_xy = None
        self.n_cover_stops = 0
        self.n_locate_stops = 0
        self.n_clear_iter = 0
        self._hold_until = {}
        self._locate_skips = {}
        self._last_bearing_stop = {}
        self._prev_stop_a = None
        self.tour_log = []

    # ------------------------------------------------------------------
    # 台账
    # ------------------------------------------------------------------
    def pending(self):
        return [int(ch) for ch, rec in self.recs.items() if not rec.cleared]

    def unheard(self):
        return [int(ch) for ch, rec in self.recs.items()
                if not rec.cleared and rec.n_bearings == 0]

    def heard_pending(self):
        return [int(ch) for ch, rec in self.recs.items()
                if not rec.cleared and rec.n_bearings > 0]

    def _n_cleared(self):
        return sum(1 for r in self.recs.values() if r.cleared)

    def on_hold(self, ch):
        return self.stop_seq < self._hold_until.get(int(ch), -1)

    def hold(self, ch, stops=None):
        self._hold_until[int(ch)] = self.stop_seq + int(
            self.cfg.fail_cooldown if stops is None else stops)

    def add_bearing(self, ch, x, y, svd):
        reg = super().add_bearing(ch, x, y, svd)
        self._last_bearing_stop[int(ch)] = self.stop_seq
        self._hold_until.pop(int(ch), None)
        return reg

    def region_info(self, rec):
        """当前（或最近一次）有界区域 ``{'center','radius','poly','status'}``。"""
        if rec.n_bearings >= 2:
            reg = self.region(rec)
            if reg.get("status") == "bounded":
                return {"center": tuple(reg["min_enclosing_center"]),
                        "radius": float(reg["min_enclosing_radius_m"]),
                        "poly": [tuple(v) for v in reg.get("vertices", [])],
                        "status": "bounded", "n_bearings": rec.n_bearings}
        if rec.last_bounded is not None:
            c, r, n = rec.last_bounded
            return {"center": tuple(c), "radius": float(r), "poly": None,
                    "status": "fallback", "n_bearings": n}
        return None

    # ------------------------------------------------------------------
    # 覆盖：哪些环带格点"还可能藏着从没听到过的源"
    # ------------------------------------------------------------------
    def annulus_grid(self):
        if self._ag is None:
            step = float(self.cfg.cover_grid_step_m)
            R = R_ARENA
            xs = np.arange(-R, R + 1e-9, step)
            GX, GY = np.meshgrid(xs, xs)
            rr = np.hypot(GX, GY)
            m = (rr <= R + 1e-9) & (rr >= R_RECV_MIN - 1e-9)
            self._ag = (GX[m].copy(), GY[m].copy())
        return self._ag

    def unsafe_of(self, ch):
        """频道 ``ch`` 仍然"没被排除"的环带格点掩码。

        判据：该格点到频道 ``ch`` **真实测过的任一位置**的距离 <= 有效接收半径下界
        （1000 m）⇒ 若那里真有源，当时就会被听到 ⇒ 可以排除。
        """
        rec = self.recs[int(ch)]
        key = (int(ch), len(rec.meas_pts))
        got = self._unsafe_cache.get(key)
        if got is not None:
            return got
        gx, gy = self.annulus_grid()
        radius = float(self.cfg.cover_radius_m) + float(self.cfg.cover_slack_m)
        if not rec.meas_pts:
            m = np.ones(gx.size, bool)
        else:
            P = np.asarray(rec.meas_pts, float)
            d2 = ((gx[:, None] - P[None, :, 0]) ** 2
                  + (gy[:, None] - P[None, :, 1]) ** 2)
            m = np.sqrt(np.min(d2, axis=1)) > radius
        if len(self._unsafe_cache) > 600:
            self._unsafe_cache.clear()
        self._unsafe_cache[key] = m
        return m

    def uncovered_mask(self):
        """所有"从没听到过"的频道的联合未排除掩码。"""
        gx, gy = self.annulus_grid()
        unsafe = np.zeros(gx.size, bool)
        for ch in self.unheard():
            unsafe |= self.unsafe_of(ch)
        return gx, gy, unsafe

    def adds_coverage(self, ch, x, y):
        """在 ``(x, y)`` 测频道 ``ch`` 是否还能排除掉新的环带格点。"""
        m = self.unsafe_of(ch)
        if not m.any():
            return False
        gx, gy = self.annulus_grid()
        r2 = float(self.cfg.cover_radius_m) ** 2
        return bool(np.any(m & (((gx - x) ** 2 + (gy - y) ** 2) <= r2)))

    def is_complete(self):
        """能否断定"靶区内已无未清除源"。"""
        if self.heard_pending():
            return False
        return not bool(self.uncovered_mask()[2].any())

    # ------------------------------------------------------------------
    # 环带骨架
    # ------------------------------------------------------------------
    def ring_skeleton(self):
        """骨架停点 ``[(角度, 半径), ...]``，按角度排序（只构造一次）。"""
        if self._ring is None:
            pts = []
            for k, (r, n) in enumerate(self.cfg.cover_rings):
                off = (math.pi / float(n)) if (k % 2 == 1) else 0.0
                for i in range(int(n)):
                    a = (off + 2.0 * math.pi * i / float(n)) % (2.0 * math.pi)
                    pts.append((float(a), float(r)))
            pts.sort()
            self._ring = pts
        return self._ring

    def ring_xy(self, a, r):
        return (float(r) * math.cos(a), float(r) * math.sin(a))

    def forward_ring(self, dir_sign, cursor=None):
        """角向单调推进的骨架停点（已过去的不再选，方向锁死 ⇒ 不折返）。"""
        sk = self.ring_skeleton()
        a0 = self.ring_cursor_a if cursor is None else cursor
        if a0 is None:
            a0 = math.atan2(self.pos[1], self.pos[0]) % (2.0 * math.pi)
        out = []
        for (a, r) in sk:
            d = ((a - a0) * dir_sign) % (2.0 * math.pi)
            if d < float(self.cfg.ring_min_advance_rad):
                continue
            out.append((d, a, r))
        out.sort()
        res = []
        for _d, a, r in out:
            if self._akey(a) in self.ring_served:
                continue            # 这个角向站点的覆盖职责已经由某个目标停点代劳
            x, y = self.ring_xy(a, r)
            if not self.adds_any_coverage(x, y):
                continue
            res.append({"kind": "cover", "ch": None, "xy": (x, y), "r": None})
        return res

    @staticmethod
    def _akey(a):
        return round(float(a) % (2.0 * math.pi), 6)

    def mark_served(self, x, y):
        """某个停点（半径不小于骨架半径）已经代劳覆盖 ⇒ 附近的骨架点不必再走。

        不做这一步会留下一个隐蔽的浪费：目标停点测完之后目标被清除、不再出现在
        路点里，于是它旁边的骨架点又冒出来 —— 实测会多走一站、多测十几个频道
        （同一片区域在 70 m 内被整批测了两遍）。
        """
        if math.hypot(x, y) < min((r for (_a, r) in self.ring_skeleton()),
                                  default=0.0) * float(self.cfg.cover_duty_frac):
            return
        for (a, r) in self.ring_skeleton():
            px, py = self.ring_xy(a, r)
            if math.hypot(px - x, py - y) <= self.cfg.merge_radius_m:
                self.ring_served.add(self._akey(a))

    def adds_any_coverage(self, x, y):
        """该点是否还能为"某些从没听到过的频道"排除新的环带格点。"""
        need = self.unheard()
        if not need:
            return False
        gx, gy = self.annulus_grid()
        r2 = float(self.cfg.cover_radius_m) ** 2
        near = ((gx - x) ** 2 + (gy - y) ** 2) <= r2
        if not near.any():
            return False
        for ch in need:
            if bool(np.any(self.unsafe_of(ch) & near)):
                return True
        return False

    # ------------------------------------------------------------------
    # 目标路点
    # ------------------------------------------------------------------
    def is_long_sliver(self, br):
        """区域是不是"长条形"（最小包围圆半径巨大，或圆心落到靶区外）。

        两条近似平行的方位会把最小包围圆撑到几公里，圆心甚至落在靶区外十几公里。
        旧实现会**真的朝那个圆心走过去** —— 实测有一局为此多走 13.5 km、多花 2700 s。
        注意：判据只看 r*，不能看"圆心离原点近不近"—— 贴着靶区边界、r* 只有 1 m
        的正常区域圆心也可能在 1770 m 处，那是完全正常的可清除目标。
        """
        return bool(br is not None and float(br["radius"]) > float(self.cfg.big_r_m))

    def pending_singletons(self):
        """还只有一条方位的频道数（决定要不要动用期望场/批量定位）。"""
        return sum(1 for ch in self.heard_pending()
                   if self.recs[ch].n_bearings == 1)

    def _cheap_locate_point(self, rec, step=None):
        """**单点定位的最省做法**：只在当前位置周围一小圈里找最优第二检测点。

        和"期望场"用的是同一个代价模型（`best_refine_point` 的 E[D]），
        区别只在**候选半径**：这里把候选点限制在 ``short_locate_cap_m`` 以内
        （默认 420 m），不再允许"跑到 1 km 外去把基线拉长"。
        交会角小一点、$r^*$ 大一点没关系 —— 到了目标附近还会再定向
        （`clear_target` 的逼近—测量迭代会把误差迅速压下去），
        而**路上多走的时间是实打实丢掉的**。

        实测（`p3_paths` 场景 D）：旧做法为了给一个只知方向的源补方位，
        从 (−1716,58) 往靶区里折了 1020 m；用小步之后行程 16.1 km → 13.4 km。

        返回 ``(xy, info)``；无可用候选时 ``(None, None)``。
        """
        if not rec.pts:
            return None, None
        cap = float(self.cfg.short_locate_cap_m if step is None else step)
        p, info = best_refine_point(rec.pts, rec.svds, self.pos, None, n_t=60,
                                    radii=tuple(r for r in self.cfg.locate_radii
                                                if r <= cap) or (cap,),
                                    travel_cap_m=cap)
        if p is not None:
            if "mode" not in info:
                info = dict(info, mode="short")
            return p, info
        # 代价模型给不出候选（例如射线先验为空）时退化到"几何小步"
        return self._basic_transverse_point(rec, cap)

    def _basic_transverse_point(self, rec, cap):
        """纯几何兜底：从 $S_1$ 出发、与上一条视线成 55–105° 走一小步。"""
        S1 = np.asarray(rec.pts[-1], float)
        th1 = float(rec.svds[-1])
        ts, _w, _t_hi = ray_source_samples(S1, th1, n_t=40)
        if ts.size == 0:
            return None, None
        rho = min(max(0.5 * float(self.cfg.locate_radii[0]), 0.4 * float(np.median(ts))),
                  cap)
        cur = np.asarray(self.pos, float)
        best = None
        for ang in self.cfg.cheap_locate_angles:
            for sgn in (1.0, -1.0):
                a = math.radians(th1 + sgn * ang)
                p = S1 + rho * np.array([math.cos(a), math.sin(a)])
                if float(np.hypot(*p)) > R_ARENA - 1.0:
                    continue
                dd = float(np.linalg.norm(p - cur))
                if best is None or dd < best[0]:
                    best = (dd, p, ang)
        if best is None:
            return None, None
        _d, p, ang = best
        return ((float(p[0]), float(p[1])),
                {"mode": "basic_transverse", "rho": rho, "angle_deg": ang,
                 "move_m": _d})

    def _locate_point(self, ch, rec, br):
        """给"还需要更多方位"的频道选下一个检测点。

        两个候选来源，取总代价小者：

        * **以当前位置为中心**（`best_refine_point` 的默认做法）—— 走到候选点的
          代价已经算在 `cost_s` 里，适合"顺手就能测"的场合；
        * **以"上一条方位的检测点" $S_1$ 为中心**（半径 150–700 m）——
          这对"贴靶区边界、有效接收半径又小"的源是关键：环带骨架在 r=1000，
          而 r≈1800 处与骨架站位同方向的源，相邻两个站位离它有 1.3 km，
          早就超出它的有效接收半径了 —— 骨架只能给它**一条**方位，
          第二条必须专门回到 $S_1$ 附近横向补测。

        **待定频道很少时（< field_min_pending）不走期望场**，直接用
        `_cheap_locate_point` 的小步横向补测。
        """
        if self.pending_singletons() < int(self.cfg.field_min_pending):
            p, info = self._cheap_locate_point(rec)
            if p is not None:
                return p, info
        region = {"center": br["center"]} if br is not None else None
        p, info = best_refine_point(rec.pts, rec.svds, self.pos, region, n_t=90,
                                    radii=tuple(self.cfg.locate_radii),
                                    travel_cap_m=self.cfg.locate_travel_cap_m)
        if p is None:
            return self._cheap_locate_point(rec)
        best = (float(info["cost_s"]) if "cost_s" in info else float("inf"), p, info)
        S1 = tuple(rec.pts[-1])
        if math.dist(S1, self.pos) > 1.0:
            p2, info2 = best_refine_point(
                rec.pts, rec.svds, S1, region, n_t=90,
                radii=tuple(self.cfg.locate_radii),
                travel_cap_m=self.cfg.locate_bearing_cap_m)
            if p2 is not None:
                total = (float(info2.get("cost_s", 1e9))
                         + math.dist(self.pos, p2) / V_ROBOT)
                if total < best[0]:
                    best = (total, p2, info2)
        p, info = best[1], best[2]
        if p is None and br is not None:
            p = tuple(self._safe_point(br["center"]))
            info = {"mode": "center_fallback"}
        return p, info

    @staticmethod
    def _safe_point(p):
        """把点夹到靶区圆盘内（两条近平行方位会把区域中心撑到靶区外十几公里）。"""
        x, y = float(p[0]), float(p[1])
        d = math.hypot(x, y)
        lim = R_ARENA - 1.0
        if d > lim:
            return (x * lim / d, y * lim / d)
        return (x, y)

    def target_waypoints(self):
        """当前所有"听到了但没清掉"的频道 → 下一批目标路点。

        每个频道给的是 ``clear``（有界且不是长条形 ⇒ 直接去它的定位区域中心）
        或 ``locate``（只有一条方位 / 区域无界 / 长条形 ⇒ 先去横向补一条方位）。
        **长条形绝不能去最小包围圆的圆心** —— 圆心可能在靶区外十几公里。

        ``locate`` 的门槛（"该不该专门跑一趟去补方位"）分两种：

        * **只有一条方位**：先问"环形航路还会不会再听到它"（`_lost_fraction`），
          还会听到就**耐心等**（环形航路每个角度只经过一次，下一个骨架停点
          通常就在它那个方向）；只有确实听不到了、或已经等了
          ``locate_patience_stops`` 站，才专门去补测；
        * **有 >=2 条方位但区域无界/长条形**：环形航路再给方位也压不下去
          （问题在于交会角太差），必须专门换一个横向检测点。
        """
        cfg = self.cfg
        fut_xy = None
        wps = []
        for ch in self.heard_pending():
            if self.on_hold(ch):
                continue
            rec = self.recs[ch]
            br = self.region_info(rec)
            if br is not None and not self.is_long_sliver(br):
                wps.append({"kind": "clear", "ch": ch, "xy": self._safe_point(br["center"]),
                            "r": float(br["radius"]), "n_bearings": rec.n_bearings})
                continue
            # 区域无界/退化/长条形：必须换一个横向检测点
            if cfg.locate_mode == "never" or self.stop_seq - \
                    self._last_bearing_stop.get(int(ch), -99) < int(cfg.locate_stale_stops):
                continue
            if rec.n_bearings < 2:
                # 还会被环形航路听到 ⇒ 白等就行，别专门跑一趟
                waited = self.stop_seq - self._last_bearing_stop.get(int(ch), -99)
                if waited < int(cfg.locate_patience_stops):
                    if fut_xy is None:
                        fut_xy = [w["xy"] for w in
                                  self.forward_ring(self.ring_dir if self.ring_dir else 1.0)]
                    if self._lost_fraction(rec, fut_xy) < float(cfg.risk_min_lost):
                        continue
            p, info = self._locate_point(ch, rec, br)
            if p is None:
                continue
            p = self._safe_point(p)
            if math.hypot(p[0] - self.pos[0], p[1] - self.pos[1]) \
                    > cfg.locate_travel_cap_m:
                continue
            wps.append({"kind": "locate", "ch": ch, "xy": p,
                        "r": (float(br["radius"]) if br is not None else None),
                        "info": info, "n_bearings": rec.n_bearings})
        return wps

    # ------------------------------------------------------------------
    # 航路组装：骨架 + 目标"最便宜插入"
    # ------------------------------------------------------------------
    def assemble_route(self, dir_sign, targets=None, cursor=None):
        """返回 ``(route, length)``：骨架按角向单调排列，目标插在最便宜的空隙里。

        ``cover_duty``：被目标"顶替"掉的骨架停点，其覆盖职责转交给该目标 ——
        到那一站时必须把"从没听到过"的频道一并测掉，否则会留下覆盖空洞。
        """
        cfg = self.cfg
        saved = self.ring_cursor_a
        self.ring_cursor_a = cursor
        ring_all = self.forward_ring(dir_sign, cursor=cursor)
        self.ring_cursor_a = saved
        tgs = [dict(t) for t in (self.target_waypoints() if targets is None else targets)]
        for t in tgs:
            t["cover_duty"] = any(math.dist(w["xy"], t["xy"]) <= cfg.merge_radius_m
                                  for w in ring_all)
        ring = [w for w in ring_all
                if all(math.dist(w["xy"], t["xy"]) > cfg.merge_radius_m for t in tgs)]
        seq = list(ring)
        start = np.asarray(self.pos, float)

        def L(a, b):
            return math.dist(tuple(a), tuple(b))

        for t in sorted(tgs, key=lambda w: math.dist(self.pos, w["xy"])):
            best_i, best_extra = 0, None
            for i in range(len(seq) + 1):
                a = tuple(start) if i == 0 else seq[i - 1]["xy"]
                b = seq[i]["xy"] if i < len(seq) else None
                extra = L(a, t["xy"]) + (L(t["xy"], b) - L(a, b) if b else 0.0)
                if best_extra is None or extra < best_extra:
                    best_i, best_extra = i, extra
            cap = (cfg.locate_max_detour_m if t["kind"] == "locate"
                   else cfg.clear_max_detour_m)
            forced = (t["kind"] == "locate"
                      and self._locate_skips.get(t["ch"], 0) >= int(cfg.locate_force_after))
            if best_extra is not None and best_extra > float(cap) and not forced:
                # **定位**路点绕行太狠：本轮先不排它（航路绕下去往往自然会给它第二条方位）。
                # 但连续跳过 locate_force_after 轮之后就强制排进去。
                # **清除**路点不在这个规则里 —— 听到了的源必须清，绕行大只影响排序，
                # 不能变成"不清"（`clear_max_detour_m` 默认取一个极大的值）。
                self._locate_skips[t["ch"]] = self._locate_skips.get(t["ch"], 0) + 1
                continue
            seq.insert(best_i, t)
        mode = str(self.cfg.route_mode)
        if mode == "tsp":
            seq = self.nn_2opt(seq)
        elif mode == "polish":
            seq = self.polish_route(seq)
        if not seq:
            return [], 0.0
        total = L(start, seq[0]["xy"])
        for a, b in zip(seq, seq[1:]):
            total += L(a["xy"], b["xy"])
        return seq, total

    # ---- 航路后处理：允许目标在骨架空隙间自由换位，但不许骨架倒序 ----
    def _order_total(self, order, pts, s):
        d = float(np.linalg.norm(pts[order[0]] - s))
        for a, b in zip(order, order[1:]):
            d += float(np.linalg.norm(pts[b] - pts[a]))
        return d

    def polish_route(self, seq):
        """2-opt 后处理：**骨架停点的相对顺序不变**，目标可以在空隙间换位。

        实测（12 局）"骨架顺序 + 最便宜插入"比"同样这些路点的最优航路"多走
        3.0 km/局（13841 vs 10806 m），其中大部分是"某个目标本该排在后面一站
        之后"这种局部次序问题；允许目标换位、但禁止骨架倒序，既拿回这部分行程，
        又保留"绕圈不折返"的结构性保证。
        """
        if len(seq) < 4:
            return seq
        s = np.asarray(self.pos, float)
        pts = [np.asarray(w["xy"], float) for w in seq]
        is_cover = [w["kind"] == "cover" for w in seq]
        cid, c = {}, 0
        for i, f in enumerate(is_cover):
            if f:
                cid[i] = c
                c += 1

        def ring_ok(order):
            last = -1
            for i in order:
                if is_cover[i]:
                    if cid[i] < last:
                        return False
                    last = cid[i]
            return True

        order = list(range(len(seq)))
        best = self._order_total(order, pts, s)
        improved = True
        while improved:
            improved = False
            for i in range(len(order) - 1):
                for j in range(i + 1, len(order)):
                    cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                    if not ring_ok(cand):
                        continue
                    d = self._order_total(cand, pts, s)
                    if d < best - 1e-9:
                        order, best, improved = cand, d, True
        return [seq[i] for i in order]

    def nn_2opt(self, seq):
        """完全自由的最近邻 + 2-opt（消融对照用；结构约束全部放开）。"""
        if len(seq) < 4:
            return seq
        s = np.asarray(self.pos, float)
        pts = [np.asarray(w["xy"], float) for w in seq]
        k = len(seq)
        left, cur, order = list(range(k)), s, []
        while left:
            j = min(left, key=lambda i: float(np.linalg.norm(pts[i] - cur)))
            order.append(j)
            left.remove(j)
            cur = pts[j]
        best = self._order_total(order, pts, s)
        improved = True
        while improved:
            improved = False
            for i in range(k - 1):
                for j in range(i + 1, k):
                    cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                    d = self._order_total(cand, pts, s)
                    if d < best - 1e-9:
                        order, best, improved = cand, d, True
        return [seq[i] for i in order]

    def pick_direction(self):
        """选定**绕行方向**与**进入环带的位置**。

        旧实现直接用"当前位置的极角"当游标：原点扫描之后机器人还在原点附近，
        `atan2(0,0)` 恒为 0，于是每次都是"从正东开始绕" —— 这就是路径图上
        "进入环的位置是固定的"的原因。

        现在枚举 **(每个骨架停点 × 两个方向)** 共 2n 个入口，各组装一次航路，
        取总长最短的；长度相差在 ``entry_tie_m`` 以内的，再按"进入方向是否
        指向信息方向"（所有单方位频道候选源位的平均方向）来选 ——
        从源多的那一侧切进环带，源会更早被找到、更早被清掉，
        这也正是"平均定位清除时间"这个指标最敏感的地方。
        """
        cfg = self.cfg
        step = 2.0 * math.pi / max(len(self.ring_skeleton()), 1)
        if not cfg.entry_select:
            # 消融对照：只用"当前位置极角"当游标（旧行为）
            best = None
            for s in (1.0, -1.0):
                _seq, L = self.assemble_route(s)
                if best is None or L < best[0]:
                    best = (L, s)
            self.ring_dir = best[1]
            return self.ring_dir
        cands = []
        for s in (1.0, -1.0):
            for i, (a, _r) in enumerate(self.ring_skeleton()):
                cursor = (a - s * 0.5 * step) % (2.0 * math.pi)
                seq, L = self.assemble_route(s, cursor=cursor)
                cands.append((L, s, a))
        if not cands:
            self.ring_dir = 1.0
            return self.ring_dir
        best_len = min(c[0] for c in cands)
        a_info = self.info_direction_deg()
        pool = [c for c in cands if c[0] <= best_len + float(cfg.entry_tie_m)]
        if a_info is None:
            chosen = min(pool, key=lambda c: c[0])
        else:
            def key(c):
                diff = abs((math.degrees(c[2]) - a_info + 180.0) % 360.0 - 180.0)
                return (round(diff / 15.0), c[0])   # 先看是否朝信息方向，再看长度
            chosen = min(pool, key=key)
        _L, s, a = chosen
        self.ring_dir = s
        self.ring_cursor_a = (a - s * 0.5 * step) % (2.0 * math.pi)
        self.log(f"进入环带：选 ({self.cfg.cover_rings[0][0] * math.cos(a):.0f},"
                 f"{self.cfg.cover_rings[0][0] * math.sin(a):.0f})"
                 f"（角 {math.degrees(a):.0f}°），绕行方向 "
                 f"{'逆时针' if s > 0 else '顺时针'}；"
                 f"{len(cands)} 个入口里航路 {best_len:.0f} m 最短"
                 + (f"，信息方向 {a_info:.0f}°" if a_info is not None else ""))
        return self.ring_dir

    def info_direction_deg(self):
        """信息方向：所有"只有一条方位"的频道按先验中位源位加权求平均方向。"""
        acc = np.zeros(2)
        used = 0
        for ch in self.heard_pending():
            rec = self.recs[ch]
            if rec.n_bearings != 1:
                continue
            S1 = np.asarray(rec.pts[-1], float)
            ts, _w, _t_hi = ray_source_samples(S1, float(rec.svds[-1]), n_t=30)
            if ts.size == 0:
                continue
            t = float(np.median(ts))
            u = np.array([math.cos(math.radians(float(rec.svds[-1]))),
                          math.sin(math.radians(float(rec.svds[-1])))])
            g = S1 + t * u
            n = float(np.linalg.norm(g))
            if n > 1e-6:
                acc += g / n
                used += 1
        if used == 0 or float(np.linalg.norm(acc)) < 1e-6:
            return None
        return math.degrees(math.atan2(float(acc[1]), float(acc[0]))) % 360.0

    # ------------------------------------------------------------------
    # 停点测量
    # ------------------------------------------------------------------
    def _cross_ok(self, rec, x, y):
        """从 ``(x, y)`` 再测这条频道，与上一条视线的张角是否够大（否则白测）。"""
        if not rec.pts:
            return True
        (sx, sy), a = rec.pts[-1], rec.svds[-1]
        dx, dy = x - sx, y - sy
        n = math.hypot(dx, dy)
        if n < 1e-6:
            return False
        u = (math.cos(math.radians(a)), math.sin(math.radians(a)))
        cosang = abs((dx * u[0] + dy * u[1]) / n)
        cosang = max(-1.0, min(1.0, cosang))
        return math.degrees(math.acos(cosang)) >= float(self.cfg.min_cross_deg)

    def chans_at(self, x, y, ch=None, cover_duty=False):
        """本停点该测哪些频道。

        * 目标频道一定测；
        * **0 方位**频道（这些频道是"没有源"的频道，测它们纯粹为了证明没有残留源）：
          只有在本停点**负有覆盖职责**、且本点还能排除新的环带格点时才测。
          "负有覆盖职责"= 骨架停点 / 顶替了骨架停点的目标 / **半径不小于骨架半径的
          外圈目标停点** —— 最后一条很关键：半径越大的检测点，对 r=1800 外圈 rim 的
          角向覆盖半宽越大（r=880 时 ±18°，r=1500 时 ±34°），所以**顺路清外圈源时
          顺手一测，就能顶掉两个骨架停点**，比"先跑完骨架再清"省一倍检测；
        * **1 方位**频道：张角够大（>= ``min_cross_deg``）才测。
        """
        out = []
        duty = bool(cover_duty) or ch is None
        if not duty:
            rr = min((r for (_a, r) in self.ring_skeleton()), default=0.0)
            duty = math.hypot(x, y) >= rr * float(self.cfg.cover_duty_frac)
        for c in self.pending():
            rec = self.recs[c]
            if rec.n_bearings == 0:
                if duty and self.adds_coverage(c, x, y):
                    out.append(c)
            elif rec.n_bearings == 1:
                if self._cross_ok(rec, x, y):
                    out.append(c)
            if ch is not None and c == int(ch) and c not in out:
                out.append(c)
        if ch is not None and int(ch) in out:
            out.remove(int(ch))
            out.insert(0, int(ch))
        return out

    def visit(self, wp):
        x, y = wp["xy"]
        chans = self.chans_at(x, y, wp.get("ch"),
                              cover_duty=bool(wp.get("cover_duty")))
        if not chans:
            return 0
        n = self.scan_at(float(x), float(y), chans)
        self.note_pos()
        return n

    # ------------------------------------------------------------------
    # 清除：逼近—测量—试探 的迭代
    # ------------------------------------------------------------------
    def probe_path(self, c, r, poly=None, tried=()):
        """覆盖式试探点，按"里圈起、环内按极角、贪心最近邻"排成一条短折线。"""
        from p3_robot import _dist_point_polygon
        cfg = self.cfg
        c = np.asarray(c, float)
        s = float(cfg.probe_spacing_m)
        rr = min(float(r), float(cfg.probe_max_radius_m)) + R_CLEAR
        u = np.array([s, 0.0])
        v = np.array([s / 2.0, s * math.sqrt(3.0) / 2.0])
        N = int(math.ceil(rr / s)) + 1
        cand = []
        for i in range(-N, N + 1):
            for j in range(-N, N + 1):
                p = c + i * u + j * v
                if float(np.hypot(*(p - c))) <= rr + 1e-9:
                    cand.append(p)
        if poly is not None and len(poly) >= 3:
            P = np.asarray(poly, float)
            keep = [p for p in cand
                    if _dist_point_polygon(p, P) <= R_CLEAR + 1e-9]
            cand = keep if keep else cand
        if tried:
            T = np.asarray(tried, float)
            cand = [p for p in cand
                    if float(np.min(np.hypot(T[:, 0] - p[0], T[:, 1] - p[1]))) >= 2.0]
        if not cand:
            return []
        cand.sort(key=lambda p: (round(float(np.hypot(*(p - c))) / (2 * s)),
                                 math.atan2(float(p[1] - c[1]), float(p[0] - c[0]))))
        cand = cand[:int(cfg.probe_max_points)]
        cur = np.asarray(self.pos, float)
        rest, out = list(cand), []
        while rest:
            j = min(range(len(rest)),
                    key=lambda i: float(np.hypot(*(rest[i] - cur))))
            p = rest.pop(j)
            out.append(p)
            cur = p
        return out

    # 兼容父类 `_probe_count` / `estimate_clear_cost` 的调用名
    def probe_points(self, c, r, poly=None, tried=()):
        return self.probe_path(c, r, poly=poly, tried=tried)

    def sweep_clear(self, ch, rec, c, r, poly=None):
        probes = self.probe_path(c, r, poly=poly, tried=rec.tried_probes)
        self.log(f"  覆盖式试探：中心 ({c[0]:.0f},{c[1]:.0f})，r={r:.0f} m，"
                 f"{'多边形区域' if poly else '外接圆'}，试探点 {len(probes)}"
                 f"（间距 {self.cfg.probe_spacing_m:.0f} m）")
        for p in probes:
            if self.aborted or not self.can_afford(T_CLEAR_FAIL + 5.0):
                return False
            trav = math.dist(self.pos, (float(p[0]), float(p[1])))
            if not self.can_afford(trav / V_ROBOT + T_CLEAR_FAIL + 3.0):
                return False
            rec.tried_probes.append((float(p[0]), float(p[1])))
            self.stats["n_probe"] = self.stats.get("n_probe", 0) + 1
            self.stats["probe_m"] = self.stats.get("probe_m", 0.0) + trav
            if self.do_clear(float(p[0]), float(p[1]), ch):
                return True
        return False

    def _measure_far(self, ch, x, y, min_gap=None):
        """在 ``(x, y)`` 给频道补一条方位（与既有测量点太近就跳过）。"""
        rec = self.recs[int(ch)]
        gap = float(self.cfg.approach_eps_m if min_gap is None else min_gap)
        for q in rec.meas_pts:
            if math.hypot(x - q[0], y - q[1]) < gap:
                return None
        if not self.can_afford(
                math.dist(self.pos, (x, y)) / V_ROBOT + T_MEASURE + T_SWITCH + 4.0):
            return None
        return self.measure(float(x), float(y), int(ch))

    def clear_target(self, ch, rec):
        """定位 → 逼近 → 覆盖式试探（可迭代，直到成功或用尽预算/迭代数）。

        旧实现在 `clear_targets()` 里把 ``r* > 600 m`` 的目标永久过滤掉，
        碰到"区域无界"就直接 `clear_fail += 1` 走人 —— 这正是清除率上不去的主因。
        这里改成迭代：区域大就往中心逼近并补方位（每补一条方位区域都会明显缩小），
        区域小到 ``probe_enter_r_m`` 再走覆盖式试探。
        """
        ch = int(ch)
        cfg = self.cfg
        self.log(f"清除频道{ch}：{rec.n_bearings} 条方位，"
                 f"起点 ({self.pos[0]:.0f},{self.pos[1]:.0f})")
        for it in range(int(cfg.clear_max_iters)):
            if rec.cleared or self.aborted:
                break
            self.n_clear_iter += 1
            br = self.region_info(rec)
            # (A) 没有可用区域：换横向点补方位
            if br is None:
                p, info = self._locate_point(ch, rec, None)
                if p is None:
                    break
                resp = self._measure_far(ch, p[0], p[1])
                if resp is None:
                    break
                self.stats["n_refine"] += 1
                self.log(f"  [{it+1}] 区域无界/退化 -> 横向补测 "
                         f"({p[0]:.0f},{p[1]:.0f})")
                if resp.get("measure_result") == "near":
                    return self.do_clear(float(p[0]), float(p[1]), ch)
                continue
            c = np.asarray(br["center"], float)
            r = float(br["radius"])
            d = math.dist(self.pos, tuple(c))
            long_sliver = self.is_long_sliver(br)
            # (A0) 区域还大时先靠近区域中心（顺便测一条方位把区域压小）。
            #      **区域已经够小时不要走这一步**：覆盖式试探的第一发就是"移动到
            #      区域内的试探点"，本身就是逼近；而"逼近测量"要求新测点离既有
            #      测点至少 approach_eps_m，对"源就在原点附近"这类目标会永远返回
            #      None，于是 clear_target 空转、clear_leftovers 反复重试
            #      （实测 seed 20262713：源在 (−4,15)、r* 只有 2.2 m，却跑了 37.6 km）。
            if (not long_sliver) and r > cfg.probe_enter_r_m \
                    and d > max(r, cfg.arrive_radius_m) + cfg.approach_eps_m:
                if not self.can_afford(d / V_ROBOT + T_MEASURE + T_SWITCH + 6.0):
                    break
                resp = self._measure_far(ch, float(c[0]), float(c[1]))
                if resp is None:
                    p, _info = self._locate_point(ch, rec, br)
                    if p is not None:
                        resp = self._measure_far(ch, p[0], p[1])
                if resp is not None:
                    self.log(f"  [{it+1}] 逼近区域中心 ({c[0]:.0f},{c[1]:.0f})："
                             f"移动 {d:.0f} m（r*={r:.0f} m）")
                    if resp.get("measure_result") == "near":
                        return self.do_clear(float(self.pos[0]), float(self.pos[1]), ch)
                    continue
                # 逼近测量做不了（附近已测过）⇒ 直接进入覆盖式试探
            # (B) 区域够小：覆盖式试探
            if r <= cfg.probe_enter_r_m and not long_sliver:
                if self.sweep_clear(ch, rec, c, r, poly=br.get("poly")):
                    return True
                r2 = min(max(r * 1.8, r + 40.0), cfg.probe_max_radius_m)
                if r2 > r + 1.0:
                    self.log(f"  区域内未发现目标 -> 扩大到 r={r2:.0f} m 再试")
                    if self.sweep_clear(ch, rec, c, r2, poly=None):
                        return True
                p, _info = self._locate_point(ch, rec, br)
                if p is None:
                    break
                resp = self._measure_far(ch, p[0], p[1])
                if resp is None:
                    break
                if resp.get("measure_result") == "near":
                    return self.do_clear(float(p[0]), float(p[1]), ch)
                continue
            # (C) 区域还大 / 长条形：补一条横向方位（对长条形**不去圆心**，那可能在靶区外）
            if long_sliver:
                p, _info = self._locate_point(ch, rec, None)
                if p is None:
                    break
                target = self._safe_point(p)
            else:
                target = tuple(c)
                if d < cfg.approach_eps_m:
                    p, _info = self._locate_point(ch, rec, br)
                    if p is None:
                        break
                    target = self._safe_point(p)
            resp = self._measure_far(ch, target[0], target[1])
            if resp is None:
                p, _info = self._locate_point(ch, rec, None if long_sliver else br)
                if p is None:
                    break
                target = self._safe_point(p)
                resp = self._measure_far(ch, target[0], target[1])
                if resp is None:
                    break
            self.stats["n_refine"] += 1
            self.log(f"  [{it+1}] 逼近测量 ({target[0]:.0f},{target[1]:.0f})："
                     f"移动 {math.dist(self.pos, target):.0f} m，r* {r:.0f} -> ?")
            if resp.get("measure_result") == "near":
                return self.do_clear(float(target[0]), float(target[1]), ch)
        if not rec.cleared:
            rec.clear_fail += 1
            self.hold(ch)
            self.log(f"  [x] 频道{ch} 本轮未清除成功（冷却 {cfg.fail_cooldown} 个停点）")
        return rec.cleared

    # ------------------------------------------------------------------
    # 开场：期望场定点 + 先清近处目标
    # ------------------------------------------------------------------
    def initial_stage(self):
        """原点扫描之后：**用期望场选第二个检测点**，顺手清掉靠内圈的目标。

        为什么必须做：原点那一测只听得见一定范围内的源；这些"内圈源"若等到沿环带
        走的时候再处理，就得从环带上专门往回跑一趟。实测（seed 20261113）一次
        "专门跑一趟定位"的绕行高达 2.1 km，等于整局行程的 11%。趁还在原点附近，
        用第二问的 E[D] 代价模型在"两翼"上选第二检测点（对多个单方位频道的候选点
        做完全连接聚类，一次移动定住好几个源），定位完立刻清掉，再往环带走。

        做成**多轮**而不是一轮：一轮只能处理一个聚类，剩下的单方位频道会被留到
        环带上，正是上面那种绕行的来源。
        """
        if self.aborted or self.cfg.locate_mode == "never":
            return 0
        n_total = 0
        for rnd in range(int(self.cfg.initial_rounds)):
            # 每轮的移动上限递增：第一轮只走 350 m（近处的源这样最省），
            # 还有没解决的频道才逐轮放宽（远处的源需要更长的基线）
            cap = min(float(self.cfg.locate_travel_cap_m),
                      float(self.cfg.initial_locate_max_move_m)
                      * (float(self.cfg.initial_move_growth) ** rnd))
            pend = []
            for ch in self.heard_pending():
                rec = self.recs[ch]
                if rec.n_bearings != 1 or self.on_hold(ch):
                    continue
                if math.hypot(rec.pts[0][0], rec.pts[0][1]) \
                        > self.cfg.initial_locate_max_m:
                    continue
                pend.append(ch)
            if not pend:
                break
            per = {}
            for ch in pend:
                p, info = self._locate_point(ch, self.recs[ch], None)
                if p is not None:
                    per[ch] = np.asarray(p, float)
            if not per:
                break
            groups = []
            for ch, p in per.items():
                for g in groups:
                    if all(float(np.linalg.norm(p - per[c2])) <= self.cfg.batch_max_m
                           for c2 in g):
                        g.append(ch)
                        break
                else:
                    groups.append([ch])
            best = None
            for g in groups:
                if len(g) < int(self.cfg.batch_min_channels) \
                        and len(groups) > 1:
                    continue
                P = np.asarray([per[c2] for c2 in g], float)
                for c0 in [P.mean(axis=0)] + [P[i] for i in range(P.shape[0])]:
                    trav = float(np.linalg.norm(c0 - np.asarray(self.pos, float)))
                    if trav > cap:
                        continue
                    cost = trav / V_ROBOT + len(g) * (T_MEASURE + T_SWITCH)
                    key = (-len(g), cost)          # 先看能一次定住几个频道
                    if best is None or key < best[0]:
                        best = (key, c0, g, trav)
            if best is None:
                break
            _key, c0, group, trav = best
            if not self.can_afford(
                    trav / V_ROBOT + len(group) * (T_MEASURE + T_SWITCH) + 20.0):
                break
            self.log(f"开场定点（期望场，第 {rnd+1} 轮）：{len(group)} 个单方位频道 "
                     f"{group} -> 合并第二检测点 ({c0[0]:.0f},{c0[1]:.0f})，"
                     f"移动 {trav:.0f} m")
            self.n_locate_stops += 1
            self.scan_points.append((float(c0[0]), float(c0[1])))
            before = self._state_key()
            for ch in group:
                if self.aborted or not self.can_afford(T_MEASURE + T_SWITCH + 3.0):
                    break
                resp = self.measure(float(c0[0]), float(c0[1]), int(ch))
                n_total += 1
                if resp.get("measure_result") == "near":
                    self.do_clear(float(c0[0]), float(c0[1]), int(ch))
            self.note_pos()
            self.stop_seq += 1
            self.last_stop_xy = (float(c0[0]), float(c0[1]))
            # 顺手清掉已经定下来、又在附近的目标（"先清较靠近原点的目标"）
            self.opportunistic_clear(radius=self.cfg.initial_clear_radius_m, max_n=4)
            if self._state_key() == before:
                break
        self.opportunistic_clear(radius=self.cfg.initial_clear_radius_m, max_n=4)
        return n_total

    def opportunistic_clear(self, radius=250.0, max_n=3):
        """脚下已经定位好、区域也够小的目标立刻清掉（"边走边清"的落实）。"""
        done = 0
        for _ in range(int(max_n)):
            if self.aborted or not self.can_afford(self.cfg.min_action_budget_s):
                break
            cands = []
            for ch in self.heard_pending():
                if self.on_hold(ch):
                    continue
                br = self.region_info(self.recs[ch])
                if br is None or br["radius"] > self.cfg.probe_enter_r_m * 2.0:
                    continue
                d = math.dist(self.pos, br["center"])
                if d <= max(radius, br["radius"]):
                    cands.append((d, ch))
            if not cands:
                break
            cands.sort()
            ch = cands[0][1]
            if not self.clear_target(ch, self.recs[ch]):
                break
            done += 1
        return done

    # ------------------------------------------------------------------
    # 角向扇区：**走过的扇区里"该清没清"的目标不许留到下一圈**
    # ------------------------------------------------------------------
    def offroute_clear(self, here, nxt, nxt2=None, max_n=None):
        """**"现在清"还是"等下一站再清"** —— 用"哪一个的额外绕行更小"来判。

        用户给的直觉是"看第一条方位与行进方向的夹角"：夹角小（源基本在行进方向上）
        就等下一站，夹角大就**立刻走一小步、定位并清除**。方向完全正确 ——
        环形航路每个角度只经过一次，等下一站 = 让下一站替我们定位、
        但之后要**拐回来清**，那个回头距离由"源离环带多远"决定。

        但**只按夹角判太粗**（实测：常规随机 330 → 350、外圈环带 4085 → 5238 s），
        因为夹角大是常态，而"拐回来"到底多花多少，取决于源离哪一站更近。
        所以这里把夹角当**粗筛**，真正的判据是拿射线先验直接算两种做法的
        **额外绕行**：

        * 现在清：``|A→G| + |G→B| − |A→B|``
        * 等下一站：``|B→G| + |G→C| − |B→C|``（没有 C 时按"从 B 出再回 B"算）

        按面积均匀的射线先验对 ``G`` 加权平均，前者明显更小才就地清。
        这样"源就在正前方"（B 更近）自然选等待，"源在侧后方"（A 更近）自然选就地清，
        夹角判据只是它的一个粗糙近似。
        """
        cfg = self.cfg
        if not cfg.offroute_clear or self.aborted or nxt is None:
            return 0
        ax, ay = here["xy"]
        bx, by = nxt["xy"]
        A = np.array([ax, ay], float)
        B = np.array([bx, by], float)
        C = (np.array(nxt2["xy"], float) if nxt2 is not None
             else B + (B - A))
        phi = math.atan2(by - ay, bx - ax)
        cands = []
        for ch in self.heard_pending():
            rec = self.recs[ch]
            if rec.n_bearings != 1 or self.on_hold(ch):
                continue
            # 只处理"就是在这一站听到的"（上一条方位的检测点离本站很近）
            if math.dist(rec.pts[-1], (ax, ay)) > 80.0:
                continue
            th = float(rec.svds[-1])
            sep = abs(math.degrees((th - math.degrees(phi) + 180.0) % 360.0 - 180.0))
            if sep < float(cfg.wait_angle_min_deg):
                continue            # 源几乎在行进方向上 ⇒ 等下一站肯定更省
            ts, w, _t_hi = ray_source_samples(np.asarray(rec.pts[-1], float), th,
                                              n_t=50)
            if ts.size == 0:
                continue
            if float(_t_hi) > float(cfg.offroute_max_thi_m):
                continue        # 射线太长 ⇒ 源位估计不可靠，别拿它做判断
            u = np.array([math.cos(math.radians(th)), math.sin(math.radians(th))])
            S1 = np.asarray(rec.pts[-1], float)
            G = S1[None, :] + ts[:, None] * u[None, :]

            def d(X):
                return np.hypot(G[:, 0] - X[0], G[:, 1] - X[1])
            # 源位先验的加权平均距离太远时，估计不可靠、"现在清"多半是白跑
            if float(np.dot(w, d(A))) > float(cfg.offroute_max_dist_m):
                continue
            extra_now = d(A) + d(B) - float(np.linalg.norm(B - A))
            extra_wait = d(B) + d(C) - float(np.linalg.norm(C - B))
            e_now = float(np.dot(w, extra_now))
            e_wait = float(np.dot(w, extra_wait))
            if e_now + float(cfg.offroute_margin_m) >= e_wait:
                continue            # 等下一站更省 ⇒ 耐心等
            cands.append((e_wait - e_now, ch, sep))
        cands.sort(reverse=True)
        n_max = int(max_n or cfg.offroute_max_per_stop)
        done = 0
        for gain, ch, _sep in cands[:max(0, n_max)]:
            rec = self.recs[ch]
            p, _info = self._cheap_locate_point(rec, step=cfg.offroute_step_m)
            if p is None:
                continue
            dd = math.dist(self.pos, p)
            if dd > float(cfg.offroute_step_m) * 1.3:
                continue
            if not self.can_afford(dd / V_ROBOT + T_MEASURE + T_SWITCH + 8.0):
                continue
            resp = self.measure(float(p[0]), float(p[1]), int(ch))
            self.note_pos()
            self.log(f"  就地定位 频道{ch}：预计省 {gain:.0f} m（现在清 vs 等下一站）"
                     f"-> 走 {dd:.0f} m 到 ({p[0]:.0f},{p[1]:.0f}) 补第二条方位")
            if resp.get("measure_result") == "near":
                self.do_clear(float(p[0]), float(p[1]), int(ch))
                done += 1
                continue
            br = self.region_info(rec)
            if br is None:
                continue
            if self.clear_target(int(ch), rec):
                done += 1
        return done

    def risk_locate(self, max_n=None):
        """**防过期补测**：对"马上就要听不到"的单方位频道，就地走一小步补第二条方位。

        为什么必须做：这条航路每个角度**大致只经过一次**。某个频道如果在它所在
        扇区只拿到一条方位、之后环形航路越走越远，就只能等下一圈（或收尾阶段
        横穿全场）—— 实测 `p3_paths` 场景 C 里 ch6 就是这样横穿了 3.4 km。

        判据（按射线先验加权）：把源位按面积均匀撒在射线上，统计"往后
        ``risk_lookahead`` 个骨架停点**都听不到**（距离 > 1000 m，而任何源的
        有效接收半径都 >= 1000 m）"的比例；比例超过 ``risk_min_lost`` 就说明
        这个源有相当大概率要"过期"。此刻我们还在它的扇区里，走一小步补一条方位
        最便宜；步长只有 ``risk_step_m``（默认 300 m），基线短一点无所谓 ——
        等清到目标附近还会再定向（`clear_target` 的逼近—测量迭代）。
        """
        cfg = self.cfg
        if not cfg.risk_locate or self.aborted:
            return 0
        fut = self.forward_ring(self.ring_dir if self.ring_dir else 1.0)
        fut_xy = [w["xy"] for w in fut[:int(cfg.risk_lookahead)]]
        if not fut_xy:
            return 0
        todo = []
        for ch in self.heard_pending():
            rec = self.recs[ch]
            if rec.n_bearings != 1 or self.on_hold(ch):
                continue
            if self.stop_seq - self._last_bearing_stop.get(int(ch), -99) <= 0:
                continue            # 刚在本站拿到方位，先给下一站一次机会
            if self._lost_fraction(rec, fut_xy) < float(cfg.risk_min_lost):
                continue
            p, info = self._cheap_locate_point(rec)
            if p is None:
                continue
            d = math.dist(self.pos, p)
            if d > float(cfg.risk_step_m) * 1.5:
                continue
            todo.append((d, ch, p, info))
        todo.sort()
        n = 0
        for _d, ch, p, _info in todo[:int(max_n or cfg.risk_max_per_stop)]:
            if not self.can_afford(math.dist(self.pos, p) / V_ROBOT
                                   + T_MEASURE + T_SWITCH + 8.0):
                break
            resp = self.measure(float(p[0]), float(p[1]), int(ch))
            n += 1
            self.log(f"  防过期补测 频道{ch}：走到 ({p[0]:.0f},{p[1]:.0f})"
                     f"（{_d:.0f} m）取第二条方位")
            if resp.get("measure_result") == "near":
                self.do_clear(float(p[0]), float(p[1]), int(ch))
                break
        if n:
            self.note_pos()
            self.opportunistic_clear(radius=self.cfg.sector_clear_m, max_n=2)
        return n

    def _lost_fraction(self, rec, fut_xy):
        """先验中"往后这些骨架停点都听不到该源"的概率（面积均匀的射线先验）。"""
        S1 = np.asarray(rec.pts[-1], float)
        th1 = float(rec.svds[-1])
        ts, w, _t_hi = ray_source_samples(S1, th1, n_t=60)
        if ts.size == 0:
            return 0.0
        u = np.array([math.cos(math.radians(th1)), math.sin(math.radians(th1))])
        G = S1[None, :] + ts[:, None] * u[None, :]
        heard = np.zeros(ts.size, bool)
        for (x, y) in fut_xy:
            heard |= (np.hypot(G[:, 0] - x, G[:, 1] - y) <= R_RECV_MIN)
        return float(w[~heard].sum())

    def sector_clear(self, a_from, a_to):
        """把"刚刚走过的角向扇区"里已经定位好的目标就地清掉。

        扇区定义：从上一站到本站的方位角区间（沿绕行方向）。这就是用户说的
        "每个角度大致只经过一次，覆盖的点要尽快清理"—— 目标已经能清了、
        又正好在我们刚扫过的扇区里，就地清掉比留给下一圈便宜得多。
        """
        if a_from is None or a_to is None or self.aborted:
            return 0
        cap = float(self.cfg.sector_clear_m)
        todo = []
        for ch in self.heard_pending():
            if self.on_hold(ch):
                continue
            br = self.region_info(self.recs[ch])
            if br is None:
                continue
            xy = br["center"]
            d = math.dist(self.pos, xy)
            if d > max(cap, br["radius"]):
                continue
            a = math.atan2(xy[1], xy[0]) % (2.0 * math.pi)
            if self._in_sector(a_from, a_to, a):
                todo.append((d, ch))
        todo.sort()
        done = 0
        for _d, ch in todo:
            if self.aborted or not self.can_afford(self.cfg.min_action_budget_s):
                break
            if self.clear_target(ch, self.recs[ch]):
                done += 1
        return done

    def _in_sector(self, a0, a1, a):
        """``a`` 是否落在"从 ``a0`` 走到 ``a1``"的短弧区间里。"""
        span = (a1 - a0) % (2.0 * math.pi)
        if span > math.pi:
            span = (a0 - a1) % (2.0 * math.pi)
            rel = (a0 - a) % (2.0 * math.pi)
        else:
            rel = (a - a0) % (2.0 * math.pi)
        return rel <= span + 1e-9

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------
    def run(self):
        t0 = time.time()
        resp = self.arena.enter()
        if resp.get("accepted") is not True:
            raise ArenaError(f"/enter 未被接受：{resp}")
        self.log(f"进入靶区：可用预算 {self.remaining():.0f} s"
                 f"（{self.arena.budget_kind()}）；策略=统一滚动航路")
        try:
            # ---- 第 0 轮：原点全频道扫描 ----
            chans0 = self.chans_at(0.0, 0.0)
            self.log(f"第 0 轮扫描（原地）：{len(chans0)} 个频道 {chans0}")
            self.scan_points.append(self.pos)
            if chans0:
                self.scan_at(self.pos[0], self.pos[1], chans0)
            self.note_pos()
            self.stop_seq += 1

            # ---- 开场：期望场定点，先清近处目标 ----
            self.initial_stage()

            # ---- 统一滚动航路 ----
            stall = 0
            while (not self.aborted and self.stop_seq < int(self.cfg.max_stops)
                   and self.remaining() > self.cfg.min_stop_budget_s):
                if self.is_complete():
                    self.log("* 所有频道要么已清除、要么已被 1000 m 覆盖排除 -> 收工")
                    break
                targets = self.target_waypoints()
                if self.ring_dir == 0.0:
                    self.pick_direction()
                route, _L = self.assemble_route(self.ring_dir, targets=targets,
                                                cursor=self.ring_cursor_a)
                if not route:
                    if self.opportunistic_clear(radius=1e9, max_n=4):
                        continue
                    if self.clear_leftovers():
                        continue
                    self.log("没有可用路点、也没有可处理的目标 -> 结束")
                    break
                wp = route[0]
                # 防死循环：与上一个停点几乎重合时退到下一站
                if (self.last_stop_xy is not None
                        and math.dist(wp["xy"], self.last_stop_xy) < self.cfg.min_move):
                    alt = next((w for w in route[1:]
                                if math.dist(w["xy"], self.last_stop_xy)
                                >= self.cfg.min_move), None)
                    if alt is None:
                        self.log("航路剩余点都与当前停点重合 -> 结束")
                        break
                    wp = alt
                cost = (math.dist(self.pos, wp["xy"]) / V_ROBOT
                        + T_MEASURE + T_SWITCH + 4.0)
                if not self.can_afford(cost):
                    self.log(f"剩余时间不足以再走一站（约 {cost:.0f} s）-> 收工")
                    break
                before = self._state_key()
                nxt = route[1] if len(route) > 1 else None
                nxt2 = route[2] if len(route) > 2 else None
                n = self.visit(wp)
                self.stop_seq += 1
                self.last_stop_xy = tuple(wp["xy"])
                self.mark_served(float(wp["xy"][0]), float(wp["xy"][1]))
                if wp["kind"] == "cover":
                    self.ring_cursor_a = math.atan2(wp["xy"][1], wp["xy"][0]) \
                        % (2.0 * math.pi)
                self.tour_log.append({"stop": self.stop_seq, "kind": wp["kind"],
                                      "ch": wp.get("ch"),
                                      "xy": [round(v, 1) for v in wp["xy"]],
                                      "n_chans": n,
                                      "t": round(float(self.arena.virtual_time_s), 1)})
                self.log(f"航路第 {self.stop_seq} 站｜{self._wp_desc(wp)}｜"
                         f"测 {n} 个频道｜已排除 "
                         f"{1.0 - float(self.uncovered_mask()[2].mean()):.3f}｜"
                         f"已清除 {self._n_cleared()}")
                if n == 0:
                    break
                # 到站之后：本站目标立刻处理，附近可清目标顺手清
                a_prev = self._prev_stop_a
                a_now = math.atan2(wp["xy"][1], wp["xy"][0]) % (2.0 * math.pi)
                self._prev_stop_a = a_now
                ch = wp.get("ch")
                if ch is not None and not self.recs[int(ch)].cleared \
                        and self.region_info(self.recs[int(ch)]) is not None:
                    self.clear_target(int(ch), self.recs[int(ch)])
                self.opportunistic_clear(radius=self.cfg.merge_radius_m, max_n=2)
                # ① 不在行进方向上的新目标：就地补测并清除（见 wait_angle_min_deg）
                self.offroute_clear(wp, nxt, nxt2)
                # ② 刚走过的角向扇区里"已经能清"的目标就地清掉（默认关闭）
                self.sector_clear(a_prev, a_now)
                # ③ 马上就要"过期"的单方位频道（默认关闭）
                self.risk_locate()
                if self._state_key() == before:
                    stall += 1
                    if stall >= 3:
                        self.log("连续 3 站没有产生任何新信息 -> 结束")
                        break
                else:
                    stall = 0

            # ---- 收尾 ----
            self.clear_leftovers()
        finally:
            try:
                self.arena.exit()
            except ArenaError as e:
                self.log(f"/exit 异常：{e}")
        self.stats["program_runtime_s"] = time.time() - t0
        self.stats["n_scan_rounds"] = self.stop_seq
        rep = self.report()
        cov, mdist = self.coverage_now()
        rep["coverage"] = cov
        rep["max_uncovered_dist_m"] = mdist
        rep["complete_proof"] = bool(self.is_complete())
        rep["n_cover_stops"] = self.n_cover_stops
        rep["n_locate_stops"] = self.n_locate_stops
        rep["n_clear_iter"] = self.n_clear_iter
        return rep

    def clear_leftovers(self, max_steps=14):
        """收尾：剩下的"听到过但没清掉"的频道，逐个自适应定位清除。"""
        done = 0
        for _ in range(int(max_steps)):
            if self.aborted or self.remaining() <= self.cfg.min_stop_budget_s:
                break
            left = [ch for ch in self.heard_pending() if not self.on_hold(ch)]
            if not left:
                for ch in self.heard_pending():
                    self._hold_until.pop(int(ch), None)
                left = self.heard_pending()
            if not left:
                break
            left.sort(key=lambda c: math.dist(
                self.pos, (self.region_info(self.recs[c]) or {"center": (0.0, 0.0)})["center"]))
            ch = left[0]
            self.log(f"收尾：处理频道{ch}")
            if self.clear_target(ch, self.recs[ch]):
                done += 1
            else:
                self.hold(ch, 1)
        return done

    # ------------------------------------------------------------------
    def _state_key(self):
        return (self._n_cleared(), sum(len(r.pts) for r in self.recs.values()),
                sum(len(r.meas_pts) for r in self.recs.values()))

    def _wp_desc(self, wp):
        x, y = wp["xy"]
        if wp["kind"] == "cover":
            self.n_cover_stops += 1
            return f"骨架覆盖 ({x:.0f},{y:.0f})"
        if wp["kind"] == "clear":
            return (f"清除 ch{wp['ch']}（{wp['n_bearings']} 方位，"
                    f"r*={wp['r']:.0f} m）({x:.0f},{y:.0f})")
        self.n_locate_stops += 1
        return f"定位 ch{wp['ch']}（{wp['n_bearings']} 方位）({x:.0f},{y:.0f})"


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------
def _nn_2opt_len(pts, start=(0.0, 0.0)):
    """从 ``start`` 出发、遍历 ``pts`` 的最近邻 + 2-opt 航路长度（下界参考）。"""
    P = [np.asarray(p, float) for p in pts]
    S = np.asarray(start, float)
    k = len(P)
    if k == 0:
        return 0.0
    left, cur, seq = list(range(k)), S, []
    while left:
        j = min(left, key=lambda i: float(np.linalg.norm(P[i] - cur)))
        seq.append(j)
        left.remove(j)
        cur = P[j]

    def tot(order):
        d = float(np.linalg.norm(P[order[0]] - S))
        for a, b in zip(order, order[1:]):
            d += float(np.linalg.norm(P[b] - P[a]))
        return d
    best = tot(seq)
    improved = True
    while improved:
        improved = False
        for i in range(k - 1):
            for j in range(i + 1, k):
                cand = seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]
                d = tot(cand)
                if d < best - 1e-9:
                    seq, best, improved = cand, d, True
    return best


def selfcheck(verbose=True, seed=20260913, cases=3):
    """T1–T6：统一航路策略的结构性断言。"""
    from p3_arena import MockArena

    out, ok_all = [], True

    def rec(name, ok, detail=""):
        nonlocal ok_all
        ok_all = ok_all and bool(ok)
        out.append({"check": name, "ok": bool(ok), "detail": detail})
        if verbose:
            print(f"[{'OK ' if ok else 'FAIL'}] {name}  {detail}")

    rb = TourRobot(MockArena(seed=1), TourConfig(), base=None, log=None)
    gx, gy, unsafe = rb.uncovered_mask()
    rec("T1 只有原点一次检测时，环带全部未经排除", bool(unsafe.all()),
        f"{gx.size} 个环带格点，未排除 {int(unsafe.sum())} 个")

    sk = rb.ring_skeleton()
    P = np.asarray([rb.ring_xy(a, r) for (a, r) in sk] + [(0.0, 0.0)], float)
    d = np.sqrt(np.min((gx[:, None] - P[None, :, 0]) ** 2
                       + (gy[:, None] - P[None, :, 1]) ** 2, axis=1))
    rec("T2 原点 + 环带骨架即可覆盖环带（最大未覆盖 <= 1000 m）",
        float(d.max()) <= 1000.0,
        f"骨架 {len(sk)} 点，最大未覆盖 {float(d.max()):.1f} m")

    # T3 角向单调：锁定方向后，forward_ring 的极角严格递增
    rb3 = TourRobot(MockArena(seed=2), TourConfig(), base=None, log=None)
    rb3.arena.enter()
    rb3.ring_dir = 1.0
    rb3.ring_cursor_a = 0.3
    seq = rb3.forward_ring(1.0)
    angs = [math.atan2(w["xy"][1], w["xy"][0]) % (2 * math.pi) for w in seq]
    ok3 = len(seq) > 0 and all((b - a) % (2 * math.pi) > 0 for a, b in zip(angs, angs[1:]))
    rec("T3 骨架停点按角向单调推进（不折返的结构性保证）", ok3,
        f"{len(seq)} 个停点，角向增量 "
        f"{[round(math.degrees((b - a) % (2 * math.pi)), 1) for a, b in zip(angs, angs[1:])][:6]}…")

    # T4 端到端
    res = []
    for k in range(cases):
        a = MockArena(seed=seed + 100 * k)
        r4 = TourRobot(a, TourConfig(), base=None, log=None)
        res.append(r4.run())
    rec("T4 mock 端到端跑通且清除率 > 0.8",
        all(r["clear_ratio"] is not None and r["clear_ratio"] > 0.8 for r in res),
        "; ".join(f"seed{seed+100*k}: {r['cleared']}/{r['n_sources']} "
                  f"T={r['virtual_time_s']:.0f}s" for k, r in enumerate(res)))

    # T5 完工判据与真值一致
    bad = [seed + 100 * k for k, r in enumerate(res)
           if r["complete_proof"] and r["cleared"] != r["n_sources"]]
    rec("T5 判定『靶区无残留源』时确实全部清除", not bad, f"反例 {bad or '无'}")

    # T6 行程相对"结构下界"的倍数
    #    下界 = TSP(原点 + 骨架停点 + 全部真源位置)（预知全部源位、且骨架点免费给的理想航路）
    #    实测 30 局该比值中位数约 1.2–1.5；最坏出现在"源数取到上限 16 个"的个别案例上
    #    （路点最多、组合最乱，实测 seed 20261113 约 1.9）。这是"滚动时域在线决策"
    #    相对"离线最优"的真实差距，也是尾部风险，故留到 2.1 作为报警线。
    worst, ratios = 1.0, []
    for k, r in enumerate(res):
        a = MockArena(seed=seed + 100 * k)
        pts = [(rr * math.cos(2 * math.pi * i / n), rr * math.sin(2 * math.pi * i / n))
               for (rr, n) in TourConfig().cover_rings for i in range(int(n))]
        pts += [(x.x, x.y) for x in a.sources]
        lb = _nn_2opt_len(pts)
        ratios.append(r["travel_m"] / max(lb, 1.0))
        worst = max(worst, ratios[-1])
    rec("T6 行程不超过『骨架 + 源位最优航路』的 2.1 倍（30 局中位数 1.2–1.5）",
        worst <= 2.1,
        f"最坏 {worst:.2f}，逐局 {[round(x, 2) for x in ratios]}")

    if verbose:
        print(f"\n自检总结：{'全部通过' if ok_all else '存在失败项'}")
    return {"ok": ok_all, "checks": out}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="问题3 统一滚动航路策略自检")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--cases", type=int, default=3)
    args = ap.parse_args()
    r = selfcheck(cases=args.cases)
    raise SystemExit(0 if r["ok"] else 1)
