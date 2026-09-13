"""B 题问题 3：机器狗"基于期望的行动"在线搜索—定位—清除策略。

策略流程（与设计说明一一对应）
------------------------------
1. **第一轮扫描**：机器狗从原点出发，测向机初始频道 1，按频道 1..20 依次 ``/measure``，
   得到若干条"检测点 + 示向度"（部分频道无信号属正常）。
2. **期望场选点**：对每个"只测到一次方位"的频道，用第二问的网格模拟结果
   （``out/p3_family`` 或 ``out/p2_grid``）做旋转 + 平移 + 双线性插值，把
   :math:`\\mathbb E[D]` 叠加到全局网格上；没有数据/超阈值的格子取最大值 1500 m；
   归一化后再叠加一层**与探测器距离线性增长**的代价（系数 λ 可调），取 ``argmin``
   作为下一个检测点，随后开始新一轮 20 频道扫描。
3. **清理**：某些频道已经测到 ≥2 条方位 —— 用问题 1 的交会算法算出定位区域
   （最小包围圆 = 中心 + 半径 r*）。对所有可清理的频道按最近邻顺序规划航路，
   依次前往；到达区域后继续检测把区域压小，直到进入清除范围，再用
   **覆盖式试探**（六边形格点，间距 ≤ 20√3 m，保证圆域内任一点到某个试探点 ≤ 20 m）
   逐个 ``/clear``，必然有一点成功。
4. **清除后继续扫描**；已经清除的频道、已经定位够的频道、以及"在同一个有效接收半径内
   重复测过的频道"都会被跳过，从而节省时间。
5. 反复执行 2–4，直到时间预算耗尽或没有新的可用信息。

关键设计
--------
* **为什么"未覆盖 = 1500 m"是对的**：E[D] 越小定位越好；把没有信息的格子记成最差，
  只有在附近确实没有更好格子时才会选它 —— 这天然形成了"顺路探索"的行为。
* **为什么不能沿示向度方向逼近**：那会退化成问题 1 的"无界区域"几何。所以清理时的
  侧移精定位点取在**与上一条视线近似正交**的方向上。
* **清理阶段的覆盖式试探是"保证成功"的**：真源必落在 ±1° 锥的交集（定位区域）内，
  区域内任意一点到某个试探点的距离 ≤ 20 m = 清除半径。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field as dc_field

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from p1_intersection import analyse  # noqa: E402
from p3_arena import (  # noqa: E402
    ArenaError, BEARING_ERR, CHANNELS, MockArena, NEAR_R, R_ARENA, R_CLEAR,
    T_CLEAR_FAIL, T_CLEAR_OK, T_MEASURE, T_SWITCH, V_ROBOT,
)
from p3_expect_field import (  # noqa: E402
    DEFAULT_BASE_CSV, DEFAULT_FAMILY_DIR, BaseMap, BaseMapFamily, ExpectField,
    FieldConfig, best_refine_point,
)


# --------------------------------------------------------------------------
# 覆盖式试探的三种结局
# --------------------------------------------------------------------------
# 必须区分"预算不够、一个试探点都没来得及发"与"试探了但没打中"：
# 前者不是策略失败（不该累加 clear_fail、不该写进论文的失败归因），
# 后者才是真正的"区域内没找到目标"。
SWEEP_OK = "success"        # 某一点 /clear 成功
SWEEP_MISS = "miss"         # 试探了全部候选点（或中途超时）都没打中
SWEEP_BUDGET = "no_budget"  # 剩余预算不足，**一个 /clear 都没发出**，主动放弃


# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------
@dataclass
class P3Config:
    # ---- 期望场（全局网格 + 距离惩罚）----
    grid_step: float = 100.0        # 全局网格步长（m）
    e_max: float = 1500.0           # 未覆盖网格的默认最大值（m）
    dist_weight: float = 1.5        # 距离项系数 λ（离线演练调参得到，见 review/P3-design.md）
    visited_radius: float = 250.0   # 已扫描点邻域排除半径（m）
    min_move: float = 60.0          # 距当前位置过近的格子排除（m）
    field_terms: str = "pending"    # pending：只叠加"还缺方位"的频道
    field_discovery: bool = False   # 始终叠加"探索项"（把扫描点推向能发现新源的地方）
    auto_discovery_when_empty: bool = True  # 场上一条可用方位都没有时自动启用探索项

    # ---- 扫描 ----
    channels: tuple = CHANNELS
    scan_1bearing_first: bool = True
    repeat_gap_m: float = 60.0          # 同一频道在附近重复测量的最小间隔（m）
    nosignal_gap_m: float = 1000.0      # "无信号"频道要换足够远的地方重测
                                        # （= 有效接收半径下界：在 1000 m 外重测才有
                                        #   真正的新信息；实测 450→1000 使检测次数
                                        #   289→186、平均定位清除时间 398→315 s，
                                        #   清除率 0.992→0.995，见 review/P3-design.md §5.1）（m）
    enroute_scan: bool = True            # 清理途中顺路补测
    enroute_scan_max: int = 2
    second_bearing_refine: bool = False  # 新发现频道立刻补第二条方位（实测收益不稳，默认关）
    second_bearing_max: int = 2          # 每个停点最多补几条
    second_bearing_budget_s: float = 320.0  # 剩余时间低于它就不再补测
    max_rounds: int = 30
    tour: str = "nn2opt"                 # 清理航路：nn | nn2opt
    dynamic_replan: bool = True          # 清理阶段每步重规划（滚动时域）；False=阶段内固定顺序
    clear_policy: str = "tour"           # tour（NN+2-opt 全局结构）| rollout（一步前瞻+SPT）
    clear_budget_truncation: bool = False  # 是否按剩余预算裁剪航路（实测关掉更好）
    optimistic_probe_steps: int = 3      # 打开裁剪时的试探点数封顶
    min_scan_rounds_before_clear: int = 1  # 先扫描几轮再开始清理

    # ---- 定位与清除 ----
    clear_min_bearings: int = 2
    clear_max_radius_m: float = 600.0   # 定位区域半径超过它就先不清理
                                        # （400 → 600：扫圈在 r≈1100 m 处交会、区域半径
                                        #   常在 400–650 m，400 会让这些源被"跳过"；
                                        #   600 实测把扫圈的清除率从 0.958 提到 0.989–1.000）
    arrive_radius_m: float = 30.0
    direct_probe_radius_m: float = 60.0  # r* 不超过它就无需侧移精定位，直接试探
    probe_spacing_m: float = 34.0        # ≤ 20√3 ≈ 34.6 m 才能保证覆盖
    probe_max_points: int = 60           # 候选点数上限（仅"可覆盖"档位，见下）
    probe_unlimited: bool = True         # True=不按点数截断（保证覆盖；截断会破坏 20 m 保证）
    probe_max_radius_m: float = 200.0
    refine_leg_m: float = 320.0
    refine_travel_cap_m: float = 700.0
    refine_mode: str = "perp"            # perp（正交侧移）| exact（精确期望最优）
    max_approach_steps: int = 3

    # ---- 时间预算 ----
    time_reserve_s: float = 3.0
    min_action_budget_s: float = 10.0
    min_scan_channels: int = 2       # 单轮扫描至少要能测这么多频道才值得跑一趟

    # ---- 预算感知的扫描闸门（"剩余时间不够就不要再扫"）----
    # 诊断依据：30 局里扫描阶段吃掉约 1016 s / 1200 s，而末尾有 23% 的未清除源
    # **已经定位好却没时间走过去**。所以关键不是"怎么选扫描点"，而是"还要不要扫"。
    scan_budget_gate: bool = False       # 开：本轮扫描后必须还够清最近的一个目标，否则不扫
    scan_gate_margin: float = 0.0        # 额外预留秒数（越大越倾向"别扫了，去清除"）
    scan_gate_factor: float = 1.0        # 对"清最近目标"耗时估计的放大系数
    scan_only_toward_targets: bool = False  # 扫描点若背着已知目标走，则该轮不扫
    # 扫描时间的硬性上限（占总预算比例）。诊断显示扫描占掉约 1016 s / 1200 s，
    # 而 29/49 个"已定位未清除"的目标在变成可清目标时**剩余时间完全够用**却没去清。
    scan_budget_frac: float = 1.0        # 1.0 = 不限制；0.5 = 扫描累计不超过一半预算

    # ---- 清理航路：可达近点子集（"优先清路程近的点"）----
    clear_shortlist: bool = False        # 开：只保留"预算内可达"的近点子集，再排序
    clear_shortlist_reserve_s: float = 0.0  # 为后续扫描预留的秒数


# --------------------------------------------------------------------------
# 频道台账
# --------------------------------------------------------------------------
@dataclass
class ChannelRec:
    channel: int
    pts: list = dc_field(default_factory=list)     # 测到方位的检测点
    svds: list = dc_field(default_factory=list)    # 对应的示向度
    meas_pts: list = dc_field(default_factory=list)  # 所有检测过的位置（含无信号）
    meas_log: list = dc_field(default_factory=list)  # (x, y, virtual_time, result)
    meas_stations: list = dc_field(default_factory=list)  # 测过该频道的**站位编号**
                                                     # （问题 4 的覆盖记账用：只有"这一站
                                                     #   本来能听到它"才抵扣覆盖）
    cleared: bool = False
    cleared_at: float | None = None
    near_hits: int = 0
    no_signal: int = 0
    clear_fail: int = 0                # 自最近一次"新增方位"以来清理失败的次数
    last_bounded: tuple | None = None  # (center, radius, n_bearings) 最近一次有界区域
    tried_probes: list = dc_field(default_factory=list)
    history: list = dc_field(default_factory=list)

    @property
    def n_bearings(self) -> int:
        return len(self.pts)


# --------------------------------------------------------------------------
# 机器狗
# --------------------------------------------------------------------------
def load_base(family_dir=DEFAULT_FAMILY_DIR, base_csv=DEFAULT_BASE_CSV):
    """优先用"基准图族"（按先验外径 t_hi 分族，变换才严格成立），否则退回单张基准图。"""
    if family_dir and os.path.isdir(family_dir):
        fam = BaseMapFamily.load_dir(family_dir)
        if fam is not None:
            return fam
    if os.path.exists(base_csv):
        return BaseMap.load_csv(base_csv)
    return None


def _dist_point_segment(p, a, b):
    ab = b - a
    L2 = float(ab @ ab)
    if L2 < 1e-12:
        return float(np.linalg.norm(p - a))
    t = float(np.clip((p - a) @ ab / L2, 0.0, 1.0))
    return float(np.linalg.norm(p - (a + t * ab)))


def _point_in_polygon(p, P):
    """射线法（P 为凸多边形顶点，逆时针或顺时针均可）。"""
    n = len(P)
    inside = False
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x > p[0]:
                inside = not inside
    return inside


def _dist_point_polygon(p, P):
    p = np.asarray(p, float)
    P = np.asarray(P, float)
    if _point_in_polygon(p, P):
        return 0.0
    n = len(P)
    return min(_dist_point_segment(p, P[i], P[(i + 1) % n]) for i in range(n))


class P3Robot:
    def __init__(self, arena, cfg: P3Config | None = None, base=None, log=None,
                 log_prefix=""):
        self.arena = arena
        self.cfg = cfg or P3Config()
        self.base = base if base is not None else load_base()
        self._log_fn = log
        self.log_prefix = log_prefix
        self.recs = {int(ch): ChannelRec(int(ch)) for ch in self.cfg.channels}
        self.scan_points: list[tuple] = []
        self.meas_pts: list[tuple] = []      # **真实做过的检测**位置（覆盖度评估口径：
                                             # "到过的点"≠"测过的点"，覆盖度只能按后者算）
        self.events: list[dict] = []
        self.aborted = False
        # 覆盖式试探因"预算不足"放弃时置位：让 clear_phase 立刻收敛，
        # 不要对同一个目标反复重规划（实测会把重规划次数抬高一到两个数量级）。
        self.abort_clear_phase = False
        self.stats = {"n_measure": 0, "n_clear": 0, "n_clear_fail": 0,
                      "n_scan_rounds": 0, "n_bearings": 0, "n_rejected": 0,
                      "n_refine": 0, "n_second_bearing": 0, "n_replans": 0,
                      "n_midphase_targets": 0, "n_sweep_aborted": 0,
                      "n_sweep_miss": 0, "n_probe_issued": 0,
                      "n_scan_gated": 0, "n_shortlist_kept": 0, "n_shortlist_in": 0,
                      "t_scan_s": 0.0, "t_clear_s": 0.0, "t_clear_ends_s": 0.0,
                      "vtime_at_last_clear": 0.0}

    # ---------------- 基础设施 ----------------
    def log(self, msg):
        self.events.append({"t": float(self.arena.virtual_time_s), "msg": msg})
        if self._log_fn:
            # 日志里避免使用 GBK 控制台无法编码的符号（⇒ ★ √ × 等），
            # 万一还有，退化为替换字符也不要让整局崩掉。
            try:
                self._log_fn(f"{self.log_prefix}{msg}")
            except UnicodeEncodeError:
                self._log_fn(f"{self.log_prefix}{msg}".encode(
                    "gbk", "replace").decode("gbk"))

    def remaining(self):
        return float(self.arena.remaining_budget_s())

    def can_afford(self, seconds):
        return self.remaining() > float(seconds) + self.cfg.time_reserve_s

    @property
    def pos(self):
        return tuple(self.arena.pos)

    # ---------------- 检测 / 清除 ----------------
    def measure(self, x, y, ch):
        resp = self.arena.measure(x, y, ch)
        self.stats["n_measure"] += 1
        if resp.get("accepted") is not True:
            self.stats["n_rejected"] += 1
            self.aborted = True
            self.log(f"  ! /measure 频道{ch} 未执行（{resp.get('reason', '?')}）")
            return resp
        res = resp.get("measure_result")
        rec = self.recs[int(ch)]
        rec.meas_pts.append((float(x), float(y)))
        rec.meas_log.append((float(x), float(y), float(self.arena.virtual_time_s), res))
        if res == "direction":
            self.add_bearing(int(ch), x, y, float(resp["svd_deg"]))
        elif res == "near":
            rec.near_hits += 1
        else:
            rec.no_signal += 1
        return resp

    def add_bearing(self, ch, x, y, svd):
        rec = self.recs[int(ch)]
        rec.pts.append((float(x), float(y)))
        rec.svds.append(float(svd))
        rec.clear_fail = 0
        rec.tried_probes = []
        self.stats["n_bearings"] += 1
        reg = self.region(rec)
        if reg.get("status") == "bounded":
            rec.last_bounded = (tuple(reg["min_enclosing_center"]),
                                float(reg["min_enclosing_radius_m"]), len(rec.pts))
        rec.history.append({"n": len(rec.pts), "x": float(x), "y": float(y),
                            "svd": float(svd), "status": reg.get("status"),
                            "r_star_m": (rec.last_bounded[1] if rec.last_bounded else None)})
        return reg

    def do_clear(self, x, y, ch):
        resp = self.arena.clear(x, y, ch)
        self.stats["n_probe_issued"] = self.stats.get("n_probe_issued", 0) + 1
        if resp.get("accepted") is not True:
            self.stats["n_rejected"] += 1
            self.aborted = True
            self.log(f"  ! /clear 频道{ch} 未执行（{resp.get('reason', '?')}）")
            return False
        if resp.get("clear_result") == "success":
            rec = self.recs[int(ch)]
            rec.cleared = True
            rec.cleared_at = float(self.arena.virtual_time_s)
            self.stats["n_clear"] += 1
            self.stats["vtime_at_last_clear"] = float(self.arena.virtual_time_s)
            self.log(f"  [OK] 频道{ch} 已清除（t={self.arena.virtual_time_s:.1f}s）")
            return True
        self.stats["n_clear_fail"] += 1
        return False

    # ---------------- 定位区域 ----------------
    def region(self, rec: ChannelRec):
        if not rec.pts:
            return {"status": "none", "n_bearings": 0}
        return analyse(rec.pts, rec.svds, BEARING_ERR)

    def bounded_region(self, rec: ChannelRec):
        """当前（或最近一次）有界区域；返回 ``{'center','radius','poly','status'}``。"""
        if len(rec.pts) >= 2:
            reg = self.region(rec)
            if reg.get("status") == "bounded":
                return {"center": tuple(reg["min_enclosing_center"]),
                        "radius": float(reg["min_enclosing_radius_m"]),
                        "poly": [tuple(v) for v in reg.get("vertices", [])],
                        "status": "bounded", "n_bearings": len(rec.pts)}
        if rec.last_bounded is not None:
            c, r, n = rec.last_bounded
            return {"center": tuple(c), "radius": float(r), "poly": None,
                    "status": "fallback", "n_bearings": n}
        return None

    # ---------------- 扫描 ----------------
    def needed_channels(self):
        """还需要（且值得）拿到新方位的频道：已清除、已够定位两次的跳过。"""
        need, done = [], []
        for ch in self.cfg.channels:
            rec = self.recs[int(ch)]
            if rec.cleared or rec.n_bearings >= self.cfg.clear_min_bearings:
                continue
            (done if rec.pts else need).append(int(ch))
        order = (done + need) if self.cfg.scan_1bearing_first else sorted(done + need)
        return order

    def channels_to_measure(self, limit=None, pos=None, subset=None, apply_gap=True):
        """在 ``pos`` 处值得检测的频道。

        **跳过规则**（"节省时间"的关键）：已清除 / 已定位两次的不测；
        对"无信号"频道，新检测点必须距它所有历史检测点 ≥ ``nosignal_gap_m``
        （有效接收半径至少 1000 m，在同一个圈里重复扫几乎拿不到新信息）；
        对已有一条方位的频道，新检测点距历史点 ≥ ``repeat_gap_m``（太小交会角没意义）。
        """
        p = np.asarray(pos if pos is not None else self.arena.pos, float)
        out = []
        for ch in (subset if subset is not None else self.needed_channels()):
            rec = self.recs[int(ch)]
            if apply_gap and rec.meas_pts:
                gap = self.cfg.repeat_gap_m if rec.pts else self.cfg.nosignal_gap_m
                d = min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in rec.meas_pts)
                if d < gap:
                    continue
            out.append(int(ch))
        return out[:limit] if limit else out

    def build_field(self, grid_step=None, dist_weight=None):
        cfg = FieldConfig(grid_step=grid_step or self.cfg.grid_step,
                          e_max=self.cfg.e_max,
                          dist_weight=(self.cfg.dist_weight if dist_weight is None
                                       else dist_weight),
                          visited_radius=self.cfg.visited_radius,
                          min_move=self.cfg.min_move)
        f = ExpectField(self.base, cfg)
        if self.base is None:
            return f, 0
        n = 0
        for ch, rec in self.recs.items():
            if rec.cleared:
                continue
            if self.cfg.field_terms == "pending" and rec.n_bearings >= self.cfg.clear_min_bearings:
                continue
            if rec.n_bearings == 0:
                continue
            for ((x, y), th) in zip(rec.pts, rec.svds):
                f.add_bearing((x, y), th, tag=ch)
                n += 1
        if n == 0:
            # 一条"缺第二方位"的频道都没有（例如后半程只剩没听到过的频道）：
            # 自动退化为**探索项**，否则场上没有任何信息、选点无从谈起。
            for ch, rec in self.recs.items():
                if rec.cleared or rec.n_bearings > 0 or not rec.meas_pts:
                    continue
                if not self.cfg.field_discovery and not self.cfg.auto_discovery_when_empty:
                    continue
                f.add_raw(f.discovery_term(rec.meas_pts, self.cfg.nosignal_gap_m),
                          tag=("disc", ch))
                n += 1
        return f, n

    def choose_scan_point(self, dist_weight=None, max_dist=None):
        f, n = self.build_field(dist_weight=dist_weight)
        visited = list(self.scan_points)
        sel = f.argmin(self.pos, visited=visited, max_dist=max_dist)
        if sel is None:
            sel = f.fallback_point(self.pos, visited=visited, max_dist=max_dist)
        sel["n_bearing_terms"] = n
        return sel, f

    def plan_scan(self, dist_weight=None):
        """选下一个检测点，并确定该点上值得测哪些频道。

        顺序很重要：**先**用期望场选点，**再**判断该点上哪些频道还没被"测透"，
        否则会出现"因为要换地方才有信息、但没地方可去"的死锁。
        """
        base = self.needed_channels()
        if not base:
            return None
        # 时间不够时把可选点限制在"还能走到"的范围内（给检测与安全余量留出空间）
        slack = 2.0 * (T_MEASURE + T_SWITCH) + 4.0
        dmax = max(0.0, (self.remaining() - self.cfg.time_reserve_s - slack) * V_ROBOT)
        sel, f = self.choose_scan_point(dist_weight=dist_weight, max_dist=dmax)
        chans = self.channels_to_measure(pos=sel["xy"], subset=base)
        if not chans:
            sel2 = f.fallback_point(self.pos, visited=self.scan_points)
            chans2 = self.channels_to_measure(pos=sel2["xy"], subset=base)
            if chans2:
                sel, chans = sel2, chans2
        if not chans:                     # 兜底：宁可多测几次也不原地空转
            chans = base[:3]
        # 时间不够时自动缩减本轮的频道数（至少测 min_scan_channels 个），把边角时间也用上
        travel = math.dist(self.pos, sel["xy"]) / V_ROBOT
        avail = self.remaining() - self.cfg.time_reserve_s - travel - 4.0
        kmax = max(1, int(avail // (T_MEASURE + T_SWITCH)))
        if len(chans) > kmax:
            if kmax < self.cfg.min_scan_channels:
                return None        # 只剩时间测一两个频道：不值得为它专门跑一趟
            self.log(f"  时间只剩 {self.remaining():.0f} s -> 本轮只测 {kmax}/{len(chans)} 个频道")
            chans = chans[:kmax]
        cost = travel + len(chans) * (T_MEASURE + T_SWITCH) + 2.0
        plan = {"chans": chans, "sel": sel, "field": f, "cost_s": cost}
        if self.cfg.scan_budget_gate and not self._scan_worth_it(plan):
            return None
        return plan

    # ---------------- 预算感知的扫描闸门 ----------------
    def nearest_clear_cost_after(self, at_xy):
        """估计"到达 ``at_xy`` 之后，再清掉最近一个已知目标"所需秒数；没有已知目标则 None。"""
        cand = self.clear_targets()
        if not cand:
            return None
        nxt = min(cand, key=lambda t: math.dist(at_xy, t[2]["center"]))
        return self.estimate_clear_cost(nxt[2], from_pos=at_xy,
                                        probe_cap=self.cfg.optimistic_probe_steps)

    def _scan_budget_left(self):
        """允许继续扫描的剩余秒数（= frac × 总预算 − 已花在扫描上的时间）。"""
        if self.cfg.scan_budget_frac >= 1.0:
            return float("inf")
        return self.cfg.scan_budget_frac * float(self.arena.budget) \
            - self.stats.get("t_scan_s", 0.0)

    def _scan_worth_it(self, plan):
        """本轮扫描值不值得做：**扫完还必须够清最近的一个已知目标**，否则不扫。

        动机（诊断数据）：30 局里扫描阶段平均吃掉约 1016 s / 1200 s，末尾有 23% 的
        未清除源**已经定位好却走不到**。也就是说"再多发现一个源"的边际价值，在
        剩余时间已经不足以走过去清掉它时等于 0 —— 这种扫描纯属消耗预算。

        注意这里只做"取舍"不做"折中"：要么整轮扫，要么整轮不扫；
        因为扫描点本身的移动无法中途变成对目标的逼近（两者方向不同）。
        """
        rem = self.remaining()
        left = self._scan_budget_left()
        if plan["cost_s"] > left:
            self.stats["n_scan_gated"] = self.stats.get("n_scan_gated", 0) + 1
            self.log(f"  ⏹ 放弃本轮扫描：扫描时间额度已用尽（本轮需 {plan['cost_s']:.0f} s，"
                     f"额度剩 {left:.0f} s = {self.cfg.scan_budget_frac:.2f}×总预算）"
                     f"-> 预算留给已定位目标")
            return False
        cand = self.clear_targets()
        need = None
        if cand:
            nxt = min(cand, key=lambda t: math.dist(plan["sel"]["xy"], t[2]["center"]))
            need = self.estimate_clear_cost(nxt[2], from_pos=plan["sel"]["xy"],
                                            probe_cap=self.cfg.optimistic_probe_steps)
            # 可选：扫描点不能"背着"已知目标走（否则这轮的移动无法回收为进度）
            if self.cfg.scan_only_toward_targets:
                u = np.asarray(plan["sel"]["xy"], float) - np.asarray(self.pos, float)
                w = np.asarray(nxt[2]["center"], float) - np.asarray(self.pos, float)
                nu, nw = float(np.hypot(*u)), float(np.hypot(*w))
                if nu > 1e-9 and nw > 1e-9 and float(u @ w) / (nu * nw) < 0.0:
                    self.stats["n_scan_gated"] = self.stats.get("n_scan_gated", 0) + 1
                    self.log(f"  ⏹ 放弃本轮扫描：扫描点 ({plan['sel']['xy'][0]:.0f},"
                             f"{plan['sel']['xy'][1]:.0f}) 与已知目标方向相反 -> 预算留给清除")
                    return False
        if need is None:
            return True                      # 手上没有可清目标：扫描是唯一的进展方式
        required = (plan["cost_s"] + self.cfg.scan_gate_margin
                    + self.cfg.scan_gate_factor * need)
        if rem >= required:
            return True
        self.stats["n_scan_gated"] = self.stats.get("n_scan_gated", 0) + 1
        self.log(f"  ⏹ 放弃本轮扫描：剩余 {rem:.0f} s < 本轮扫描 {plan['cost_s']:.0f} s"
                 f" + 清最近目标 {need:.0f} s（阈值 {required:.0f} s）"
                 f"-> 预算留给已定位目标")
        return False

    def execute_scan(self, plan):
        sel, chans = plan["sel"], plan["chans"]
        x, y = sel["xy"]
        if sel["kind"] == "explore":
            self.log(f"扫描轮：期望场无可用方位（{sel.get('n_bearing_terms', 0)} 项）"
                     f"-> 探索点 ({x:.0f},{y:.0f})，距 {sel['dist_m']:.0f} m")
        else:
            self.log(f"扫描轮：选点 ({x:.0f},{y:.0f})｜E={sel['E_mean_m']:.1f} m  "
                     f"E_norm={sel['E_norm']:.3f}  距离惩罚={sel['dist_penalty']:.3f}  "
                     f"score={sel['score']:.4f}  移动 {sel['dist_m']:.0f} m｜"
                     f"待测 {len(chans)} 个频道 {chans}")
        self.scan_points.append((float(x), float(y)))
        n = self.scan_at(x, y, chans)
        self.stats["n_scan_rounds"] += 1
        return n

    def scan_round(self, dist_weight=None):
        plan = self.plan_scan(dist_weight=dist_weight)
        if plan is None:
            return 0
        if not self.can_afford(plan["cost_s"]):
            return 0
        return self.execute_scan(plan)

    def scan_at(self, x, y, chans):
        """在 (x, y) 依次检测这些频道（第一次调用会带来移动耗时）。"""
        n = 0
        for i, ch in enumerate(chans):
            if self.aborted or not self.can_afford(T_MEASURE + T_SWITCH + 3.0):
                break
            resp = self.measure(x, y, ch)
            n += 1
            if resp.get("measure_result") == "near":
                # 已在 5 m 内：直接清除
                self.do_clear(x, y, ch)
        return n

    # ---------------- 清理 ----------------
    def clear_targets(self):
        out = []
        for ch, rec in self.recs.items():
            if rec.cleared or rec.n_bearings < self.cfg.clear_min_bearings:
                continue
            if rec.clear_fail > 0:
                continue                       # 上次清理失败，等下一次新方位再试
            br = self.bounded_region(rec)
            if br is None or br["radius"] > self.cfg.clear_max_radius_m:
                continue
            out.append((ch, rec, br))
        out.sort(key=lambda t: math.dist(self.pos, t[2]["center"]))
        return out

    # ---------------- 清理：滚动时域动态规划 ----------------
    def _probe_count(self, br):
        """该定位区域需要多少个覆盖式试探点（带缓存：区域不变就不重算）。

        这里**故意**对点数封顶：它只用于"值不值得跑一趟"的代价预估，
        真实覆盖由 :meth:`probe_points` 保证。不封顶会让大 r* 上的枚举变得很贵
        （r*=200 m 时 151 个点 × 每步重规划），实测把程序运行时间抬高两个数量级。
        """
        key = (round(float(br["center"][0]), 1), round(float(br["center"][1]), 1),
               round(float(br["radius"]), 1))
        cache = getattr(self, "_probe_cache", None)
        if cache is None:
            cache = self._probe_cache = {}
        if key not in cache:
            r = min(float(br["radius"]), self.cfg.probe_max_radius_m)
            n = len(self.probe_points(np.asarray(br["center"], float), r,
                                      poly=br.get("poly")))
            cache[key] = min(int(n), int(self.cfg.probe_max_points))
        return cache[key]

    def estimate_clear_cost(self, br, from_pos=None, n_probe=None, probe_cap=None):
        """估计"从 ``from_pos`` 出发清掉某个目标"的耗时（秒）。

        组成：走到区域中心 + 一次逼近检测 + 覆盖式试探（试探点数 × 平均步长/速度 + 3 s/次）
        + 成功清除 5 s。

        ``probe_cap`` 用于**乐观估计**：实际执行时试探是逐点进行的、随时可以中止
        （多数目标前几个试探点就成功），所以判断"值不值得跑一趟"时把试探数封顶，
        否则会过于保守、把还有 400 s 的尾巴白白浪费掉。
        """
        p = np.asarray(from_pos if from_pos is not None else self.pos, float)
        c = np.asarray(br["center"], float)
        if n_probe is None:
            n_probe = self._probe_count(br)
        if probe_cap is not None:
            n_probe = min(int(n_probe), int(probe_cap))
        t_probe = n_probe * (self.cfg.probe_spacing_m / V_ROBOT + T_CLEAR_FAIL)
        return (math.dist(p, c) / V_ROBOT + T_MEASURE + T_SWITCH
                + t_probe + T_CLEAR_OK)

    def budget_feasible_shortlist(self, targets, start=None, budget=None):
        """从 ``targets`` 里挑出"剩余预算内走得完"的**近点子集**（贪心插入）。

        对"近点优先"的回答：滚动时域下每步只执行第一个目标，所以**只保留一个近点**
        在语义上已经等价于"优先清最近的点"；本函数真正的作用是判断
        "这一轮清理是否还排得下任何一个目标"，以及给排序一个**可达性**约束。

        排序键是"距当前位置"（近点优先），逐个累计
        ``走到区域中心 + 一次逼近检测 + 覆盖式试探 + 清除`` 的乐观代价，
        超预算就停止插入（后面更远的点更进不来）。
        """
        if not targets:
            return []
        p = np.asarray(start if start is not None else self.pos, float)
        rem = self.remaining() if budget is None else float(budget)
        room = rem - self.cfg.time_reserve_s - self.cfg.min_action_budget_s \
            - self.cfg.clear_shortlist_reserve_s
        ordered = sorted(targets, key=lambda t: math.dist(p, t[2]["center"]))
        out, used = [], 0.0
        for t in ordered:
            src = p if not out else np.asarray(out[-1][2]["center"], float)
            # estimate_clear_cost 已含"从 from_pos 走到区域中心"的行程
            cost = self.estimate_clear_cost(
                t[2], from_pos=src, probe_cap=self.cfg.optimistic_probe_steps)
            if used + cost > room:
                continue          # 这个点排不进，试下一个更远的（更近的已进来）
            out.append(t)
            used += cost
        return out

    def plan_clear_tour(self, targets, remaining_s=None):
        """**动态规划（滚动时域）**清理航路：每执行一步就重新规划一次。

        与旧版（清理阶段开始时规划一次、阶段内顺序冻结）的区别：

        * 每次调用都重读台账 ⇒ **途中新定位出来的频道立刻进入航路**；
        * 各频道用**最新**的定位区域中心（逼近过程中区域会变小、中心会移动）；
        * 以**当前位置**为起点重新做最近邻 + 2-opt（可用 ``tour`` 配置切换）；
        * 本步只执行规划结果的第一个，执行完立刻重规划（rolling horizon）。

        **为什么默认不按剩余预算裁剪目标表**：目标是"边走边判"执行的 ——
        逼近、一次检测、逐点试探各自都检查剩余时间、随时可以中止，多数目标在
        前几个试探点就成功。用统一的预估代价去裁剪，会把还剩 300–400 s 的尾巴
        整段浪费掉（实测：裁剪 39.8% vs 不裁剪 41.2%）。故默认只排序、不裁剪，
        由 :meth:`clear_target` / :meth:`sweep_clear` 在动作粒度上兜底。
        ``clear_budget_truncation=True`` 可打开裁剪做对照。

        ``clear_policy`` 两种策略：
        * ``tour``（默认）：NN + 2-opt 的**全局航路结构**，按顺序执行；
        * ``rollout``：一步前瞻 + SPT 推演，直接最大化"预算内可清除个数"
          （理论更贴合目标函数，但实测更差 36.3% vs 41.2%：贪心总挑最近的，
          最后把最远的目标拖成"永远清不掉"）。
        """
        if not targets:
            return []
        self.stats["n_replans"] = self.stats.get("n_replans", 0) + 1
        remaining = self.remaining() if remaining_s is None else float(remaining_s)
        budget = remaining - self.cfg.time_reserve_s - self.cfg.min_action_budget_s
        if self.cfg.clear_policy == "rollout":
            return self._plan_rollout(targets, budget)
        if self.cfg.clear_policy == "tour_greedy_cost":
            # 贪心"每次挑预计剩余预算花得完、且最近的"目标，滚动推进。
            # 与 'tour' 的差别：这里显式用**剩余预算**逐目标判定可达性，
            # 而不是先排一条全局航路、再边走边判。
            return self._plan_greedy_cost(targets, remaining)
        # ---- 可选：先用"可达近点子集"过滤，再做航路排序 ----
        pool = list(targets)
        if self.cfg.clear_shortlist:
            pool = self.budget_feasible_shortlist(pool, start=self.pos, budget=remaining)
            self.stats["n_shortlist_kept"] = self.stats.get("n_shortlist_kept", 0) \
                + len(pool)
            self.stats["n_shortlist_in"] = self.stats.get("n_shortlist_in", 0) \
                + len(targets)
            if not pool:
                return []
        # ---- tour 策略：全局航路结构（可选预算截断）----
        order = self.order_targets(list(pool), from_pos=self.pos)
        by_ch = {t[0]: t for t in pool}
        ordered = [by_ch[ch] for ch in order if ch in by_ch]
        if not self.cfg.clear_budget_truncation:
            return ordered
        out, used, pos = [], 0.0, tuple(self.pos)
        for t in ordered:
            c = self.estimate_clear_cost(t[2], from_pos=pos,
                                         probe_cap=self.cfg.optimistic_probe_steps)
            if used + c > budget:
                continue
            out.append(t)
            used += c
            pos = tuple(t[2]["center"])
        return out

    def _plan_greedy_cost(self, targets, remaining):
        """贪心 + 剩余预算可达性（``clear_policy='tour_greedy_cost'``）。

        诊断动机：末尾 26/49 个"已定位未清除"的目标在变成可清目标时剩余时间完全够用，
        却因为全局航路把它们排在后面而没轮到（清完前面的目标后预算就没了）。
        本策略每一步只在"当前剩余预算真的能走完"的目标里挑最近的，
        从而避免"先承诺一个远点、结果后面全部落空"。

        与 ``clear_budget_truncation`` 的区别：那个是对已排好的全局航路做事后裁剪，
        本策略是**在挑选时就**把可达性作为约束。
        """
        pos = np.asarray(self.pos, float)
        left = list(targets)
        out, used = [], 0.0
        room = remaining - self.cfg.time_reserve_s - self.cfg.min_action_budget_s
        while left:
            best, best_cost = None, None
            for t in left:
                c = self.estimate_clear_cost(t[2], from_pos=pos,
                                             probe_cap=self.cfg.optimistic_probe_steps)
                if best_cost is None or c < best_cost:
                    best, best_cost = t, c
            if best is None or used + best_cost > room:
                break
            out.append(best)
            used += best_cost
            pos = np.asarray(best[2]["center"], float)
            left.remove(best)
        return out

    def _plan_rollout(self, targets, budget):
        """一步前瞻 + SPT 推演（``clear_policy='rollout'``，见 :meth:`plan_clear_tour`）。"""
        k = len(targets)
        pos0 = tuple(self.pos)
        centers = [tuple(t[2]["center"]) for t in targets]
        nprobe = []
        for t in targets:
            nprobe.append(self._probe_count(t[2]))
        t_probe = [n * (self.cfg.probe_spacing_m / V_ROBOT + T_CLEAR_FAIL) for n in nprobe]

        def leg(a, b):
            return (math.dist(a, centers[b]) / V_ROBOT + T_MEASURE + T_SWITCH
                    + t_probe[b] + T_CLEAR_OK)

        cost0 = [leg(pos0, j) for j in range(k)]

        def rollout(cur, left, tb):
            left = set(left)
            n = 0
            while True:
                best_c, best_j = None, None
                for j in left:
                    c = leg(cur, j)
                    if c <= tb and (best_c is None or c < best_c):
                        best_c, best_j = c, j
                if best_j is None:
                    return n
                tb -= best_c
                n += 1
                cur = centers[best_j]
                left.discard(best_j)

        best_j, best_key = None, None
        for j in range(k):
            if cost0[j] > budget:
                continue
            n = 1 + rollout(centers[j], [i for i in range(k) if i != j], budget - cost0[j])
            key = (n, -cost0[j])
            if best_key is None or key > best_key:
                best_key, best_j = key, j
        if best_j is None:
            return []
        out = [targets[best_j]]
        used, pos = cost0[best_j], centers[best_j]
        for j in sorted((i for i in range(k) if i != best_j), key=lambda i: leg(pos, i)):
            c = leg(pos, j)
            if used + c > budget:
                continue
            out.append(targets[j])
            used += c
            pos = centers[j]
        return out

    def order_targets(self, targets, from_pos=None):
        """航路排序：最近邻 + 2-opt（以 ``from_pos`` 为固定起点）。

        目标点用各自的（最新）定位区域中心；k ≤ 20，暴力 2-opt 代价可忽略。

        ``tour`` 三种模式（对照用）：
        * ``nn``      ：纯最近邻 —— 第一步必然最近，但总路程偏长；
        * ``nn2opt``  ：最近邻 + 2-opt（**默认**）—— 总路程最短，但 2-opt 的
          区间反转会改写**第一步**（60 局实测有 14.1% 的排序其第一步不是最近的）；
        * ``nn2opt_keepfirst``：先钉住最近的点作第一步，只对**其后**的子序列做 2-opt。
          动机：滚动时域下**只执行第一步**，后面重排一次；所以"总路程最短"并不是
          正确的目标函数，"第一步最近的 + 剩余结构合理"才是。
        """
        start = tuple(self.pos if from_pos is None else from_pos)
        if len(targets) <= 1 or self.cfg.tour == "nn":
            targets.sort(key=lambda t: math.dist(start, t[2]["center"]))
            return [t[0] for t in targets]
        pts = [tuple(t[2]["center"]) for t in targets]
        k = len(pts)
        cur = start
        # 最近邻构造
        left = list(range(k))
        seq = []
        p = cur
        while left:
            j = min(left, key=lambda i: math.dist(p, pts[i]))
            seq.append(j)
            left.remove(j)
            p = pts[j]

        def total(order):
            d = math.dist(cur, pts[order[0]])
            for a, b in zip(order, order[1:]):
                d += math.dist(pts[a], pts[b])
            return d

        # 钉住第一步时，只允许反转 index >= 1 的区间
        lo = 1 if (self.cfg.tour == "nn2opt_keepfirst" and k >= 2) else 0
        best = total(seq)
        improved = True
        while improved:
            improved = False
            for i in range(lo, k - 1):
                for j in range(i + 1, k):
                    cand = seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]
                    d = total(cand)
                    if d < best - 1e-9:
                        seq, best, improved = cand, d, True
        return [targets[i][0] for i in seq]

    def clear_phase(self):
        """清理阶段：**每清一个目标就重新规划一次**（滚动时域）。

        循环体：读最新台账 → 动态规划 → 只执行第一步 → 顺路补测（可能新增可清理频道）
        → 回到循环顶部重新规划。这样"清除之后扫描过程中新定位的位置"会立刻进入航路，
        而且航路始终以当前位置为起点、用最新的区域中心优化。
        """
        first = self.clear_targets()
        if not first:
            return 0
        self.abort_clear_phase = False
        tour0 = self.plan_clear_tour(first) if self.cfg.dynamic_replan else None
        if self.cfg.dynamic_replan and not tour0:
            return 0          # 预算内一个都排不下：静默返回，让主循环把时间用于扫描
        if not self.can_afford(self.cfg.min_action_budget_s):
            return 0
        self.log(f"清理阶段（动态重规划）：{len(first)} 个频道已定位两次 -> "
                 f"{[(t[0], round(t[2]['radius'])) for t in first]}")
        n = 0
        guard = 0
        static_order = None
        tour = tour0
        initial_chs = {t[0] for t in (tour0 or first)}
        midphase = 0
        while not self.aborted and guard < 4 * len(self.recs) + 8:
            guard += 1
            if self.cfg.dynamic_replan:
                tour = self.plan_clear_tour(self.clear_targets())   # ① 每步重新读台账并规划
                if not tour:
                    self.log("剩余时间不足以完成任何一条清理航段 -> 结束清理阶段")
                    break
                ch, rec, _br = tour[0]                 # ② 只执行第一步
                if ch not in initial_chs:
                    midphase += 1                      # 本阶段中途才定位出来的目标
                    self.log(f"  动态航路：频道{ch} 是本阶段中途新定位的，立即插队执行")
                elif len(tour) > 1:
                    self.log(f"  动态航路：本步 频道{ch}，随后 "
                             f"{[t[0] for t in tour[1:4]]}{'…' if len(tour) > 4 else ''}")
            else:                                      # 静态对照（消融用）
                targets = self.clear_targets()
                if not targets:
                    break
                if not self.can_afford(self.cfg.min_action_budget_s):
                    break
                if static_order is None:
                    static_order = self.order_targets(list(targets))
                if not static_order:
                    break
                ch = static_order.pop(0)
                t = next((x for x in targets if x[0] == ch), None)
                if t is None:
                    continue
                rec = t[1]
            if self.clear_target(ch, rec):
                n += 1
            if self.abort_clear_phase:
                self.log("预算不足 -> 结束清理阶段（剩余时间留给扫描）")
                break
            self.enroute_scan()                        # ③ 顺路补测（可能新增可清理频道）
        self.stats["n_midphase_targets"] = self.stats.get("n_midphase_targets", 0) + midphase
        return n

    def enroute_scan(self):
        """清理途中在当前位置顺手补测：既补充方位，也给新发现的频道补第二条方位。

        这一步很关键：发现一个新频道只要 6 s，但只有拿到**第二条**方位才能进入清理队列。
        所以一旦在本停点发现新频道，就立刻用第二问的"局部最优第二检测点"再测一条，
        让它本轮就能被清除，而不是等到下一次扫描（往往等不到）。
        """
        if not self.cfg.enroute_scan or self.aborted:
            return 0
        chans = self.channels_to_measure(limit=self.cfg.enroute_scan_max)
        if not chans:
            return 0
        cost = len(chans) * (T_MEASURE + T_SWITCH) + 2.0
        if not self.can_afford(cost + self.cfg.min_action_budget_s * 0.5):
            return 0
        self.log(f"  顺路补测 {len(chans)} 个频道 {chans}")
        n = self.scan_at(self.pos[0], self.pos[1], chans)
        if self.cfg.second_bearing_refine:
            fresh = [ch for ch in chans
                     if not self.recs[ch].cleared and self.recs[ch].n_bearings == 1]
            fresh.sort(key=lambda ch: -self.recs[ch].near_hits)
            for ch in fresh[:self.cfg.second_bearing_max]:
                if self.remaining() < self.cfg.second_bearing_budget_s + self.cfg.time_reserve_s:
                    break
                self.acquire_second_bearing(ch)
        return n

    def acquire_second_bearing(self, ch):
        """给"只有一条方位"的频道补第二检测点（局部最优，含行驶代价）。"""
        rec = self.recs[int(ch)]
        if rec.n_bearings != 1 or rec.cleared:
            return False
        p, info = best_refine_point(rec.pts, rec.svds, self.pos, None, n_t=100,
                                    travel_cap_m=self.cfg.refine_travel_cap_m * 1.4)
        if p is None:
            return False
        trav = math.dist(self.pos, (float(p[0]), float(p[1])))
        if not self.can_afford(trav / V_ROBOT + T_MEASURE + T_SWITCH + 20.0):
            return False
        self.log(f"  频道{ch} 新方位 -> 第二检测点 ({p[0]:.0f},{p[1]:.0f})，"
                 f"移动 {trav:.0f} m（E[D]≈{info['E_diam_m']:.0f} m，"
                 f"预计代价 {info['cost_s']:.0f} s）")
        resp = self.measure(float(p[0]), float(p[1]), ch)
        if resp.get("measure_result") == "near":
            return self.do_clear(float(p[0]), float(p[1]), ch)
        self.stats["n_second_bearing"] = self.stats.get("n_second_bearing", 0) + 1
        return rec.n_bearings >= 2

    def choose_refine_point(self, ch, rec, br):
        """侧移精定位点：与上一条视线近似正交，把交会角拉到 60–90°。"""
        c = np.asarray(br["center"], float)
        if self.cfg.refine_mode == "exact":
            p, info = best_refine_point(rec.pts, rec.svds, self.pos,
                                        {"center": c}, n_t=120,
                                        travel_cap_m=self.cfg.refine_travel_cap_m)
            if p is not None:
                return np.asarray(p, float), info
        if not rec.pts:
            return None, None
        S_last = np.asarray(rec.pts[-1], float)
        u = c - S_last
        nu = float(np.linalg.norm(u))
        if nu < 1e-6:
            return None, None
        u = u / nu
        perp = np.array([-u[1], u[0]])
        rho = min(max(1.5 * br["radius"], 80.0), self.cfg.refine_leg_m)
        best = None
        for sgn in (1.0, -1.0):
            p = c + sgn * rho * perp
            if np.hypot(*p) > R_ARENA - 1.0:
                continue
            trav = float(np.hypot(*(p - np.asarray(self.pos, float))))
            if trav > self.cfg.refine_travel_cap_m:
                continue
            if best is None or trav < best[0]:
                best = (trav, p)
        if best is None:
            return None, None
        return best[1], {"mode": "perp", "rho": rho, "travel_m": best[0]}

    def probe_points(self, c, r, poly=None, tried=()):
        """覆盖式试探点。

        * 有定位区域多边形 ``poly`` 时：只在"到多边形距离 ≤ 20 m"的格点上试
          —— 交会区域常常是细长四边形，用外接圆（面积 πr*²）试探会浪费一倍以上的点；
        * 没有多边形时退化为覆盖半径 r 的圆域。
        格点间距 ≤ 20√3 m，保证区域内任一点到某个试探点 ≤ 20 m = 清除半径，**必然成功**。

        注意"必然成功"只在**候选点不被截断**时成立：``probe_max_points`` 会按"离中心
        由近及远"截断，等于丢掉覆盖区域的**外圈**，保证随之失效（实测 r* ≥ 120 m 即开始
        截断，60 个点对应 r* ≈ 120 m，而截断前需要 61 个）。因此默认
        ``probe_unlimited=True`` 取全部候选点；``probe_max_points`` 只在显式关掉
        ``probe_unlimited``（消融对照）时才起作用。
        """
        c = np.asarray(c, float)
        s = float(self.cfg.probe_spacing_m)
        rr = min(float(r), self.cfg.probe_max_radius_m) + R_CLEAR
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
            keep = []
            for p in cand:
                if _dist_point_polygon(p, P) <= R_CLEAR + 1e-9:
                    keep.append(p)
            cand = keep if keep else cand
        cand.sort(key=lambda p: float(np.hypot(*(p - c))))
        out = []
        for p in cand:
            if any(float(np.hypot(*(p - np.asarray(q, float)))) < 2.0 for q in tried):
                continue
            out.append(p)
        if self.cfg.probe_unlimited:
            return out
        return out[:self.cfg.probe_max_points]

    def sweep_clear(self, ch, rec, c, r, poly=None):
        """在区域 ``(c, r, poly)`` 上做覆盖式试探。

        返回 :data:`SWEEP_OK` / :data:`SWEEP_MISS` / :data:`SWEEP_BUDGET` 三者之一。
        **预算不足时立刻返回 ``SWEEP_BUDGET``，一个 ``/clear`` 都不发** ——
        否则会污染 ``clear_fail``、并在论文里被误读成"区域覆盖了却没找到目标"。
        """
        probes = self.probe_points(c, r, poly=poly, tried=rec.tried_probes)
        full = self.probe_points(c, r, poly=poly)
        n_try = 0
        for p in probes:
            if self.aborted:
                self.log(f"  覆盖式试探中断：程序已中止（已试 {n_try} 点）")
                return SWEEP_MISS if n_try else SWEEP_BUDGET
            if not self.can_afford(T_CLEAR_FAIL + 5.0):
                self.log(f"  覆盖式试探放弃：剩余 {self.remaining():.0f} s 不足以支付一次 "
                         f"/clear（候选 {len(full)} 个，实际尝试 {n_try} 个）")
                self.stats["n_sweep_aborted"] += 1
                return SWEEP_BUDGET if n_try == 0 else SWEEP_MISS
            trav = math.dist(self.pos, (float(p[0]), float(p[1])))
            if not self.can_afford(trav / V_ROBOT + T_CLEAR_FAIL + 3.0):
                self.log(f"  覆盖式试探放弃：剩余 {self.remaining():.0f} s 不足以走到下一个"
                         f"试探点（{trav:.0f} m；候选 {len(full)} 个，实际尝试 {n_try} 个）")
                self.stats["n_sweep_aborted"] += 1
                return SWEEP_BUDGET if n_try == 0 else SWEEP_MISS
            n_try += 1
            rec.tried_probes.append((float(p[0]), float(p[1])))
            if self.do_clear(float(p[0]), float(p[1]), ch):
                self.log(f"  覆盖式试探命中：第 {n_try}/{len(full)} 个候选点"
                         f"（间距 {self.cfg.probe_spacing_m:.0f} m）")
                return SWEEP_OK
        # 候选点全部试完仍未命中：这才是真正的"区域内没找到目标"
        self.stats["n_sweep_miss"] += 1
        self.log(f"  覆盖式试探未命中：{n_try}/{len(full)} 个候选点全部试过"
                 f"（{'多边形区域' if poly else '外接圆'}，r*={r:.0f} m）")
        return SWEEP_MISS

    def clear_target(self, ch, rec):
        """定位→逼近→（必要时）侧移精定位→覆盖式试探清除。

        失败归因**必须三分**（见 :data:`SWEEP_BUDGET`）：

        * ``SWEEP_OK``          —— 清除成功；
        * ``SWEEP_MISS``        —— 候选点全试过仍没打中 ⇒ 累加 ``clear_fail``（真的失败了）；
        * ``SWEEP_BUDGET``      —— 预算不足、**一个 /clear 都没发** ⇒ **不**累加 ``clear_fail``，
          也不报"未清除成功"，而是收敛回清理阶段由 ``plan_clear_tour`` 决定收工。
          这正是"预算耗尽后还调用 sweep_clear 并记一笔失败"那个统计/日志缺陷的修复点。
        """
        self.log(f"清理频道{ch}：当前 {rec.n_bearings} 条方位，"
                 f"起点 ({self.pos[0]:.0f},{self.pos[1]:.0f})")
        budget_stop = False
        # (1) 逼近定位区域中心（每次逼近顺带测一条方位，移动本来就要花）
        for _ in range(self.cfg.max_approach_steps):
            br = self.bounded_region(rec)
            if br is None:
                rec.clear_fail += 1
                return False
            c = np.asarray(br["center"], float)
            d = math.dist(self.pos, tuple(c))
            if d <= max(br["radius"], self.cfg.arrive_radius_m):
                break
            cost = d / V_ROBOT + T_MEASURE + T_SWITCH + 4.0
            if not self.can_afford(cost):
                # 走不过去了：进入第 (3) 步，由覆盖式试探统一判定"预算不足"
                budget_stop = True
                break
            resp = self.measure(float(c[0]), float(c[1]), ch)
            if resp.get("measure_result") == "near":
                return self.do_clear(float(c[0]), float(c[1]), ch)
            if self.aborted:
                return False
        # (2) 区域还大：侧移一条正交视线，把 r* 压小
        if not budget_stop:
            br = self.bounded_region(rec)
            if br is not None and br["radius"] > self.cfg.direct_probe_radius_m:
                p, info = self.choose_refine_point(ch, rec, br)
                if p is not None:
                    trav = math.dist(self.pos, (float(p[0]), float(p[1])))
                    cost = trav / V_ROBOT + T_MEASURE + T_SWITCH + 4.0
                    if self.can_afford(cost):
                        self.stats["n_refine"] += 1
                        self.log(f"  侧移精定位 -> ({p[0]:.0f},{p[1]:.0f})，"
                                 f"移动 {trav:.0f} m（{info}）")
                        resp = self.measure(float(p[0]), float(p[1]), ch)
                        if resp.get("measure_result") == "near":
                            return self.do_clear(float(p[0]), float(p[1]), ch)
        # (3) 覆盖式试探清除
        br = self.bounded_region(rec)
        if br is None:
            rec.clear_fail += 1
            return False
        c = np.asarray(br["center"], float)
        r = min(br["radius"], self.cfg.probe_max_radius_m)
        poly = br.get("poly")
        st = self.sweep_clear(ch, rec, c, r, poly=poly)
        if st == SWEEP_OK:
            return True
        if st == SWEEP_BUDGET:
            # 预算不足、"一个 /clear 都没发出"：不是清除失败，不计 clear_fail、
            # 也不上升为空/随机搜索；交由调用方收敛本阶段。
            self.abort_clear_phase = True
            self.log(f"  ↷ 频道{ch} 未尝试清除（预算不足），本阶段收敛")
            return False
        # (4) 区域内没找到：说明区域被算小了（或误差超界），扩大半径再试一轮
        if br["radius"] <= self.cfg.probe_max_radius_m:
            r2 = min(br["radius"] * 1.6 + 20.0, self.cfg.probe_max_radius_m)
            self.log(f"  区域内未发现目标 -> 扩大到 r={r2:.0f} m 再试")
            st2 = self.sweep_clear(ch, rec, c, r2, poly=None)
            if st2 == SWEEP_OK:
                return True
            if st2 == SWEEP_BUDGET:
                self.abort_clear_phase = True
                self.log(f"  ↷ 频道{ch} 扩大半径后未尝试（预算不足），本阶段收敛")
                return False
        rec.clear_fail += 1
        self.log(f"  [x] 频道{ch} 本轮未清除成功（候选点已试遍仍无目标，留待后续扫描后再清）")
        return False

    # ---------------- 主循环 ----------------
    def run(self):
        t0 = time.time()
        resp = self.arena.enter()
        if resp.get("accepted") is not True:
            raise ArenaError(f"/enter 未被接受：{resp}")
        self.log(f"进入靶区：可用预算 {self.remaining():.0f} s"
                 f"（{self.arena.budget_kind()}）")
        try:
            # 第 0 轮：机器狗本来就在当前位置（原点），直接扫描全部频道
            chans0 = self.channels_to_measure()
            self.log(f"第 0 轮扫描（原地）：待测 {len(chans0)} 个频道 {chans0}")
            self.scan_points.append(self.pos)
            self.scan_at(self.pos[0], self.pos[1], chans0)
            rounds = 1
            stall = 0
            while (not self.aborted and rounds < self.cfg.max_rounds
                   and self.remaining() > self.cfg.time_reserve_s):
                did = 0
                t_before = float(self.arena.virtual_time_s)
                if self.clear_targets() and (rounds >= self.cfg.min_scan_rounds_before_clear
                                             or not self.plan_scan()):
                    did += self.clear_phase()
                    self.stats["t_clear_s"] += (float(self.arena.virtual_time_s)
                                                - t_before)
                    self.stats["t_clear_ends_s"] = float(self.arena.virtual_time_s)
                if self.aborted or self.remaining() <= self.cfg.time_reserve_s:
                    break
                plan = self.plan_scan()
                if plan is None:
                    # 扫描被预算闸门否掉时，plan_scan() 也可能只是"暂无值得测的频道"；
                    # 此时若还有可清目标，就再走一次清理阶段，而不是直接判为 stall。
                    if self.clear_targets():
                        did += self.clear_phase()
                        self.stats["t_clear_s"] += (float(self.arena.virtual_time_s)
                                                    - t_before)
                        self.stats["t_clear_ends_s"] = float(self.arena.virtual_time_s)
                    if self.aborted:
                        break
                elif self.can_afford(plan["cost_s"]) \
                        and (did == 0 or not self.clear_targets()):
                    did += self.execute_scan(plan)
                    self.stats["t_scan_s"] += (float(self.arena.virtual_time_s)
                                               - t_before)
                    rounds += 1
                if did == 0:
                    stall += 1
                    if stall >= 2:
                        self.log("没有可清理的频道、也没有值得检测的频道 -> 提前结束")
                        break
                else:
                    stall = 0
        finally:
            try:
                self.arena.exit()
            except ArenaError as e:  # 接口已关闭等
                self.log(f"/exit 异常：{e}")
        self.stats["program_runtime_s"] = time.time() - t0
        return self.report()

    # ---------------- 汇报 ----------------
    def report(self):
        truth = self.arena.truth()
        n_cleared = sum(1 for r in self.recs.values() if r.cleared)
        total = (truth or {}).get("n_sources")
        vt = float(self.arena.virtual_time_s)
        last = float(self.stats.get("vtime_at_last_clear", vt))
        st = getattr(self.arena, "stats", {})
        rep = {
            "cleared": int(n_cleared),
            "n_sources": total,
            "clear_ratio": (n_cleared / total) if total else None,
            "virtual_time_s": vt,
            "avg_clear_time_s": (last / n_cleared) if n_cleared else None,
            "program_runtime_s": float(self.stats.get("program_runtime_s", 0.0)),
            "budget_kind": self.arena.budget_kind(),
            "remaining_budget_s": self.remaining(),
            "n_measure": self.stats["n_measure"],
            "n_bearings": self.stats["n_bearings"],
            "n_clear": self.stats["n_clear"],
            "n_clear_fail": self.stats["n_clear_fail"],
            "n_scan_rounds": self.stats["n_scan_rounds"],
            "n_refine": self.stats["n_refine"],
            "n_second_bearing": self.stats.get("n_second_bearing", 0),
            "n_replans": self.stats.get("n_replans", 0),
            "n_midphase_targets": self.stats.get("n_midphase_targets", 0),
            "n_rejected": self.stats["n_rejected"],
            "travel_m": float(st.get("travel_m", 0.0)),
            "mock_stats": dict(st),
            "n_sweep_aborted": self.stats.get("n_sweep_aborted", 0),
            "n_sweep_miss": self.stats.get("n_sweep_miss", 0),
            "n_probe_issued": self.stats.get("n_probe_issued", 0),
            "n_scan_gated": self.stats.get("n_scan_gated", 0),
            "t_scan_s": self.stats.get("t_scan_s", 0.0),
            "t_clear_s": self.stats.get("t_clear_s", 0.0),
            "t_clear_ends_s": self.stats.get("t_clear_ends_s", 0.0),
            "n_leftover_located": sum(
                1 for r in self.recs.values()
                if not r.cleared and r.n_bearings >= self.cfg.clear_min_bearings),
            "scan_points": [[round(float(x), 2), round(float(y), 2)]
                            for (x, y) in self.scan_points],
            "channels": {str(ch): {"n_bearings": rec.n_bearings,
                                   "cleared": bool(rec.cleared),
                                   "no_signal": rec.no_signal,
                                   "near": rec.near_hits,
                                   "status": self.region(rec).get("status"),
                                   "r_star_m": (self.bounded_region(rec) or {}).get("radius")}
                         for ch, rec in self.recs.items() if rec.n_bearings or rec.cleared},
            "truth": truth,
        }
        return rep


# --------------------------------------------------------------------------
# 自检：策略层的结构性断言（离线 mock 上跑）
# --------------------------------------------------------------------------
def selfcheck_mock(verbose=True, seed=20260913, cases=3):
    out = []
    ok_all = True

    def rec(name, ok, detail=""):
        nonlocal ok_all
        ok_all = ok_all and bool(ok)
        out.append({"check": name, "ok": bool(ok), "detail": detail})
        if verbose:
            print(f"[{'OK ' if ok else 'FAIL'}] {name}  {detail}")

    # S1 覆盖式试探点确实能覆盖圆域（任意点 20 m 内有试探点）
    rb = P3Robot(MockArena(seed=1), P3Config())
    rng = np.random.default_rng(7)
    worst = 0.0
    for (cx, cy, r) in ((0.0, 0.0, 40.0), (500.0, -300.0, 80.0), (-900.0, 900.0, 25.0)):
        pts = np.array(rb.probe_points((cx, cy), r))
        for _ in range(400):
            a = rng.uniform(0, 2 * math.pi)
            rad = r * math.sqrt(rng.random())
            p = np.array([cx + rad * math.cos(a), cy + rad * math.sin(a)])
            d = float(np.min(np.hypot(pts[:, 0] - p[0], pts[:, 1] - p[1])))
            worst = max(worst, d)
    rec("S1 覆盖式试探：区域内任意点到最近试探点 <= 20 m（清除半径）", worst <= R_CLEAR + 1e-6,
        f"最大覆盖距离 {worst:.2f} m（试探点间距 {rb.cfg.probe_spacing_m} m）")

    # S2 端到端：mock 上跑通、清除率、时间预算
    ratios, times, cleared = [], [], []
    for k in range(cases):
        arena = MockArena(seed=seed + 100 * k)
        rb = P3Robot(arena, P3Config(), log=None)
        rep = rb.run()
        ratios.append(rep["clear_ratio"])
        times.append(rep["avg_clear_time_s"])
        cleared.append(rep["cleared"])
        if verbose:
            print(f"   案例{seed + 100 * k}: 清除 {rep['cleared']}/{rep['n_sources']}，"
                  f"虚拟时间 {rep['virtual_time_s']:.0f}s，"
                  f"平均 {rep['avg_clear_time_s']:.1f}s，"
                  f"扫描 {rep['n_scan_rounds']} 轮，检测 {rep['n_measure']} 次")
    rec("S2 mock 演练：清除率>0 且每个被清除源平均时间有限",
        all(r is not None and r > 0 for r in ratios) and all(t and t > 0 for t in times),
        f"{cases} 局：清除率 {[round(r, 3) for r in ratios]}，平均时间 "
        f"{[round(t, 1) for t in times]} s")

    # S3 策略不会超预算（mock 会计时；超时会 accepted=false）
    arena = MockArena(seed=seed + 7, budget_s=400.0)
    rb = P3Robot(arena, P3Config(), log=None)
    rep = rb.run()
    rec("S3 策略在时间预算内收工（不触发超时拒动）",
        rep["n_rejected"] == 0 and rep["virtual_time_s"] <= 400.0 + 1e-9,
        f"虚拟时间 {rep['virtual_time_s']:.1f}s / 400s，拒动 {rep['n_rejected']} 次")

    # S4 已清除的频道不再被检测（"跳过已清理过的点，节省时间"）
    arena = MockArena(seed=seed + 11)
    rb = P3Robot(arena, P3Config(), log=None)
    rep = rb.run()
    after = {}
    for ch, r in rb.recs.items():
        if r.cleared and r.cleared_at is not None:
            k = sum(1 for (_x, _y, t, _res) in r.meas_log if t > r.cleared_at + 1e-9)
            if k:
                after[ch] = k
    rec("S4 已清除频道不再被检测", not after,
        f"已清除 {sum(1 for r in rb.recs.values() if r.cleared)} 个频道；"
        f"清除后仍被检测的频道 {after or '无'}")

    # S5 定位区域一定包含真源（问题 1 的交会算法 + 模拟器误差界的一致性）
    bad5 = []
    n5 = 0
    src_map = {s["channel"]: (s["x_m"], s["y_m"]) for s in (rep["truth"] or {}).get("sources", [])}
    for ch, r in rb.recs.items():
        if r.n_bearings < 2:
            continue
        br = rb.bounded_region(r)
        if not br or not br.get("poly"):
            continue
        n5 += 1
        xy = src_map.get(ch)
        if xy is None:
            continue
        P = np.asarray(br["poly"], float)
        if not _point_in_polygon(np.asarray(xy, float), P):
            bad5.append(ch)
    rec("S5 定位区域（多边形）包含真源", not bad5,
        f"检查 {n5} 个已定位频道，越界 {bad5 or '无'}")

    # S6 探索兜底：没有任何方位时选"离已访问点最远"的点
    rb6 = P3Robot(MockArena(seed=seed + 3), P3Config(), log=None)
    sel6, _f = rb6.choose_scan_point()
    rec("S6 无方位时退化为探索点（离已访问点最远）",
        sel6["kind"] == "explore" and math.hypot(*sel6["xy"]) > 1000.0,
        f"探索点 {tuple(round(v) for v in sel6['xy'])}，距原点 "
        f"{math.hypot(*sel6['xy']):.0f} m")

    # S7 动态重规划：每清一个目标都重规划一次；静态对照为 0
    arena7 = MockArena(seed=seed + 13)
    rb7 = P3Robot(arena7, P3Config(), log=None)
    rep7 = rb7.run()
    arena7s = MockArena(seed=seed + 13)
    rb7s = P3Robot(arena7s, P3Config(dynamic_replan=False), log=None)
    rep7s = rb7s.run()
    rec("S7 动态重规划：清除途中每步重规划，静态对照 0 次",
        rep7["n_replans"] >= rep7["cleared"] >= 1 and rep7s["n_replans"] == 0,
        f"动态：清除 {rep7['cleared']} 个、重规划 {rep7['n_replans']} 次、"
        f"中途新定位插队 {rep7['n_midphase_targets']} 个；"
        f"静态：重规划 {rep7s['n_replans']} 次、中途插队 {rep7s['n_midphase_targets']} 个")

    # S8 动态航路：默认不裁剪（目标齐全）、顺序与航路排序一致
    rb8 = P3Robot(MockArena(seed=seed + 21), P3Config(), log=None)
    rb8.arena.enter()
    for ch, (gx, gy) in ((1, (300.0, 200.0)), (2, (-500.0, 700.0)), (3, (900.0, -400.0))):
        r8 = ChannelRec(ch)
        # 在真源周围取两条正交视线（交会角 90°）⇒ 定位区域小且有界
        for ang, dist in ((0.0, 500.0), (90.0, 500.0)):
            sx = gx + dist * math.cos(math.radians(ang))
            sy = gy + dist * math.sin(math.radians(ang))
            a = math.degrees(math.atan2(gy - sy, gx - sx)) % 360.0
            r8.pts.append((sx, sy))
            r8.svds.append(a)
        rb8.recs[ch] = r8
    tg8 = rb8.clear_targets()
    tour8 = rb8.plan_clear_tour(tg8)
    rec("S8 动态航路：默认不裁剪、顺序与航路排序一致",
        len(tg8) == 3 and len(tour8) == 3
        and [t[0] for t in tour8] == rb8.order_targets(list(tg8)),
        f"{len(tg8)} 个已定位频道 -> 航路 {[t[0] for t in tour8]}，"
        f"各区域半径 {[round(t[2]['radius']) for t in tour8]} m")

    # S9 覆盖式试探**不得被点数上限截断**（截断会丢掉外圈、破坏 20 m 覆盖保证）
    rb9 = P3Robot(MockArena(seed=seed + 31), P3Config(), log=None)
    n9_uncapped = len(rb9.probe_points(np.zeros(2), 195.0))
    rb9c = P3Robot(MockArena(seed=seed + 31),
                   P3Config(probe_unlimited=False, probe_max_points=60), log=None)
    n9_capped = len(rb9c.probe_points(np.zeros(2), 195.0))
    # 覆盖保证：r*=195 m 的外接圆内任一点到最近候选点必须 <= 20 m
    pts9 = np.asarray(rb9.probe_points(np.zeros(2), 195.0), float)
    rng9 = np.random.default_rng(11)
    worst9 = 0.0
    for _ in range(400):
        a = rng9.uniform(0, 2 * math.pi)
        rad = 195.0 * math.sqrt(rng9.random())
        p = np.array([rad * math.cos(a), rad * math.sin(a)])
        worst9 = max(worst9, float(np.min(np.hypot(pts9[:, 0] - p[0],
                                                   pts9[:, 1] - p[1]))))
    rec("S9 覆盖式试探不被截断（大 r* 时仍满足 20 m 覆盖保证）",
        worst9 <= R_CLEAR + 1e-6 and n9_uncapped > n9_capped,
        f"r*=195 m：{n9_uncapped} 个候选点（封顶对照 {n9_capped} 个），"
        f"最大覆盖距离 {worst9:.2f} m")

    # S10 预算不足时**不得**把"未尝试"记成"清除失败"（失败归因三分）
    arena10 = MockArena(seed=seed + 41)
    rb10 = P3Robot(arena10, P3Config(), log=None)
    rb10.arena.enter()
    rec10 = ChannelRec(4)
    for (sx, sy) in ((0.0, 0.0), (0.0, 300.0)):     # 两条正交视线 -> 小而紧的区域
        a = math.degrees(math.atan2(150.0 - sy, 100.0 - sx)) % 360.0
        rec10.pts.append((sx, sy))
        rec10.svds.append(a)
    rb10.recs[4] = rec10
    br10 = rb10.bounded_region(rec10)
    arena10.vtime = arena10.budget - 0.5          # 只剩 0.5 s：连一次 /clear 都付不起
    f10 = rb10.remaining()
    st10 = rb10.sweep_clear(4, rec10, np.asarray(br10["center"], float),
                            float(br10["radius"]), poly=br10.get("poly"))
    rec("S10 预算不足时不误记 clear_fail / 不发 /clear",
        st10 == SWEEP_BUDGET and rec10.clear_fail == 0
        and rb10.stats["n_probe_issued"] == 0
        and rb10.stats["n_sweep_aborted"] == 1,
        f"剩余预算 {f10:.1f} s（付不起一次 /clear）⇒ 返回 {st10!r}，"
        f"clear_fail={rec10.clear_fail}，发出 /clear {rb10.stats['n_probe_issued']} 次，"
        f"n_sweep_aborted={rb10.stats['n_sweep_aborted']}")

    # S11 区域中心在"排序决策 → 执行"之间**不发生漂移**（否则排序依据会过期）
    arena11 = MockArena(seed=seed + 51)
    rb11 = P3Robot(arena11, P3Config(), log=None)
    orig_plan11 = rb11.plan_clear_tour
    orig_clear11 = rb11.clear_target
    snap11 = {}
    drift11 = []

    def plan11(targets, remaining_s=None):
        for t in (targets or []):
            snap11[t[0]] = tuple(t[2]["center"])
        return orig_plan11(targets, remaining_s=remaining_s)

    def clear11(ch, rec):
        br = rb11.bounded_region(rec)
        if br is not None and ch in snap11:
            drift11.append(math.dist(snap11[ch], tuple(br["center"])))
        return orig_clear11(ch, rec)

    rb11.plan_clear_tour = plan11
    rb11.clear_target = clear11
    rb11.run()
    rec("S11 区域中心在'排序决策→执行'之间不漂移",
        bool(drift11) and max(drift11) == 0.0,
        f"检查 {len(drift11)} 次执行，最大漂移 {max(drift11) if drift11 else float('nan'):.1f} m"
        f"（新方位只在 /measure 后产生，逼近途中不产生）")

    # S12 航路排序的三种模式：第一步必为最近邻（nn / nn2opt_keepfirst），
    #     或允许 2-opt 改写第一步但总路程不更差（nn2opt）
    rb12 = P3Robot(MockArena(seed=seed + 61), P3Config(), log=None)
    rb12.arena.enter()
    pts12 = [(300.0, 200.0), (-500.0, 700.0), (900.0, -400.0),
             (-1200.0, -300.0), (200.0, -1500.0)]
    for i, (gx, gy) in enumerate(pts12, start=1):
        r12 = ChannelRec(i)
        for ang in (0.0, 90.0):
            sx = gx + 500.0 * math.cos(math.radians(ang))
            sy = gy + 500.0 * math.sin(math.radians(ang))
            r12.pts.append((sx, sy))
            r12.svds.append(math.degrees(math.atan2(gy - sy, gx - sx)) % 360.0)
        rb12.recs[i] = r12
    tg12 = rb12.clear_targets()
    start12 = tuple(rb12.pos)
    nearest12 = min(tg12, key=lambda t: math.dist(start12, t[2]["center"]))[0]

    def plen12(order):
        seq = [next(t for t in tg12 if t[0] == ch) for ch in order]
        d = math.dist(start12, seq[0][2]["center"])
        for a, b in zip(seq, seq[1:]):
            d += math.dist(a[2]["center"], b[2]["center"])
        return d

    rb12.cfg.tour = "nn"
    o_nn = rb12.order_targets(list(tg12))
    rb12.cfg.tour = "nn2opt_keepfirst"
    o_kf = rb12.order_targets(list(tg12))
    rb12.cfg.tour = "nn2opt"
    o_2o = rb12.order_targets(list(tg12))
    rec("S12 航路排序：nn 与 keepfirst 第一步为最近邻；2-opt 不劣于 nn",
        o_nn[0] == nearest12 and o_kf[0] == nearest12
        and plen12(o_2o) <= plen12(o_nn) + 1e-9,
        f"最近目标=频道{nearest12}；nn 第一步={o_nn[0]}，keepfirst={o_kf[0]}，"
        f"2-opt={o_2o[0]}；路程 nn={plen12(o_nn):.0f} m，2-opt={plen12(o_2o):.0f} m")

    if verbose:
        print(f"\n自检总结：{'全部通过' if ok_all else '存在失败项'}")
    return {"ok": ok_all, "checks": out}


def main():
    ap = argparse.ArgumentParser(description="问题3 机器狗策略（离线自检 / 单局演练）")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--mock", action="store_true", help="跑一局离线演练并打印明细")
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--dist-weight", type=float, default=1.5)
    ap.add_argument("--grid-step", type=float, default=100.0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        res = selfcheck_mock(verbose=True)
        raise SystemExit(0 if res["ok"] else 1)
    cfg = P3Config(dist_weight=args.dist_weight, grid_step=args.grid_step)
    arena = MockArena(seed=args.seed)
    rb = P3Robot(arena, cfg, log=None if args.quiet else print)
    rep = rb.run()
    print(json.dumps({k: v for k, v in rep.items()
                      if k not in ("truth", "channels", "mock_stats")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
