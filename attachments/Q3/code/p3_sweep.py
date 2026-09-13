"""问题 3 的"覆盖扫圈"策略（与 `p3_robot.P3Robot` 的"期望场贪心"并列可选）。

设计动机（来自 2026-09-11 两局在线演练的实测）
--------------------------------------------
1. **不必"发现即清除"**：实测第 2 局的 14 个源在 3353 s 就全部清完，程序又空转
   1932 s（37%）——因为它不知道"已经清完"。反过来，第 1 局有 3114 s（45%）花在
   "场上一条方位都没有"的阶段，决策场 `E_norm ≡ 0`、score 只剩距离项，
   机器人就在圆心附近 500 m 步长乱蹭。
2. **"1000 m 已扫过"是可以判定的**：干扰源的有效接收半径 ≥ `R_RECV_MIN = 1000 m`。
   因此"某点距所有已扫检测点都 > 1000 m"⇒"该点不可能存在未清除的源"是**严格**的。
   把靶区按 1000 m 的覆盖半径铺开，就能得到一个**可证明完备**的扫描航线：
   走完即"靶区内不存在未清除源"，可以立刻 `/exit`，不需要盲探、不需要走回头路。
3. **原点那一次检测白送了内圈**：原点已扫 ⇒ 半径 1000 m 以内不必再去。
   需要覆盖的只剩 r ∈ [1000, 1800] 的环带，因此停靠点不必贴边，
   沿 r ≈ 1100 / 1500 / 1800 三圈铺开即可（见 :func:`lattice_candidates`）。

策略本体
--------
    score(g) = w_cover · (g 的 1000 m 圆内"未覆盖"面积占比)
             − w_dir   · cos(方位 − 期望前进方位)      # 保持顺时针推进，不回头
             − w_near  · (1 − d/最大可能距离)          # 就近取点，别横穿靶区

    pick = argmax score     （只从格点候选里选；已停靠点 300 m 邻域排除）

每到一个停靠点：先 `clear_targets()`（顺路清除已经定位好的源），再测该点值得测的频道。
覆盖率达到 100%（或时间不够）就收工——**因为此时可以确定没有残留源**。
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from p3_arena import (  # noqa: E402
    ArenaError, R_ARENA, R_CLEAR, R_RECV_MIN, R_RECV_MAX, T_CLEAR_FAIL, T_CLEAR_OK,
    T_MEASURE, T_SWITCH, V_ROBOT,
)
from p3_robot import P3Config, P3Robot  # noqa: E402
from p3_expect_field import (  # noqa: E402
    best_refine_point, exact_expected_diameter, ray_source_samples,
)


# --------------------------------------------------------------------------
# 候选停靠点：同心环格点（"扫圈"航线就是在这些点之间走）
# --------------------------------------------------------------------------
DEFAULT_RINGS = ((1100.0, 8),)
"""``(半径 m, 该圈上的点数)``。默认只用一圈；如有需要可在后面追加"补漏圈"。

为什么一圈就够 —— 这是把题目的物理条件用足之后的结论：

* 干扰源有效接收半径 ≥ ``R_RECV_MIN = 1000 m`` ⇒ 某点距**所有**检测点都 > 1000 m 时，
  该处不可能存在未清除源（**严格**，不是启发式）；
* 原点已经测过一次（20 个频道全扫），所以 **r ≤ 1000 m 的整个内圈不必再去**；
* 于是只需要覆盖环带 r ∈ [1000, 1800]。数值枚举（`python src/p3_sweep.py --coverage`）：

  | 单圈 | 环带内最大未覆盖距离 | 30 局虚拟时间 | 30 局清除率 | 30 局全清 |
  |---|---|---|---|---|
  | **r=1100, n=8（默认）** | **853 m** | **4243 s** | 0.978 | 23/30 |
  | r=1150, n=8 | — | 4237 s | 0.970 | 21/30 |
  | r=1250, n=8 | 788 m | 4516 s | 0.973 | 22/30 |
  | r=1400, n=8 | 721 m | 4621 s | 0.981 | **25/30** |

  都完备（< 1000 m）。**r=1100 最快、全清数居中**；r=1400 最稳（全清 25/30）但慢 9%。
  若把"全清"看得比时间更重，可一行改成 `DEFAULT_RINGS = ((1400.0, 8),)`。
"""


def lattice_candidates(rings=DEFAULT_RINGS, stagger=True):
    """同心环格点：``[(x, y), ...]``。相邻环之间做半格错开，避免放射状缝隙。"""
    out = []
    for k, (r, n) in enumerate(rings):
        off = (math.pi / n) if (stagger and k % 2 == 1) else 0.0
        for i in range(int(n)):
            a = off + 2.0 * math.pi * i / n
            out.append((float(r) * math.cos(a), float(r) * math.sin(a)))
    return out


def rotate_lattice(cand, level, frac, ring_n):
    """把某个圈的候选点整体旋转 ``frac`` 个站位（第 2 圈错开半格用）。"""
    out = []
    step = 2.0 * math.pi / max(int(ring_n), 1)
    for k, (x, y) in enumerate(cand):
        a = math.atan2(float(y), float(x)) + frac * step
        r = math.hypot(float(x), float(y))
        out.append((r * math.cos(a), r * math.sin(a)))
    return out


def coverage_report(pts, cover_r=R_RECV_MIN, step=25.0, r_arena=R_ARENA,
                    r_inner=0.0):
    """给定停靠点集合，返回 ``(最大未覆盖距离, 未覆盖面积占比, 覆盖率)``。

    "未覆盖距离" = 评估区内某点到最近停靠点的距离；它 > ``cover_r`` 即说明该处
    若有源则必然已被听到（源的接收半径 ≥ cover_r）—— 所以这是**完备性度量**。

    ``r_inner``：只评估 ``r_inner ≤ |p| ≤ r_arena`` 的环带。原点已扫过时，
    ``r ≤ R_RECV_MIN`` 的内圈无需再覆盖，评估环带才是正确的口径。
    """
    R = float(r_arena)
    xs = np.arange(-R, R + 1e-9, step)
    GX, GY = np.meshgrid(xs, xs)
    rr = np.hypot(GX, GY)
    m = (rr <= R + 1e-9) & (rr >= float(r_inner) - 1e-9)
    gx, gy = GX[m], GY[m]
    if not pts:
        return float("inf"), 1.0, 0.0
    P = np.asarray(pts, float)
    d2 = ((gx[:, None] - P[None, :, 0]) ** 2 + (gy[:, None] - P[None, :, 1]) ** 2)
    dmin = np.sqrt(np.min(d2, axis=1))
    unc = dmin > float(cover_r)
    return float(np.max(dmin)), float(unc.mean()), float(1.0 - unc.mean())


# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------
@dataclass
class SweepConfig(P3Config):
    """在 `P3Config` 上追加"扫圈"参数（继承 `P3Config` 的全部字段 + 下面这些）。"""
    sweep_rings: tuple = DEFAULT_RINGS
    cover_radius_m: float = R_RECV_MIN   # 覆盖判定半径（有效接收半径下界）
    cover_w: float = 1.0                 # 未覆盖收益的权重
    near_w: float = 0.25                 # 就近权重（避免横穿靶区）
    jump_w: float = 0.00035              # 跳跃惩罚（每米），抑制"绕回已走过的扇区"
    min_gain: float = 0.25               # 低于此边际收益就不值得专门跑一趟
    stop_visited_radius_m: float = 300.0  # 已停靠点邻域排除半径
    # ---- 清除时机 ----
    clear_mode: str = "detour"           # detour（只清顺路的）| station（每站都清）| none
    clear_detour_max_m: float = 350.0    # detour 模式：绝对距离上限（m）
    onlap_clear: bool = False            # **边绕边清**：一圈走完就清完，不再有"圈后统一清除"
    onlap_cos: float = 0.10              # 只在"前方"这个夹角内（cos）的候选才顺路处理
    onlap_max_m: float = 1500.0          # 候选(或单方位源的推算位置)离本站的最远距离
    onlap_min_m: float = 120.0           # 比这更近的目标不单独绕（到站测量时顺手清）
    onlap_single: bool = True            # 单方位频道也用"推算位置"参与顺路判定
    onlap_after_ring: bool = False       # 走完圈后再清一次剩余的已定位目标
    onlap_step_m: float = 320.0          # ★"取第二方位"的侧移步长上限（m）：小步就够，
                                         #   不要跑到推算位置去（实测原来跑 1400-1600 m）
    onlap_step_frac: float = 0.25        # 侧移步长 = min(onlap_step_m, 该比例 × 到目标的距离)
    onlap_min_step_m: float = 140.0      # 步长下限（太短交会角没改善）
    onlap_angle_deg: float = 50.0        # 侧移方向与旧视线的夹角（交会角 ≈ 这个值）
    onlap_max_steps: int = 3             # 最多走几步去把区域压到可清除
    skip_station_near_target_m: float = 260.0  # 站位离"顺路目标"这么近时可考虑省掉该站
    skip_station_max_uncovered: float = 1150.0  # 省站后"最大未覆盖距离"仍须低于它
    start_toward_sources: bool = False   # 第一站朝"信息方向"出发（实测有 bug 且无收益，见 review §6.2）
    debug_onlap: bool = False            # 打印"边绕边清"的候选判定过程
    start_min_sources: int = 1           # 至少这么多条单方位才据此定起始方向
    # 下面两个"顺路"判据默认**关闭**（实测在 30 局上都没有正向收益，见 review/p3-sweep-design.md §6）：
    enroute_min_cos: float = 1.1         # >1 表示关闭"按方向判定顺路"（仅用 350 m 兜底）
    enroute_max_m: float = 1400.0        # 按方向判定时的绕行距离上限
    initial_locate: bool = True          # **开场先按期望场行动一次**
    initial_locate_max_m: float = 1400.0  # 只对"首条方位距离 ≤ 此值"的频道做开场定点
    batch_locate: bool = False           # 多个"只有一条方位"的频道**合并规划**第二测点
                                         # （实测每局触发约 2 次、每次确实更省，但会把
                                         #   机器狗拉离环线，整局行程反而 +12%，默认关）
    batch_max_m: float = 700.0           # 聚类阈值：彼此最优测点相距 ≤ 此值才算"可以合并"
    batch_min_channels: int = 2          # 至少这么多条单方位才值得合并规划
    batch_max_rounds: int = 6            # 一局里最多做几次"合并定位"
    batch_every: int = 2                 # 每走这么多站就考虑一次合并定位
    batch_min_gain_s: float = 60.0       # 联合方案至少要省这么多秒才值得做
    bear_cone_deg: float = 0.0           # >0 才启用"单方位频道按行进方向就地补测"
    sweep_all_rounds: int = 1            # 完整走圈的遍数（第 2 遍只补缺口）
    lap_offsets: tuple = (0.0, 0.5)      # 每一圈的角向错开量（单位：站位格）
    measured_revisit_gap_m: float = 400.0  # 已测过该频道但没听到 → 换这么远再测


# --------------------------------------------------------------------------
# 机器狗：覆盖扫圈
# --------------------------------------------------------------------------
class SweepRobot(P3Robot):
    """覆盖扫圈。注意：`SweepConfig` 是 dataclass，其额外参数直接传给 `P3Config` 的
    ``__init__``（会把未知键忽略），所以覆盖参数通过 ``cfg`` 对象设置，见 :meth:`_apply_cfg`。
    """

    def _apply_cfg(self, cfg):
        self.cfg = cfg

    def __init__(self, arena, cfg: SweepConfig | None = None, base=None, log=None):
        super().__init__(arena, cfg or SweepConfig(), base=base, log=log)
        self.cand = np.asarray(lattice_candidates(self.cfg.sweep_rings), float)
        # 每个候选点属于第几圈（0 = 主圈；>0 = 补漏圈，只在主圈走完还有缺口时启用）
        self.cand_level = []
        for k, (_r, n) in enumerate(self.cfg.sweep_rings):
            self.cand_level += [k] * int(n)
        self.cand_level = np.asarray(self.cand_level, int)
        self.ring_n = int(self.cfg.sweep_rings[0][1]) if self.cfg.sweep_rings else 0
        self.ring_r = float(self.cfg.sweep_rings[0][0]) if self.cfg.sweep_rings else 0.0
        self.ring_dir = 0.0        # 0 = 还没出发；±1 = 已定的绕圈方向
        self.ring_last_a = None    # 上一站的极角
        self.ring_laps = 0
        self.lap = 0               # 第几圈（0 起）：每圈把站位错开 lap_offsets[lap] 格
        self._last_dir = None      # 上一段的行进方向（用于"单方位频道是否顺路补测"）
        self.visited = []          # **真实**到过的位置（含清除绕行点），用于排除已停靠点
        self.meas_pts = []         # **真实做过的检测**位置，用于可证明的覆盖度评估
        self._cg = None            # 覆盖度评估用细网格（缓存）
        self.coverage = 0.0
        self.max_uncov_dist = float("inf")
        self.phase = "scan"

    # ---------------- 覆盖度 ----------------
    def _grid(self):
        if self._cg is None:
            step = 25.0
            R = R_ARENA
            xs = np.arange(-R, R + 1e-9, step)
            GX, GY = np.meshgrid(xs, xs)
            m = np.hypot(GX, GY) <= R + 1e-9
            self._cg = (GX[m], GY[m])
        return self._cg

    def note_pos(self, ch=None):
        """记录一次**真实做过的检测**位置，用于覆盖度评估。

        为什么要记"检测位置"而不是"到过的位置"：清除阶段会把机器人带到源附近的
        试探格点，那些点**确实测过**（我们在那儿测到方位、也听过无信号），所以算有效；
        但"到过"并不等于"测过每个频道"，所以覆盖度必须按**检测记录**算才是可证明的：
        "每个靶区点到某个检测点的距离 ≤ 1000 m" ⇒ 该点若有源且当时在测它，必已被听到。
        """
        p = (float(self.arena.pos[0]), float(self.arena.pos[1]))
        if not self.meas_pts or math.dist(self.meas_pts[-1], p) > 1.0:
            self.meas_pts.append(p)

    def coverage_now(self):
        """覆盖率 + 最大未覆盖点距最近**检测点**的距离（可证明完备的判据）。"""
        gx, gy = self._grid()
        pts = list(self.meas_pts) or list(self.scan_points)
        if not pts:
            return 0.0, float("inf")
        P = np.asarray(pts, float)
        d2 = ((gx[:, None] - P[None, :, 0]) ** 2 + (gy[:, None] - P[None, :, 1]) ** 2)
        dmin = np.sqrt(np.min(d2, axis=1))
        unc = dmin > float(self.cfg.cover_radius_m)
        self.max_uncov_dist = float(np.max(dmin))
        self.coverage = float(1.0 - unc.mean())
        return self.coverage, self.max_uncov_dist

    # ---------------- 选点（沿圈单调推进，不回头） ----------------
    def _cand_xy(self, idx):
        """第 ``lap`` 圈、第 ``idx`` 个候选点的坐标（按 ``lap_offsets`` 旋转）。"""
        offs = self.cfg.lap_offsets or (0.0,)
        frac = float(offs[min(self.lap, len(offs) - 1)])
        c = self.cand[idx]
        if abs(frac) < 1e-12:
            return float(c[0]), float(c[1])
        step = 2.0 * math.pi / max(self.ring_n, 1)
        a = math.atan2(float(c[1]), float(c[0])) + frac * step
        r = math.hypot(float(c[0]), float(c[1]))
        return float(r * math.cos(a)), float(r * math.sin(a))

    def pick_stop(self, level=0):
        """选下一站：**沿当前绕圈方向单调推进**，只在"还没覆盖"的站里挑。

        打分 ``score = w_cover·边际覆盖 − w_near·(d/2R) − w_jump·前向角增量(米)``，
        并对"反向站"直接剔除（``adv < min_step``）。这样航线就自然是
        "走一段 → 沿一个方向绕圈 → 走满一圈收工"，不会出现来回横跳或走回头路。

        ``level``：只用第 ``level`` 圈（以及更低层）的候选点。主圈走完仍有缺口时，
        调用方会升到补漏圈。
        """
        gx, gy = self._grid()
        P = np.asarray(self.visited, float) if self.visited else None
        if P is None:
            covered = np.zeros(gx.size, bool)
        else:
            d2 = ((gx[:, None] - P[None, :, 0]) ** 2 + (gy[:, None] - P[None, :, 1]) ** 2)
            covered = np.min(d2, axis=1) <= float(self.cfg.cover_radius_m) ** 2
        p = np.asarray(self.arena.pos, float)
        step = 2.0 * math.pi / max(self.ring_n, 1)
        min_step = 0.35 * step          # 至少要往前走这么多角度
        best, best_score, best_info = None, -1e18, {}
        for idx, c0 in enumerate(self.cand):
            if int(self.cand_level[idx]) > int(level):
                continue
            c = self._cand_xy(idx)
            dc = float(np.hypot(c[0] - p[0], c[1] - p[1]))
            if dc < self.cfg.min_move:
                continue
            if any(float(np.hypot(c[0] - q[0], c[1] - q[1]))
                   < self.cfg.stop_visited_radius_m for q in self.scan_points):
                continue
            in_disk = ((gx - c[0]) ** 2 + (gy - c[1]) ** 2) <= float(self.cfg.cover_radius_m) ** 2
            cnt = int(np.count_nonzero(in_disk))
            if cnt == 0:
                continue
            gain = float(np.count_nonzero(in_disk & ~covered)) / cnt     # [0,1]
            if gain < self.cfg.min_gain:
                continue
            a = math.atan2(float(c[1]), float(c[0]))
            if self.ring_last_a is None:
                adv = 0.0                       # 第一站：方向未定，就近去
            else:
                raw = a - self.ring_last_a
                if self.ring_dir >= 0:          # 未定方向时按"逆时针为正"试探
                    adv = (raw + 2.0 * math.pi) % (2.0 * math.pi)
                else:
                    adv = -(((-raw) + 2.0 * math.pi) % (2.0 * math.pi))
                if adv < min_step:
                    continue                    # 反向或原地：不回头
            near_term = 1.0 - dc / (2.0 * R_ARENA)
            jump = max(0.0, adv) * self.ring_r
            score = (self.cfg.cover_w * gain + self.cfg.near_w * near_term
                     - self.cfg.jump_w * jump)
            if score > best_score:
                best, best_score = c, score
                best_info = {"gain": gain, "dist": dc, "adv_deg": math.degrees(adv),
                             "jump_m": jump, "level": int(self.cand_level[idx]),
                             "lap": self.lap,
                             "n_new": int(np.count_nonzero(in_disk & ~covered)),
                             "cnt": cnt}
        return best, best_info

    def commit_stop(self, c):
        """记录这一站，并据此确定/保持绕圈方向。"""
        a = math.atan2(float(c[1]), float(c[0]))
        step = 2.0 * math.pi / max(self.ring_n, 1)
        if self.ring_last_a is None:
            self.ring_last_a = a
            return
        raw = (a - self.ring_last_a + math.pi) % (2.0 * math.pi) - math.pi
        if self.ring_dir == 0.0:
            # 第一段的方向即定为绕圈方向；角度增量接近 0（小于半格）时沿用正向
            self.ring_dir = 1.0 if raw >= 0 else -1.0
        if (self.ring_dir > 0 and raw < -step / 2.0) or \
           (self.ring_dir < 0 and raw > step / 2.0):
            self.ring_laps += 1        # 说明已经绕回这一圈的起点附近
        self.ring_last_a = a

    # ---------------- 到站动作 ----------------
    # ---------------- 何时可以确定"已经清完了" ----------------
    def all_heard(self):
        """是否每个频道都"给出过明确结论"：已清除，或已测到过方位。

        这是比"覆盖 100%"更早、也更容易达到的**完工判据**：一圈走下来，
        每个频道要么被测到过方位（说明确有源、随后会被清掉），要么一次都没测到。
        配合"整圈已走完"这一事实（整圈 ⇒ 每个靶区点都距某个检测点 ≤ 1000 m
        ⇒ 若有源必被听到过），就能断定**没有再多的源了**。
        """
        for rec in self.recs.values():
            if rec.cleared:
                continue
            if rec.n_bearings == 0 and not rec.meas_pts:
                return False
        return True

    def channels_here(self, pos=None, incoming_dir=None):
        """本停点值得测的频道。

        * 还缺方位的频道（未清除且方位数 < 2）一律要测；
        * **只有一条方位、且那条第方位大致指向"我们的前进方向"** 的频道也测
          —— 从当前位置看它、和第一次看它的方向差了接近 90°，交会角好，
          拿到第二条方位就能当场定位并顺路清掉（对应"不要事后走回头路"）；
        * "以前测过但没听到"的频道，若本点到它所有历史检测点都 ≥
          ``measured_revisit_gap_m`` / ``repeat_gap_m``，也再测一次。

        注意用的是**真实位置** ``pos``（清除绕行之后的位置），否则会把"计划坐标"
        当成已测过，从而在新站点漏测大量频道。
        """
        p = np.asarray(self.arena.pos if pos is None else pos, float)
        cos_need = math.cos(math.radians(self.cfg.bear_cone_deg))
        out = []
        for ch in self.needed_channels():
            rec = self.recs[int(ch)]
            if not rec.meas_pts:
                out.append(int(ch))
                continue
            gap = (self.cfg.repeat_gap_m if rec.pts
                   else self.cfg.measured_revisit_gap_m)
            d = min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in rec.meas_pts)
            if d >= gap:
                out.append(int(ch))
                continue
            # 已有 1 条方位但"离历史检测点太近"被 gap 挡住的频道：
            # 若那条方位与行进方向夹角 < bear_cone_deg，就地补第二方位。
            if rec.n_bearings == 1 and incoming_dir is not None:
                (sx, sy), a = rec.pts[-1], rec.svds[-1]
                u = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
                if float(np.asarray(incoming_dir, float) @ u) >= cos_need:
                    out.append(int(ch))
        return out

    # ---------------- 边绕边清：候选目标（含"只有一条方位"的推算位置）----------------
    def _predicted_source(self, rec):
        """给"只有一条方位"的频道一个**位置估计**，好让它在顺路判定里参与竞争。

        做法：把那条视线与"以原点为心、半径 ``R_RECV_MAX`` 的圆"求交，取较远的交点。
        这个估计误差最大约 ±R_RECV_MAX·tan1° ≈ 26 m 的横向、以及沿视线的未知距离，
        但用来判断"这个源是不是在我前方、值不值得顺路去清"已经足够。
        """
        (sx, sy), a = rec.pts[-1], rec.svds[-1]
        u = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
        S = np.array([float(sx), float(sy)])
        b = float(S @ u)
        c = float(S @ S) - (R_ARENA * R_ARENA)
        disc = b * b - c
        t = (-b + math.sqrt(disc)) if disc > 0 else R_RECV_MAX
        t = min(t, R_RECV_MAX * 1.0)
        return S + t * u

    def _onlap_candidates(self, x, y, travel_dir):
        """本段"顺路就该处理"的候选，按"越正前方、越近"排序。

        返回 ``[(kind, ch, point, cos, dist), ...]``，``kind`` ∈ {``'clear'``, ``'locate'``}：

        * ``'clear'``：已经定位（≥2 条方位且有界）——直接去清；
        * ``'locate'``：**只有一条方位**——先按推算位置过去，在那儿补一条方位把它定住再清。
          这正是用户指出的缺口：旧实现只挑"已定位"的目标，于是前方那些"只测到一次"的
          点全被跳过，最后只能绕完圈再回头找。
        """
        out = []
        p = np.asarray((x, y), float)
        for (ch, rec, br) in self.clear_targets():
            c = np.asarray(br["center"], float)
            v, d = c - p, float(np.linalg.norm(c - p))
            if d > self.cfg.onlap_max_m or d < self.cfg.onlap_min_m:
                continue
            cs = 1.0 if d < 1e-9 else float((v / d) @ travel_dir)
            if cs >= self.cfg.onlap_cos:
                out.append(("clear", ch, c, cs, d))
        if self.cfg.onlap_single:
            for ch, rec in self.recs.items():
                if rec.cleared or rec.n_bearings != 1:
                    continue
                if rec.clear_fail > 0:      # 刚失败过，先换别的
                    continue
                c = self._predicted_source(rec)
                v, d = c - p, float(np.linalg.norm(c - p))
                if d > self.cfg.onlap_max_m or d < self.cfg.onlap_min_m:
                    continue
                cs = 1.0 if d < 1e-9 else float((v / d) @ travel_dir)
                if cs >= self.cfg.onlap_cos:
                    out.append(("locate", ch, c, cs, d))
        out.sort(key=lambda t: (-t[3], t[4]))
        return out

    def _bearing_step(self, rec, p):
        """**小步定位点**：从当前位置沿"与旧视线成 ≈ onlap_angle_deg"的方向走一小步。

        * 交会角就是这个夹角（几何上最优是 90°，但 50–60° 已经把横向误差压到 1/sin 倍，
          再大就要多走路）；
        * 步长取 ``min(onlap_step_m, frac × 到目标推算位置的距离)`` 并有下限与上限。
        旧实现直接跑到"推算位置"（距离上限 R_RECV_MAX=1500 m！），一次侧移就 1400–1600 m，
        这正是路径图里那些长支线的来源。
        """
        (sx, sy), a = rec.pts[-1], rec.svds[-1]
        u = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
        p = np.asarray(p, float)
        # 目标大致在视线上、距离未知：用"当前位置沿视线方向的投影"当作尺度
        t_hat = float((p - np.array([sx, sy])) @ u)
        t_hat = min(max(t_hat, 200.0), R_RECV_MAX)
        ang = math.radians(self.cfg.onlap_angle_deg)
        best = None
        for sgn in (+1.0, -1.0):
            perm = np.array([u[0] * math.cos(sgn * ang) - u[1] * math.sin(sgn * ang),
                             u[0] * math.sin(sgn * ang) + u[1] * math.cos(sgn * ang)])
            step = min(self.cfg.onlap_step_m,
                       max(self.cfg.onlap_min_step_m, self.cfg.onlap_step_frac * t_hat))
            q = p + perm * step
            if np.hypot(*q) > R_ARENA - 1.0:
                continue
            d = float(np.linalg.norm(q - p))
            if best is None or d < best[0]:
                best = (d, q)
        return (best[1] if best else None), (best[0] if best else None)

    def _locate_and_clear(self, ch, predicted):
        """顺路把一个"只有一条方位"的频道定位并清掉：**小步侧移 → 量 → 再清**。

        与旧实现的区别：旧版走到"推算位置"（可能 1500 m 外）再量，量完还常常不在
        清除半径内，于是又要侧移/试探，来回好几趟；新版每次只走一小步、
        量一次就把区域压小一半以上，通常 1 步就能进清除流程。
        """
        rec = self.recs[int(ch)]
        n = 0
        for _step in range(max(1, self.cfg.onlap_max_steps)):
            if rec.cleared or self.aborted:
                break
            br = self.bounded_region(rec)
            if br is not None and br["radius"] <= self.cfg.clear_max_radius_m:
                self.phase = "clear"
                n += 1 if self.clear_target(int(ch), rec) else 0
                self.phase = "scan"
                if rec.cleared:
                    return n
            q, trav = self._bearing_step(rec, self.arena.pos)
            if q is None or trav is None:
                break
            if not self.can_afford(trav / V_ROBOT + T_MEASURE + T_SWITCH + 10.0):
                break
            self.log(f"  顺路定位频道{ch}：侧移 {trav:.0f} m 到 "
                     f"({q[0]:.0f},{q[1]:.0f}) 取方位"
                     f"（步长上限 {self.cfg.onlap_step_m:.0f} m，交会角 "
                     f"≈{self.cfg.onlap_angle_deg:.0f}°）")
            resp = self.measure(float(q[0]), float(q[1]), int(ch))
            self.note_pos()
            if resp.get("measure_result") == "near":
                return n + (1 if self.do_clear(float(q[0]), float(q[1]), int(ch)) else 0)
            if resp.get("measure_result") != "direction":
                rec.no_signal += 1
                break
        br = self.bounded_region(rec)
        if br is not None and not rec.cleared:
            self.phase = "clear"
            n += 1 if self.clear_target(int(ch), rec) else 0
            self.phase = "scan"
        return n

    def _onlap_handle(self, kind, ch, pt):
        """顺路处理一个候选：``locate`` 走小步补方位再清，``clear`` 直接清。"""
        rec = self.recs[int(ch)]
        if kind == "locate":
            return self._locate_and_clear(int(ch), pt)
        br = self.bounded_region(rec)
        if br is None:
            return 0
        self.phase = "clear"
        n = 1 if self.clear_target(int(ch), rec) else 0
        self.phase = "scan"
        return n

    # ---------------- 起始站：朝"信息最多的方向"出发 ----------------
    def pick_start_stop(self):
        """把第一站定在"单方位源聚集的那个方向"，并据此确定绕圈方向。

        为什么重要：旧实现的第一站恒为格点里角度最小的那个（正东），于是当所有方位
        都指向西/南时，机器人**背着源**出发 —— 一整圈里都要绕回来（用户看到的
        "绕了两圈"里就有这一段）。原点的 20 次检测已经把每个源的方向给出来了，
        用它来定起始方向是"免费的"。
        """
        if not self.cfg.start_toward_sources:
            return None, None
        vecs = []
        for rec in self.recs.values():
            if rec.cleared or rec.n_bearings != 1:
                continue
            p = self._predicted_source(rec)
            d = float(np.hypot(*p))
            if d < 1e-6:
                continue
            vecs.append(p / d)
        if len(vecs) < self.cfg.start_min_sources:
            return None, None
        mean = np.sum(np.asarray(vecs, float), axis=0)
        if float(np.linalg.norm(mean)) < 1e-6:
            return None, None
        a_mean = math.atan2(float(mean[1]), float(mean[0]))
        # 在格点里挑与"信息方向"最接近的一站
        offs = self.cfg.lap_offsets or (0.0,)
        frac = float(offs[0])
        step = 2.0 * math.pi / max(self.ring_n, 1)
        best, best_d = None, None
        for idx in range(len(self.cand)):
            ang = math.atan2(float(self.cand[idx][1]), float(self.cand[idx][0])) + frac * step
            diff = abs((ang - a_mean + math.pi) % (2 * math.pi) - math.pi)
            if best_d is None or diff < best_d:
                best, best_d = idx, diff
        c = self._cand_xy(best)
        # 绕圈方向：选"下一站"更靠近信息方向的那个方向
        nxt = []
        for sgn in (+1, -1):
            j = (best + sgn) % len(self.cand)
            cj = self._cand_xy(j)
            nxt.append((abs((math.atan2(cj[1], cj[0]) - a_mean + math.pi)
                            % (2 * math.pi) - math.pi), sgn))
        self.ring_dir = 1.0 if nxt[0][0] <= nxt[1][0] else -1.0
        # 注意：**不要**在这里设置 ring_last_a —— 第一站的角度要由 commit_stop 记录，
        # 否则"单调前进"的约束会从"信息方向"起算，导致真正的第一站被当成"往回走"而全部淘汰。
        self.log(f"起始方向：{len(vecs)} 个频道只有单条方位，其平均方向 "
                 f"{math.degrees(a_mean):.0f}° -> 第一站定在 "
                 f"({c[0]:.0f},{c[1]:.0f})，绕圈方向 "
                 f"{'逆时针' if self.ring_dir > 0 else '顺时针'}")
        return c, best

    def _target_near_station(self, c):
        """如果有"已定位/可定位目标"的位置就在计划站位 ``c`` 附近，返回 ``(ch, center)``。

        用途：**用目标位置顶替环上站位**。清一个离站位 200 m 的源时，机器狗已经站在
        那一带并做过检测 —— 让这次检测顶替"专门跑到站位再测一次"，只要覆盖度仍然够，
        就省下一个路径点（用户指出的"两个点走一遍"）。
        """
        best = None
        cands = []
        for (ch, rec, br) in self.clear_targets():
            cands.append((ch, np.asarray(br["center"], float)))
        for ch, rec in self.recs.items():
            if rec.cleared or rec.n_bearings != 1 or rec.clear_fail > 0:
                continue
            cands.append((ch, self._predicted_source(rec)))
        for ch, ctr in cands:
            d = float(np.linalg.norm(ctr - np.asarray(c, float)))
            if d <= self.cfg.skip_station_near_target_m:
                if best is None or d < best[2]:
                    best = (ch, ctr, d)
        return best

    def station_skippable(self, c, alt_pts):
        """若用 ``alt_pts``（顺路已经会去的点）顶替站位 ``c`` 后，覆盖度仍然够，则返回 True。

        判据：去掉 ``c``、加上 ``alt_pts`` 后，"靶区内最大未覆盖距离"仍 <
        ``skip_station_max_uncovered``（比严格的 1000 m 留一点余地，因为这个判据在
        过程中会反复评估，留余量可以避免把后面的补测机会也一起砍掉）。
        """
        if not self.cfg.onlap_clear:
            return False
        try:
            cov_rep, _ = self.coverage_now()
        except Exception:
            return False
        keep = list(self.scan_points) + [(float(p[0]), float(p[1])) for p in alt_pts]
        keep = [q for q in keep if float(np.hypot(q[0] - c[0], q[1] - c[1]))
                > self.cfg.stop_visited_radius_m]
        if not keep:
            return False
        gx, gy = self._grid()
        P = np.asarray(keep, float)
        d2 = ((gx[:, None] - P[None, :, 0]) ** 2 + (gy[:, None] - P[None, :, 1]) ** 2)
        dmin = np.sqrt(np.min(d2, axis=1))
        if float(np.max(dmin)) > self.cfg.skip_station_max_uncovered:
            return False
        return True

    def _enroute_target(self, x, y, travel_dir):
        """挑一个"顺路"的目标：位于本段行进方向的前方（夹角 cos ≥ enroute_min_cos）。

        为什么不能只看绝对距离：站与站之间相距 842–2000 m，目标常常"就在前方 600–900 m"
        却离本站超过 350 m —— 旧判据直接跳过，最后只能绕完一圈再回头（就是"几乎转了两圈"
        的来源）。改成按**方向**判定后，这类目标会当场清掉，回程自然消失。
        """
        best, best_key = None, None
        for (ch, rec, br) in self.clear_targets():
            c = np.asarray(br["center"], float)
            v = c - np.asarray((x, y), float)
            d = float(np.linalg.norm(v))
            if d > self.cfg.enroute_max_m:
                continue
            cos = 1.0 if d < 1e-9 else float((v / d) @ travel_dir)
            if cos < self.cfg.enroute_min_cos:
                continue
            key = (-cos, d)       # 越"正前方"越好；同方向取近的
            if best_key is None or key < best_key:
                best, best_key = (ch, rec, br), key
        return best

    def visit_stop(self, x, y, travel_dir=None, incoming_dir=None, next_dir=None):
        """移动到 (x,y) 并测量。

        ``travel_dir``：**本段**（上一站→本站）的行进方向；
        ``next_dir``：**下一段**（本站→下一站）的计划方向 —— 顺路判定要用它，
        因为到达本站后"朝本站的方向"已经是零向量（机器狗就站在站上）。

        **清除时机很关键**：第一版每站都调 `clear_phase()`，结果为了清一个源跑到
        靶区另一头，回来时"绕圈"已被打断、剩下的站点全被跳过（实测只清 6/10）。
        现在的 `detour` 模式按**方向**挑顺路目标（见 :meth:`_enroute_target`）：
        在前方就先清掉，背对行进方向的才留到一圈之后统一处理。
        """
        n = 0
        do_detour = (self.cfg.clear_mode == "detour" and not self.aborted)
        if self.cfg.clear_mode == "station" and not self.aborted:
            targets = self.clear_targets()
            if targets and self.can_afford(self.cfg.min_action_budget_s):
                self.phase = "clear"
                n += self.clear_phase()
                self.phase = "scan"
                self.note_pos()          # 清除绕行点也算一次有效检测点
        # ---- 先测本点（保证"这一站真的被扫过"），再顺路清除 ----
        if not self.aborted:
            p = np.asarray(self.arena.pos, float)
            if not self.meas_pts or math.dist(self.meas_pts[-1], tuple(p)) > 1.0:
                self.meas_pts.append((float(p[0]), float(p[1])))
            chans = self.channels_here(pos=p, incoming_dir=incoming_dir)
            if not chans:
                chans = [int(c) for c in self.needed_channels()]
            if chans:
                travel_cost = math.hypot(x - self.arena.pos[0],
                                         y - self.arena.pos[1]) / V_ROBOT
                avail = self.remaining() - self.cfg.time_reserve_s - travel_cost - 4.0
                kmax = max(1, int(avail // (T_MEASURE + T_SWITCH)))
                if len(chans) > kmax:
                    self.log(f"  剩余时间只够测 {kmax}/{len(chans)} 个频道")
                    chans = chans[:kmax]
                n += self.scan_at(float(x), float(y), chans)
                self.note_pos()

        # ---- 边绕边清：本点测完后，把"前方该清的"清掉（含只有一条方位的）----
        if self.cfg.debug_onlap:
            self.log(f"    [onlap] 本站 ({x:.0f},{y:.0f}) 当前 pos="
                     f"({self.arena.pos[0]:.0f},{self.arena.pos[1]:.0f}) "
                     f"onlap_clear={self.cfg.onlap_clear} aborted={self.aborted}")
        if self.cfg.onlap_clear and not self.aborted:
            guard = 0
            while guard < 4 and not self.aborted:
                guard += 1
                d_now = None
                if next_dir is not None:
                    d_now = np.asarray(next_dir, float)      # 用"计划前往的下一站"方向
                else:
                    c0 = np.asarray(self.arena.pos, float)
                    v = np.asarray((x, y), float) - c0
                    dv = float(np.linalg.norm(v))
                    if dv > 1e-6:
                        d_now = v / dv
                if d_now is None:
                    break
                cands = self._onlap_candidates(float(x), float(y), d_now)
                if self.cfg.debug_onlap:
                    self.log(f"    [onlap] 本站 ({x:.0f},{y:.0f}) 行进方向 "
                             f"{math.degrees(math.atan2(d_now[1], d_now[0])):.0f}°，"
                             f"候选 {[(k, ch, round(cs, 2), round(d)) for k, ch, _p, cs, d in cands[:3]]}")
                if not cands:
                    break
                kind, ch, pt, cs, d = cands[0]
                if not self.can_afford(self.cfg.min_action_budget_s + 20.0):
                    break
                n += self._onlap_handle(kind, ch, pt)
                self.note_pos()

        # ---- 兼容旧行为：按方向/距离的"顺路清除" ----
        if do_detour and not self.aborted:
            tgt = self._enroute_target(x, y, travel_dir) if travel_dir is not None else None
            if tgt is None:               # 方向判据没命中时，保留"很近就清"的兜底
                for t in self.clear_targets():
                    if math.dist((x, y), t[2]["center"]) <= self.cfg.clear_detour_max_m:
                        tgt = t
                        break
            if tgt is not None and self.can_afford(self.cfg.min_action_budget_s):
                self.phase = "clear"
                self.log(f"  顺路清除频道{tgt[0]}（中心距本站 "
                         f"{math.dist((x, y), tgt[2]['center']):.0f} m）")
                n += self.clear_target(int(tgt[0]), tgt[1])
                self.phase = "scan"
                self.note_pos()
        return n

    # ---------------- 开场 / 批量：按期望场行动 ----------------
    def _singletons(self, max_r=None):
        """"只有一条方位"且未清除的频道（可选限制首条方位距离）。"""
        out = []
        for ch, rec in self.recs.items():
            if rec.cleared or rec.n_bearings != 1:
                continue
            if max_r is not None and math.hypot(rec.pts[0][0], rec.pts[0][1]) > max_r:
                continue
            out.append(int(ch))
        return out

    def _field_batch_locate(self, reason=""):
        """**按期望场行动**：把当前所有"只有一条方位"的频道**合并**规划第二测点。

        关键认识：**一个测点可以同时给多个源提供好的交会几何**。问题 2 的结论是
        "最优第二检测点在斜前方约 1.2–1.3 km、与源方向成 ±30° 的两翼"，而这些"两翼"
        对不同方向的源常常落在同一片区域。所以：

        1. 对每个待定频道求**局部最优第二测点**（`best_refine_point`，代价里含
           "测完还要往回走多远"）；
        2. **聚类**：彼此最优测点相距 ≤ ``batch_max_m`` 的频道算一批；
        3. 每批用一个**共同测点**（各成员最优点的中点/本身，取联合代价最小者）；
        4. 去那儿按批测一遍，然后立刻清除已经定下来的目标。

        这样一次移动能定住好几个源，而不是"为一个源跑一趟、再为一个源跑一趟"。
        """
        if not self.cfg.batch_locate or self.base is None or self.aborted:
            return 0
        if self.stats.get("n_batch", 0) >= self.cfg.batch_max_rounds:
            return 0
        pend = (self._singletons(max_r=self.cfg.initial_locate_max_m)
                if reason == "开场" else self._singletons())
        if len(pend) < self.cfg.batch_min_channels:
            return 0

        per = {}
        for ch in pend:
            rec = self.recs[ch]
            p, info = best_refine_point(rec.pts, rec.svds, self.pos, None, n_t=60,
                                        radii=(150.0, 300.0, 500.0, 800.0),
                                        travel_cap_m=self.cfg.refine_travel_cap_m)
            if p is None:
                continue
            per[ch] = {"p": np.asarray(p, float), "info": info, "E": None}
        if len(per) < self.cfg.batch_min_channels:
            return 0

        # ② 聚类：**完全连接**（与组内每个成员都要够近），避免"链式"把不相干的点串成一批
        groups = []
        for ch, d in per.items():
            for g in groups:
                if all(float(np.linalg.norm(d["p"] - per[c]["p"])) <= self.cfg.batch_max_m
                       for c in g):
                    g.append(ch)
                    break
            else:
                groups.append([ch])

        best = None
        for g in groups:
            if len(g) < self.cfg.batch_min_channels:
                continue
            pts = [per[c]["p"] for c in g]
            cand = [np.mean(np.asarray(pts, float), axis=0)] + pts
            bt, bc = None, None
            for c0 in cand:
                tot = float(np.linalg.norm(np.asarray(c0) - np.asarray(self.pos))) / V_ROBOT
                tot += len(g) * (T_MEASURE + T_SWITCH)
                bad = False
                for ch in g:
                    rec = self.recs[ch]
                    S, th = rec.pts[-1], rec.svds[-1]
                    ts, w, _hi = ray_source_samples(S, th, n_t=60)
                    if ts.size == 0:
                        bad = True
                        break
                    E = float(exact_expected_diameter(S, th, np.asarray(c0, float),
                                                      ts, w)[0])
                    if not math.isfinite(E):
                        bad = True
                        break
                    tot += math.pi * max(E / 2.0 + 20.0, 20.0) ** 2 / (2.0 * R_CLEAR) / V_ROBOT
                if bad:
                    continue
                if bt is None or tot < bt:
                    bt, bc = tot, np.asarray(c0, float)
            if bc is None:
                continue
            gain = sum(per[c]["info"]["cost_s"] for c in g) - bt
            if best is None or gain > best[0]:
                best = (gain, bc, g, bt)
        if best is None:
            return 0
        gain, c, group, cost = best
        if gain <= self.cfg.batch_min_gain_s:
            return 0
        trav = float(np.linalg.norm(c - np.asarray(self.pos)))
        if not self.can_afford(trav / V_ROBOT + len(group) * (T_MEASURE + T_SWITCH) + 10.0):
            return 0
        self.stats["n_batch"] = self.stats.get("n_batch", 0) + 1
        self.log(f"定位批次{'（' + reason + '）' if reason else ''}：{len(group)} 个频道只有一条方位 "
                 f"{group} -> 合并测点 ({c[0]:.0f},{c[1]:.0f})，移动 {trav:.0f} m，"
                 f"预计比各测各的省 {gain:.0f} s")
        self.scan_points.append((float(c[0]), float(c[1])))
        n = 0
        for ch in group:
            if self.aborted or not self.can_afford(T_MEASURE + T_SWITCH + 3.0):
                break
            resp = self.measure(float(c[0]), float(c[1]), int(ch))
            n += 1
            if resp.get("measure_result") == "near":
                self.do_clear(float(c[0]), float(c[1]), int(ch))
        self.note_pos()
        if self.clear_targets() and self.can_afford(self.cfg.min_action_budget_s):
            self.phase = "clear"
            self.clear_phase()
            self.phase = "scan"
            self.note_pos()
        return n

    def _initial_locate(self):
        """开场定点：委托给 :meth:`_field_batch_locate`（它自带合并规划）。"""
        if not self.cfg.initial_locate or self.base is None or self.aborted:
            return 0
        return self._field_batch_locate(reason="开场")

    # ---------------- 主循环 ----------------
    def run(self):
        t0 = time.time()
        resp = self.arena.enter()
        if resp.get("accepted") is not True:
            raise ArenaError(f"/enter 未被接受：{resp}")
        self.log(f"进入靶区：可用预算 {self.remaining():.0f} s"
                 f"（{self.arena.budget_kind()}）；策略=覆盖扫圈")
        try:
            # 第 0 轮：原点（已经覆盖了 r<=1000 m 的整个内圈）
            chans0 = self.channels_to_measure()
            self.log(f"第 0 轮扫描（原地）：待测 {len(chans0)} 个频道 {chans0}")
            self.scan_points.append(self.pos)
            self.scan_at(self.pos[0], self.pos[1], chans0)
            self.note_pos()
            cov, mdist = self.coverage_now()
            self.log(f"  初始覆盖率 {cov:.3f}（原点一次检测即覆盖 r<=1000 m 的内圈）")

            # ---- 开场定点（方案 1）：先用决策场把近处那一簇源定位并清掉 ----
            self._initial_locate()
            cov, mdist = self.coverage_now()
            self.log(f"  开场定点结束：覆盖率 {cov:.3f}，"
                     f"已清除 {sum(1 for r in self.recs.values() if r.cleared)} 个源")

            rounds = 1
            level = 0
            laps_at_level = 0
            done = False
            first, _first_idx = self.pick_start_stop()   # 朝"信息最多的方向"出发
            while (not self.aborted and rounds < self.cfg.max_rounds
                   and self.remaining() > self.cfg.time_reserve_s):
                is_first = first is not None
                target_hit = None
                if is_first:
                    c = first
                    first = None
                    info = {"dist": float(np.hypot(float(c[0]) - self.arena.pos[0],
                                                   float(c[1]) - self.arena.pos[1])),
                            "adv_deg": 0.0, "gain": 1.0, "n_new": 0, "cnt": 0}
                else:
                    cov, mdist = self.coverage_now()
                    if mdist <= self.cfg.cover_radius_m:
                        self.log(f"* 覆盖率 100%（最大未覆盖点距最近检测点 {mdist:.0f} m "
                                 f"<= {self.cfg.cover_radius_m:.0f} m）"
                                 f"-> 靶区内不可能存在未清除源，提前收工")
                        break
                    c, info = self.pick_stop(level=level)
                if c is None:
                    # 这一圈走完了（该圈所有站位要么已到过、要么没有新覆盖）
                    if level + 1 < len(self.cfg.sweep_rings):
                        level += 1
                        laps_at_level = 0
                        self.ring_last_a = None      # 换圈后重新确定绕行方向
                        self.ring_dir = -self.ring_dir if self.ring_dir else 1.0
                        self.log(f"主圈走完仍有缺口（覆盖率 {cov:.3f}）"
                                 f"-> 启用补漏圈 level={level}"
                                 f"（r={self.cfg.sweep_rings[level][0]:.0f} m）")
                        continue
                    # 所有圈都走过了：换下一圈（角向错开 lap_offsets），再走一遍
                    if (self.lap + 1) < max(2, len(self.cfg.lap_offsets)):
                        self.lap += 1
                        level = 0
                        laps_at_level = 0
                        self.ring_last_a = None
                        self.log(f"所有环的站位都已到过，但仍有频道从未测到信号 "
                                 f"-> 第 {self.lap + 1} 圈（角向错开 "
                                 f"{self.cfg.lap_offsets[min(self.lap, len(self.cfg.lap_offsets) - 1)]} 格）")
                        continue
                    targets = self.clear_targets()
                    if targets and self.can_afford(self.cfg.min_action_budget_s):
                        self.log(f"扫圈完成但仍剩 {len(targets)} 个已定位未清除的源 -> 清除")
                        self.clear_phase()
                        continue
                    self.log(f"没有可选的停靠点、也没有待清除的源 -> 结束"
                             f"（覆盖率 {cov:.3f}，最大未覆盖 {mdist:.0f} m）")
                    break
                cost = (info["dist"] / V_ROBOT + T_MEASURE + T_SWITCH
                        + self.cfg.min_action_budget_s)
                if not self.can_afford(cost):
                    self.log(f"剩余时间不足以再走一站（还需约 {cost:.0f} s）-> 收工")
                    break
                cov, mdist = self.coverage_now()
                self.log(f"扫圈第 {rounds} 站(lv{level})：选点 ({c[0]:.0f},{c[1]:.0f})｜"
                         f"移动 {info['dist']:.0f} m｜前进 {info['adv_deg']:.0f}°｜"
                         f"本点新覆盖 {info['n_new']}/{info['cnt']} 格（收益 {info['gain']:.2f}）｜"
                         f"当前覆盖率 {cov:.3f}（最大未覆盖 {mdist:.0f} m）")
                # ---- 用"目标位置"顶替环上站位（省一个路径点）----
                if self.cfg.onlap_clear and info.get("gain", 1.0) < 0.5:
                    hit = self._target_near_station(c)
                    if hit is not None and self.station_skippable(c, [hit[1]]):
                        self.scan_points.append((float(c[0]), float(c[1])))
                        self.log(f"  * 站位 ({c[0]:.0f},{c[1]:.0f}) 与频道{hit[0]} 的目标位置只差 "
                                 f"{hit[2]:.0f} m，且顶替后覆盖仍够（最大未覆盖 < "
                                 f"{self.cfg.skip_station_max_uncovered:.0f} m）-> 省掉这一站，"
                                 f"直接去清频道{hit[0]}")
                        self._onlap_handle("locate" if self.recs[int(hit[0])].n_bearings < 2
                                           else "clear", int(hit[0]), hit[1])
                        self.note_pos()
                        rounds += 1
                        continue
                p0 = np.asarray(self.arena.pos, float)
                v = np.asarray(c, float) - p0
                dv = float(np.linalg.norm(v))
                travel_dir = (v / dv) if dv > 1e-9 else None      # 本段计划行进方向
                incoming_dir = self._last_dir                       # 上一段的行进方向
                # 下一段的方向：先"试推"一次 pick_stop（只读），用它来判定"前方该清的点"
                next_dir = None
                try:
                    _saved_last, _saved_dir = self.ring_last_a, self.ring_dir
                    _saved_pts = list(self.scan_points)
                    if not is_first:
                        self.scan_points.append((float(c[0]), float(c[1])))
                    _c2, _ = self.pick_stop(level=0)
                    if _c2 is not None:
                        v2 = np.asarray(_c2, float) - np.asarray(c, float)
                        d2 = float(np.linalg.norm(v2))
                        if d2 > 1e-9:
                            next_dir = v2 / d2
                except Exception:
                    next_dir = None
                finally:
                    self.ring_last_a, self.ring_dir = _saved_last, _saved_dir
                    self.scan_points = _saved_pts
                if not is_first:
                    self.commit_stop(c)
                    self.scan_points.append((float(c[0]), float(c[1])))
                self.visit_stop(float(c[0]), float(c[1]), travel_dir=travel_dir,
                                incoming_dir=incoming_dir, next_dir=next_dir)
                self._last_dir = travel_dir
                # 起始站在访问之后才登记：`pick_stop` 用 `scan_points` 做"已到过"的排除，
                # 若提前登记，第一站的邻域会立刻生效，下一站就选不出来了（零收益）
                if is_first:
                    self.commit_stop(c)
                    self.scan_points.append((float(c[0]), float(c[1])))
                # ---- 按期望场行动：每走几站就把"只有一条方位"的频道合并定一次 ----
                if (self.cfg.batch_locate and not self.aborted
                        and rounds % max(1, self.cfg.batch_every) == 0):
                    self._field_batch_locate(reason=f"第 {rounds} 站后")
                rounds += 1
                laps_at_level += 1
                if laps_at_level > 4 * max(self.ring_n, 8) + 8:
                    break

            # ---- 走完圈之后：把所有已定位的源统一清掉（边绕边清模式下通常已清完）----
            if (not self.cfg.onlap_clear or self.cfg.onlap_after_ring) \
                    and not self.aborted and self.clear_targets() \
                    and self.can_afford(self.cfg.min_action_budget_s):
                self.log(f"扫圈结束（覆盖率 {self.coverage:.3f}）：统一清除 "
                         f"{len(self.clear_targets())} 个已定位的源")
                self.phase = "clear"
                self.clear_phase()
                self.phase = "scan"
                self.note_pos()

            # ---- 完工判据：整圈已走完 + 每个频道都有明确结论 -> 直接收工 ----
            if not self.aborted and self.all_heard():
                self.log(f"整圈已走完，且每个频道都有明确结论"
                         f"（已清除 {sum(1 for r in self.recs.values() if r.cleared)} 个 / "
                         f"其余从未测到信号）-> 靶区内无残留源")
                self.stats["n_scan_rounds"] = rounds
                done = True

            # ---- 额外圈：整圈走完但还有频道从未测到（角向缝隙）时再走 -----------------
            while (not done and not self.aborted and rounds < self.cfg.max_rounds
                   and self.remaining() > self.cfg.time_reserve_s):
                cov, mdist = self.coverage_now()
                if self.lap + 1 >= max(2, len(self.cfg.lap_offsets)):
                    break
                c, info = self.pick_stop(level=0)
                if c is None:
                    self.lap += 1
                    self.level = 0
                    self.ring_last_a = None
                    self.log(f"第 {self.lap} 圈走完仍有频道从未测到 -> "
                             f"第 {self.lap + 1} 圈（角向错开 "
                             f"{self.cfg.lap_offsets[min(self.lap, len(self.cfg.lap_offsets) - 1)]} 格）")
                    continue
                cost = (info["dist"] / V_ROBOT + T_MEASURE + T_SWITCH
                        + self.cfg.min_action_budget_s)
                if not self.can_afford(cost):
                    break
                self.log(f"补测圈第 {rounds} 站：({c[0]:.0f},{c[1]:.0f})｜"
                         f"覆盖率 {cov:.3f}（最大未覆盖 {mdist:.0f} m）")
                self.commit_stop(c)
                self.visit_stop(float(c[0]), float(c[1]))
                rounds += 1
                if self.all_heard() and not self.clear_targets():
                    self.log("补测后每个频道都有明确结论、且没有待清除目标 -> 结束")
                    break
            self.stats["n_scan_rounds"] = rounds

            # ---- 收尾：把"听到了但还没清掉"的少量频道用自适应方式解决 ----
            guards = 0
            while (not self.aborted and rounds < self.cfg.max_rounds
                   and self.remaining() > self.cfg.time_reserve_s and guards < 8):
                guards += 1
                leftover = [ch for ch, rec in self.recs.items()
                            if not rec.cleared and rec.n_bearings >= 1]
                if not leftover:
                    break
                # 只关心"有界区域但还没清"的频道；其余先补一条方位
                todo = [t for t in self.clear_targets()]
                if todo:
                    self.log(f"收尾：清除剩余 {len(todo)} 个已定位目标 "
                             f"{[t[0] for t in todo]}")
                    self.phase = "clear"
                    n = self.clear_phase()
                    self.phase = "scan"
                    self.note_pos()
                    if n == 0:
                        break
                    continue
                plan = self.plan_scan()
                if plan is None or not self.can_afford(plan["cost_s"]):
                    self.log(f"收尾：剩余频道 {leftover} 无法在预算内继续定位 -> 结束")
                    break
                self.log(f"收尾：为剩余频道 {leftover} 补测方位 -> "
                         f"选点 {tuple(round(v) for v in plan['sel']['xy'])}")
                self.execute_scan(plan)
                rounds += 1
            self.stats["n_scan_rounds"] = rounds
        finally:
            try:
                self.arena.exit()
            except ArenaError as e:
                self.log(f"/exit 异常：{e}")
        self.stats["program_runtime_s"] = time.time() - t0
        rep = self.report()
        rep["coverage"] = self.coverage
        rep["max_uncovered_dist_m"] = self.max_uncov_dist
        return rep


class HybridRobot(SweepRobot):
    """混合策略：**先用扫圈把该听的都听到，再交给"期望场贪心"去清除**。

    动机（离线实测）：
    * 纯扫圈的**发现**效率明显更好：同样两局在线真源，虚拟时间 3.7–4.0k vs 4.0–4.4k，
      检测次数 117–145 vs 143–198，行程少 3–5 km，而且不会乱蹭、有完备性判据；
    * 但纯扫圈的**清除**偏弱（外圈环带场景 0.972），因为它把清除也绑在"绕圈"结构上。
    * 所以让两者各干自己最擅长的：扫圈负责"把 20 个频道都听到一遍"（发现），
      之后切到自适应循环负责"把听到的源清干净"（决策场选点 + 覆盖式试探 + 顺路补测）。
    """

    def run(self):
        t0 = time.time()
        resp = self.arena.enter()
        if resp.get("accepted") is not True:
            raise ArenaError(f"/enter 未被接受：{resp}")
        self.log(f"进入靶区：可用预算 {self.remaining():.0f} s"
                 f"（{self.arena.budget_kind()}）；策略=扫圈发现 + 自适应清除")
        try:
            chans0 = self.channels_to_measure()
            self.log(f"第 0 轮扫描（原地）：待测 {len(chans0)} 个频道 {chans0}")
            self.scan_points.append(self.pos)
            self.scan_at(self.pos[0], self.pos[1], chans0)
            self.note_pos()

            # ---- 阶段 1：绕一圈，把该听的频道都听一遍（不清除） ----
            self.phase = "scan"
            rounds = 1
            while (not self.aborted and rounds < self.cfg.max_rounds
                   and self.remaining() > self.cfg.time_reserve_s):
                cov, mdist = self.coverage_now()
                c, info = self.pick_stop(level=0)
                if c is None:
                    break
                cost = (info["dist"] / V_ROBOT + T_MEASURE + T_SWITCH
                        + self.cfg.min_action_budget_s)
                if not self.can_afford(cost):
                    break
                self.log(f"扫圈第 {rounds} 站：({c[0]:.0f},{c[1]:.0f})｜"
                         f"移动 {info['dist']:.0f} m｜收益 {info['gain']:.2f}｜"
                         f"覆盖率 {cov:.3f}（最大未覆盖 {mdist:.0f} m）")
                self.commit_stop(c)
                self.scan_points.append((float(c[0]), float(c[1])))
                self.visit_stop(float(c[0]), float(c[1]))
                rounds += 1
                if self.all_heard():
                    self.log("整圈走完，每个频道都有明确结论 -> 结束扫描阶段，"
                             "转交自适应清除")
                    break
            self.stats["n_scan_rounds"] = rounds

            # ---- 阶段 2：切回自适应主循环（决策场选点 + 清理 + 顺路补测） ----
            self.phase = "adaptive"
            stall = 0
            while (not self.aborted and rounds < self.cfg.max_rounds
                   and self.remaining() > self.cfg.time_reserve_s):
                did = 0
                if self.clear_targets() and (rounds >= self.cfg.min_scan_rounds_before_clear
                                             or not self.plan_scan()):
                    did += self.clear_phase()
                if self.aborted or self.remaining() <= self.cfg.time_reserve_s:
                    break
                plan = self.plan_scan()
                if plan is not None and self.can_afford(plan["cost_s"]) \
                        and (did == 0 or not self.clear_targets()):
                    did += self.execute_scan(plan)
                    rounds += 1
                if did == 0:
                    stall += 1
                    if stall >= 2:
                        self.log("自适应阶段：没有可清理的频道、也没有值得检测的频道 "
                                 "-> 提前结束")
                        break
                else:
                    stall = 0
            self.stats["n_scan_rounds"] = rounds
        finally:
            try:
                self.arena.exit()
            except ArenaError as e:
                self.log(f"/exit 异常：{e}")
        self.stats["program_runtime_s"] = time.time() - t0
        rep = self.report()
        rep["coverage"] = self.coverage
        rep["max_uncovered_dist_m"] = self.max_uncov_dist
        return rep


def selfcheck(verbose=True):
    out, ok_all = [], True

    def rec(name, ok, detail=""):
        nonlocal ok_all
        ok_all = ok_all and bool(ok)
        out.append({"check": name, "ok": bool(ok), "detail": detail})
        if verbose:
            print(f"[{'OK ' if ok else 'FAIL'}] {name}  {detail}")

    cand = lattice_candidates()
    mdist, unc, cov = coverage_report(cand, r_inner=R_RECV_MIN)
    rec("C1 一圈格点即可覆盖环带 r∈[1000,1800]（最大未覆盖距离 <= 1000 m）",
        mdist <= R_RECV_MIN,
        f"{len(cand)} 个候选点；环带内最大未覆盖距离 {mdist:.0f} m；"
        f"未覆盖面积 {unc*100:.2f}%")

    mdist1, unc1, cov1 = coverage_report([(0.0, 0.0)] + cand, r_inner=0.0)
    rec("C2 原点 + 一圈覆盖整个靶区（这才是实际航线的完备性口径）",
        mdist1 <= R_RECV_MIN,
        f"最大未覆盖 {mdist1:.0f} m；覆盖率 {cov1*100:.2f}%")

    from p3_arena import MockArena
    a = MockArena(seed=20260913)
    rb = SweepRobot(a, SweepConfig(), base=None, log=None)
    sel, info = rb.pick_stop()
    rec("C3 第一站只从还没覆盖的格点里选，且不选已停靠点邻域",
        sel is not None and info["gain"] >= rb.cfg.min_gain,
        f"第一个停靠点 ({sel[0]:.0f},{sel[1]:.0f})，距原点 {info['dist']:.0f} m，"
        f"边际覆盖 {info['gain']:.2f}（新覆盖 {info['n_new']}/{info['cnt']} 格）")

    return {"ok": ok_all, "checks": out}


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        res = selfcheck()
        raise SystemExit(0 if res["ok"] else 1)
    if "--coverage" in sys.argv:
        for rings in (DEFAULT_RINGS,):
            cand = lattice_candidates(rings)
            mdist, unc, cov = coverage_report(cand)
            print(f"候选点 {len(cand)} 个：最大未覆盖 {mdist:.0f} m，未覆盖 {unc*100:.2f}%")
        print("\n只用原点一个点：", coverage_report([(0.0, 0.0)])[:2])
        print("原点 + 一圈 r=1500 (8 点)：",
              coverage_report([(0.0, 0.0)] + [(1500 * math.cos(2 * math.pi * i / 8),
                                              1500 * math.sin(2 * math.pi * i / 8))
                                              for i in range(8)])[:2])
        print("原点 + 一圈 r=1800 (12 点)：",
              coverage_report([(0.0, 0.0)] + [(1800 * math.cos(2 * math.pi * i / 12),
                                               1800 * math.sin(2 * math.pi * i / 12))
                                              for i in range(12)])[:2])
