"""B 题问题 3：机器狗与模拟器之间的统一接口层。

两个后端对上层暴露**完全相同的接口与返回字段**（字段名与模拟器 JSON 一致），
因此 :mod:`p3_robot` 里的策略代码在"离线演练"和"真实模拟器"上完全一致：

* :class:`MockArena` —— 完全离线复刻附件 1/附件 2 的物理与计时规则。
  用于自检、调参、批量演练（可以跑几百局，正式测试只有 3 次机会）。
* :class:`HttpArena` —— 真实模拟器的 HTTP+JSON 客户端，负责协议里最容易踩的坑：
  串行发送、``request_id`` 幂等与重试、``accepted`` 与 HTTP 状态双重校验、
  ``remaining_real_duration_s`` 动态预算、自身行为日志（论文支撑材料需要）。

计时规则（附件 1 表 1 / 附件 2 第 4 节）
----------------------------------------
* ``/measure``：移动距离/5 + （频道变化 ? 1 : 0） + 5 秒；只有 ``/measure`` 会切换频道；
* ``/clear``：移动距离/5 + （成功 5 / 未发现 3）秒；**不切换频道**；
* ``/enter``、``/exit`` 不推进虚拟时钟；
* 示向度误差在 [-1°,1°] 内，**同一地点固定**（本模块用"平滑随机场 + 局地量化项"建模）。
"""
from __future__ import annotations

import json
import math
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field as dc_field

import numpy as np

# --------------------------------------------------------------------------
# 物理常数（题目附录 1/2、模拟器接口说明）
# --------------------------------------------------------------------------
R_ARENA = 1800.0            # 靶区半径（m）
V_ROBOT = 5.0               # 移动速度（m/s）
T_MEASURE = 5.0             # 一次检测耗时（s）
T_SWITCH = 1.0              # 频道切换耗时（s）
T_CLEAR_OK = 5.0            # 成功清除耗时（s）：光学 3 + 激光 2
T_CLEAR_FAIL = 3.0          # 未发现目标时的光学精确定位耗时（s）
T_CLEAR = T_CLEAR_OK
NEAR_R = 5.0                # 近场阈值（m）：更近时返回 near，无示向度
R_CLEAR = 20.0              # 清除半径（m）
R_RECV_MIN, R_RECV_MAX = 1000.0, 1500.0
BEARING_ERR = 1.0           # 示向度误差界（度）
CHANNELS = tuple(range(1, 21))
# 程序运行时间（现实时间）上限（s）：题目附录 3，/enter 响应里由 remaining_real_duration_s 给出
DEF_BUDGET_S = 1200.0
# 虚拟世界限时（s）：接口说明 1.4/4.5，默认 360000（100 小时）。
# **注意**：这是虚拟时钟的上限，与上面 1200 s 的现实时间预算是两回事。
# 离线 mock 必须用同一个值，否则等于给离线演练加了一条真实测试里不存在的约束。
DEF_VIRTUAL_LIMIT_S = 360000.0
COORD_LIMIT = 2_000_000.0   # 接口允许的坐标绝对值上限（m）


class ArenaError(RuntimeError):
    """接口层不可恢复错误（网络重试用尽、响应无法解析等）。"""


# --------------------------------------------------------------------------
# 离线模拟器
# --------------------------------------------------------------------------
@dataclass
class MockSource:
    channel: int
    x: float
    y: float
    r_recv: float
    cone_half: float = 180.0      # 覆盖半角：180 = 全向（问题 4 会用到 <180）
    dir_deg: float | None = None
    cleared: bool = False

    @property
    def xy(self):
        return (self.x, self.y)


class MockArena:
    """离线复刻的模拟器（问题 3：全向源）。"""

    def __init__(self, seed=0, n_sources=None, budget_s=DEF_VIRTUAL_LIMIT_S,
                 r_arena=R_ARENA, sources=None, error_corr_m=250.0,
                 error_local_w=0.25, verbose=False):
        """``budget_s`` = **虚拟时钟上限**（默认 360000 s，与真实模拟器一致）。"""
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.r_arena = float(r_arena)
        self.budget = float(budget_s)
        self.sources = list(sources) if sources is not None else self._gen_sources(n_sources)
        self._init_error_field(error_corr_m, error_local_w)
        self.pos = (0.0, 0.0)
        self.channel = 1
        self.vtime = 0.0
        self.entered = False
        self.finished = False
        self.verbose = verbose
        self.actions: list[dict] = []
        self.stats = {"n_measure": 0, "n_clear": 0, "n_clear_fail": 0,
                      "travel_m": 0.0, "n_direction": 0, "n_near": 0, "n_no_signal": 0}

    # ---------------- 场景生成 ----------------
    def _gen_sources(self, n_sources=None):
        rng = self.rng
        n = int(n_sources) if n_sources else int(rng.integers(10, 17))
        n = max(1, min(n, len(CHANNELS)))
        chans = rng.choice(np.asarray(CHANNELS), size=n, replace=False)
        out = []
        for ch in chans:
            r = self.r_arena * math.sqrt(float(rng.random()))
            a = float(rng.uniform(0, 2 * math.pi))
            out.append(MockSource(channel=int(ch), x=r * math.cos(a), y=r * math.sin(a),
                                  r_recv=float(rng.uniform(R_RECV_MIN, R_RECV_MAX))))
        return out

    def _init_error_field(self, corr_m, local_w):
        """示向度误差场：平滑随机场（模拟电磁环境）+ 局地量化项；量程严格 ±1°。"""
        rng = self.rng
        self._waves = []
        for _ in range(12):
            lam = float(rng.uniform(max(corr_m * 1.5, 120.0), 3.0 * self.r_arena))
            ang = float(rng.uniform(0, 2 * math.pi))
            self._waves.append((2 * math.pi * math.cos(ang) / lam,
                                2 * math.pi * math.sin(ang) / lam,
                                float(rng.uniform(0, 2 * math.pi)),
                                1.0 / lam))
        # 归一化：用靶区内抽样点的最大绝对值做标定，再乘 1.05 并截断到 ±1
        pts = self._sample_disc(4000, rng)
        raw = self._raw_field(pts[:, 0], pts[:, 1])
        self._scale = max(float(np.max(np.abs(raw))) * 1.05, 1e-9)
        self._local_w = float(local_w)
        self._local_seed = int(rng.integers(1, 10 ** 6))

    def _sample_disc(self, n, rng):
        r = self.r_arena * np.sqrt(rng.random(n))
        a = rng.uniform(0, 2 * math.pi, n)
        return np.stack([r * np.cos(a), r * np.sin(a)], axis=1)

    def _raw_field(self, x, y):
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        v = np.zeros_like(x)
        for (kx, ky, ph, a) in self._waves:
            v = v + a * np.sin(kx * x + ky * y + ph)
        return v

    def _local_field(self, x, y):
        i = int(math.floor(x / 25.0))
        j = int(math.floor(y / 25.0))
        h = (i * 73856093) ^ (j * 19349663) ^ (self._local_seed * 83492791)
        h &= 0x7FFFFFFF
        return (h % 200001) / 100000.0 - 1.0

    def env_error(self, x, y):
        """该地点的示向度误差（度，[-1,1]，同一地点固定）。"""
        v = (float(self._raw_field(x, y)) / self._scale
             + self._local_w * self._local_field(x, y))
        return float(max(-1.0, min(1.0, v)))

    # ---------------- 状态查询 ----------------
    @property
    def virtual_time_s(self):
        return self.vtime

    def remaining_budget_s(self):
        return max(0.0, self.budget - self.vtime)

    def budget_kind(self):
        return "virtual"

    def truth(self):
        return {"n_sources": len(self.sources),
                "n_cleared": sum(1 for s in self.sources if s.cleared),
                "sources": [{"channel": s.channel, "x_m": round(s.x, 3),
                             "y_m": round(s.y, 3), "r_recv_m": round(s.r_recv, 3),
                             "cleared": bool(s.cleared)} for s in self.sources]}

    # ---------------- 内部工具 ----------------
    def _src_of(self, channel):
        for s in self.sources:
            if s.channel == int(channel):
                return s
        return None

    def _reject(self, reason, **kw):
        r = {"accepted": False, "real_timestamp_ms": int(time.time() * 1000),
             "virtual_time_s": 0.0, "reason": reason}
        r.update(kw)
        return r

    def _advance(self, x, y, dt, kind, payload):
        d = math.hypot(x - self.pos[0], y - self.pos[1])
        self.stats["travel_m"] += d
        self.vtime += dt
        self.pos = (float(x), float(y))
        rec = {"kind": kind, "x": float(x), "y": float(y), "dt": float(dt),
               "dist_m": float(d), "virtual_time_s": float(self.vtime)}
        rec.update(payload)
        self.actions.append(rec)
        if self.verbose:
            print(f"    [mock] {kind} ({x:.0f},{y:.0f}) dt={dt:.1f}s "
                  f"t={self.vtime:.1f}s {payload}")
        return rec

    # ---------------- 四条指令 ----------------
    def enter(self):
        if self.entered:
            return self._reject("already_entered")
        self.entered = True
        self.actions.append({"kind": "enter", "virtual_time_s": 0.0})
        return {"accepted": True, "real_timestamp_ms": int(time.time() * 1000),
                "virtual_time_s": 0.0, "max_virtual_duration_s": self.budget,
                "max_real_duration_s": self.budget,
                "remaining_real_duration_s": int(self.budget)}

    def measure(self, x, y, channel):
        if not self.entered:
            return self._reject("not_entered")
        if self.finished:
            return self._reject("finished")
        x, y, ch = float(x), float(y), int(channel)
        if not (math.isfinite(x) and math.isfinite(y)) \
                or abs(x) > COORD_LIMIT or abs(y) > COORD_LIMIT:
            return self._reject("bad_position")
        if ch not in CHANNELS:
            return self._reject("bad_channel")
        switch = T_SWITCH if ch != self.channel else 0.0
        d = math.hypot(x - self.pos[0], y - self.pos[1])
        dt = d / V_ROBOT + switch + T_MEASURE
        if self.vtime + dt > self.budget + 1e-9:
            self.finished = True
            return self._reject("timeout")
        src = self._src_of(ch)
        svd = None
        if src is None or src.cleared:
            result = "no_signal"
        else:
            dist = math.hypot(x - src.x, y - src.y)
            in_cone = True
            if src.cone_half < 180.0:
                a = math.degrees(math.atan2(src.y - y, src.x - x))
                ref = src.dir_deg if src.dir_deg is not None else 0.0
                in_cone = abs((a - ref + 180.0) % 360.0 - 180.0) <= src.cone_half + 1e-12
            if dist > src.r_recv or not in_cone:
                result = "no_signal"
            elif dist <= NEAR_R:
                result = "near"
            else:
                result = "direction"
                a = math.degrees(math.atan2(src.y - y, src.x - x))
                svd = round((a + self.env_error(x, y)) % 360.0, 2)
        self.channel = ch
        self.stats["n_measure"] += 1
        self.stats["n_" + result] += 1
        self._advance(x, y, dt, "measure",
                      {"channel": ch, "measure_result": result, "svd_deg": svd,
                       "switch_s": switch})
        resp = {"accepted": True, "real_timestamp_ms": int(time.time() * 1000),
                "virtual_time_s": self.vtime, "measure_result": result}
        if svd is not None:
            resp["svd_deg"] = svd
        return resp

    def clear(self, x, y, channel):
        if not self.entered:
            return self._reject("not_entered")
        if self.finished:
            return self._reject("finished")
        x, y, ch = float(x), float(y), int(channel)
        if not (math.isfinite(x) and math.isfinite(y)) \
                or abs(x) > COORD_LIMIT or abs(y) > COORD_LIMIT:
            return self._reject("bad_position")
        if ch not in CHANNELS:
            return self._reject("bad_channel")
        d = math.hypot(x - self.pos[0], y - self.pos[1])
        src = self._src_of(ch)
        ok = bool(src is not None and not src.cleared
                  and math.hypot(x - src.x, y - src.y) <= R_CLEAR + 1e-9)
        dt = d / V_ROBOT + (T_CLEAR_OK if ok else T_CLEAR_FAIL)
        if self.vtime + dt > self.budget + 1e-9:
            self.finished = True
            return self._reject("timeout")
        if ok:
            src.cleared = True
        self.stats["n_clear"] += 1
        if not ok:
            self.stats["n_clear_fail"] += 1
        self._advance(x, y, dt, "clear",
                      {"channel": ch, "clear_result": "success" if ok else "no_target_in_range"})
        return {"accepted": True, "real_timestamp_ms": int(time.time() * 1000),
                "virtual_time_s": self.vtime,
                "clear_result": "success" if ok else "no_target_in_range"}

    def exit(self):
        self.finished = True
        self.actions.append({"kind": "exit", "virtual_time_s": self.vtime})
        return {"accepted": True, "real_timestamp_ms": int(time.time() * 1000),
                "virtual_time_s": self.vtime, "exit_reason": "user_exit"}


# --------------------------------------------------------------------------
# 真实模拟器客户端
# --------------------------------------------------------------------------
class HttpArena:
    """模拟器 HTTP+JSON 客户端（默认 http://127.0.0.1:2026）。"""

    def __init__(self, base_url="http://127.0.0.1:2026", robot_id="",
                 arena_id="default", timeout=5.0, max_retries=4, retry_delay=0.4,
                 log_path=None, budget_s=DEF_BUDGET_S, safety_margin_s=3.0,
                 enter_wait_s=40.0):
        self.base_url = base_url.rstrip("/")
        self.robot_id = robot_id
        self.arena_id = arena_id
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self.retry_delay = float(retry_delay)
        self.log_path = log_path
        self.budget = float(budget_s)
        self.safety_margin_s = float(safety_margin_s)
        self.enter_wait_s = float(enter_wait_s)
        self._n = 0
        self.entered = False
        self.pos = (0.0, 0.0)
        self.channel = 1
        self.vtime = 0.0
        self.remaining_real0 = float(budget_s)
        self._t0 = None
        self.actions: list[dict] = []
        # 与 MockArena 同名的统计（接口不返回行程，客户端自己按动作位置累加，
        # 只统计 accepted=true 的动作，与虚拟时间的推进口径一致）
        self.stats = {"n_measure": 0, "n_clear": 0, "n_clear_fail": 0,
                      "travel_m": 0.0, "n_direction": 0, "n_near": 0, "n_no_signal": 0}
        if self.log_path:
            os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write(json.dumps({"kind": "session", "base_url": self.base_url,
                                    "robot_id": self.robot_id}, ensure_ascii=False) + "\n")

    # ---------------- HTTP ----------------
    def _rid(self, tag):
        self._n += 1
        return f"{tag}-{self._n}"

    def _base(self, rid):
        return {"arena_id": self.arena_id, "robot_id": self.robot_id, "request_id": rid}

    def _post(self, path, payload, tag):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_err = None
        for attempt in range(self.max_retries):
            req = urllib.request.Request(
                self.base_url + path, data=data,
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = r.read().decode("utf-8")
                resp = json.loads(body)
                self._log({"kind": "resp", "path": path, "attempt": attempt, "resp": resp})
                return resp
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", "replace")
                    resp = json.loads(body)
                    self._log({"kind": "http_error", "path": path, "code": e.code,
                               "resp": resp})
                    return resp
                except Exception:
                    self._log({"kind": "http_error", "path": path, "code": e.code,
                               "body": body[:500]})
                    raise ArenaError(f"{path} HTTP {e.code}: {body[:200]}") from e
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
                # 网络超时/中断：按协议重试完全相同的动作（复用 request_id 与内容）
                last_err = e
                self._log({"kind": "net_error", "path": path, "attempt": attempt,
                           "error": repr(e)})
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_delay * (attempt + 1))
        raise ArenaError(f"{path} 请求失败（已重试 {self.max_retries} 次）：{last_err!r}")

    def _log(self, rec):
        rec["wall_s"] = round(time.time() - (self._t0 or time.time()), 3)
        self.actions.append(rec)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _new(self, path, extra, tag):
        rid = self._rid(tag)
        payload = self._base(rid)
        payload.update(extra)
        self._log({"kind": "req", "path": path, "payload": payload})
        return self._post(path, payload, tag)

    # ---------------- 状态 ----------------
    @property
    def virtual_time_s(self):
        return self.vtime

    def remaining_budget_s(self):
        if self._t0 is None:
            return self.remaining_real0
        used = time.monotonic() - self._t0
        return max(0.0, self.remaining_real0 - used - self.safety_margin_s)

    def budget_kind(self):
        return "real"

    def truth(self):
        return None

    # ---------------- 四条指令 ----------------
    def enter(self):
        """进入靶区。接口未开放时（倒计时未结束 / 测试未开始）会重试同一 request_id。

        协议规定"同一 request_id + 同一内容返回第一次的完整响应"，所以用固定的
        request_id 重试 /enter 是安全的（不会重复进入、也不会推进时钟）。
        """
        rid = self._rid("enter")
        payload = self._base(rid)
        self._log({"kind": "req", "path": "/enter", "payload": payload})
        t0 = time.monotonic()
        last = None
        keep_retries = self.max_retries
        self.max_retries = min(keep_retries, 2)   # 接口未开放时缩短单次重试，尽快进入下一轮
        try:
            while True:
                try:
                    resp = self._post("/enter", payload, "enter")
                except ArenaError as e:
                    resp, last = None, e
                if resp is not None and resp.get("accepted") is True:
                    self.entered = True
                    self._t0 = time.monotonic()
                    self.remaining_real0 = float(resp.get("remaining_real_duration_s",
                                                          self.budget))
                    self.vtime = float(resp.get("virtual_time_s", 0.0))
                    return resp
                if resp is not None and resp.get("accepted") is False \
                        and resp.get("reason") == "already_entered":
                    return resp
                if time.monotonic() - t0 > self.enter_wait_s:
                    if resp is not None:
                        return resp
                    raise ArenaError(
                        f"/enter 在 {self.enter_wait_s:.0f} s 内一直失败：{last!r}")
                time.sleep(2.0)
        finally:
            self.max_retries = keep_retries

    def measure(self, x, y, channel):
        resp = self._new("/measure", {"position": {"x": float(x), "y": float(y)},
                                      "channel": int(channel)}, "measure")
        if resp.get("accepted") is True:
            self.stats["travel_m"] += math.hypot(float(x) - self.pos[0],
                                                 float(y) - self.pos[1])
            self.pos = (float(x), float(y))
            self.channel = int(channel)
            self.vtime = float(resp.get("virtual_time_s", self.vtime))
            res = resp.get("measure_result")
            self.stats["n_measure"] += 1
            if res in ("direction", "near", "no_signal"):
                self.stats["n_" + res] += 1
        return resp

    def clear(self, x, y, channel):
        resp = self._new("/clear", {"position": {"x": float(x), "y": float(y)},
                                    "channel": int(channel)}, "clear")
        if resp.get("accepted") is True:
            self.stats["travel_m"] += math.hypot(float(x) - self.pos[0],
                                                 float(y) - self.pos[1])
            self.pos = (float(x), float(y))
            self.vtime = float(resp.get("virtual_time_s", self.vtime))
            self.stats["n_clear"] += 1
            if resp.get("clear_result") != "success":
                self.stats["n_clear_fail"] += 1
        return resp

    def exit(self):
        return self._new("/exit", {}, "exit")


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------
def selfcheck(verbose=True, seed=20260913):
    """核对 MockArena 是否忠实复刻附件 1/2 的规则。"""
    out = []
    ok_all = True

    def rec(name, ok, detail=""):
        nonlocal ok_all
        ok_all = ok_all and bool(ok)
        out.append({"check": name, "ok": bool(ok), "detail": detail})
        if verbose:
            print(f"[{'OK ' if ok else 'FAIL'}] {name}  {detail}")

    # A1 附件 1 表 2 的计时算例（(300,400) 频道1 -> 频道2 -> /clear 未发现 -> 频道2）
    a = MockArena(seed=1, sources=[MockSource(3, 100000.0, 0.0, 1000.0)])
    a.enter()
    r1 = a.measure(300.0, 400.0, 1)
    r2 = a.measure(300.0, 400.0, 2)
    r3 = a.clear(300.0, 0.0, 3)
    r4 = a.measure(300.0, 0.0, 2)
    ok1 = (abs(r1["virtual_time_s"] - 105.0) < 1e-9
           and abs(r2["virtual_time_s"] - 111.0) < 1e-9
           and abs(r3["virtual_time_s"] - 194.0) < 1e-9
           and abs(r4["virtual_time_s"] - 199.0) < 1e-9)
    rec("A1 计时算例与附件1表2逐条一致（105/111/194/199 s）", ok1,
        f"{r1['virtual_time_s']}, {r2['virtual_time_s']}, "
        f"{r3['virtual_time_s']}, {r4['virtual_time_s']}")

    # A2 /clear 不切换频道，也不产生切换耗时
    b = MockArena(seed=2, sources=[MockSource(1, 0.0, 0.0, 1000.0)])
    b.enter()
    b.measure(0.0, 100.0, 1)
    t0 = b.virtual_time_s
    b.clear(0.0, 50.0, 7)
    rec("A2 /clear 不切换频道、不产生切换耗时",
        abs(b.virtual_time_s - t0 - (50.0 / V_ROBOT + T_CLEAR_FAIL)) < 1e-9
        and b.channel == 1,
        f"Δt={b.virtual_time_s - t0:.1f}s, 当前频道={b.channel}")

    # A3 三种检测结果与清除半径
    src = MockSource(5, 0.0, 0.0, 1000.0)
    c = MockArena(seed=3, sources=[src])
    c.enter()
    m_far = c.measure(0.0, 0.0, 5)          # 距离 0 <= 5 m -> near
    m_dir = c.measure(0.0, 300.0, 5)        # direction（真方位 270°）
    m_no = c.measure(0.0, 1200.0, 5)        # 超出 1000 m -> no_signal
    ok3 = (m_far["measure_result"] == "near" and m_dir["measure_result"] == "direction"
           and abs(m_dir["svd_deg"] - 270.0) <= BEARING_ERR + 1e-9
           and m_no["measure_result"] == "no_signal")
    rec("A3 near / direction / no_signal 三种结果与真方位一致", ok3,
        f"near={m_far['measure_result']}, dir={m_dir.get('svd_deg')}°, "
        f"no={m_no['measure_result']}")
    cl_far = c.clear(0.0, 1000.0, 5)
    cl_ok = c.clear(0.0, 20.0, 5)
    rec("A4 清除半径 20 m：远处未发现、20 m 内成功",
        cl_far["clear_result"] == "no_target_in_range"
        and cl_ok["clear_result"] == "success",
        f"{cl_far['clear_result']} / {cl_ok['clear_result']}")
    rec("A5 同一干扰源只能清除一次",
        c.clear(0.0, 0.0, 5)["clear_result"] == "no_target_in_range",
        "二次清除返回 no_target_in_range")

    # A6 误差界与"同一地点固定"
    d = MockArena(seed=4)
    e1 = d.env_error(123.0, -456.0)
    e2 = d.env_error(123.0, -456.0)
    vals = [d.env_error(float(x), float(y)) for x, y in d._sample_disc(500, d.rng)]
    rec("A6 示向度误差：|e|<=1° 且同一地点固定",
        abs(e1 - e2) < 1e-12 and max(abs(v) for v in vals) <= 1.0 + 1e-12,
        f"e={e1:.4f}，重复一致；500 点最大 |e|={max(abs(v) for v in vals):.4f}")

    # A7 真源一定落在"测得方位 ±1°"的楔内（区间算法成立的前提）
    bad = 0
    nchk = 0
    d2 = MockArena(seed=4, budget_s=1e9)
    d2.enter()
    for s in d2.sources:
        for _ in range(3):
            aa = float(d2.rng.uniform(0, 2 * math.pi))
            dd = float(d2.rng.uniform(50.0, 0.9 * s.r_recv))
            x, y = s.x + dd * math.cos(aa), s.y + dd * math.sin(aa)
            r = d2.measure(x, y, s.channel)
            if r.get("accepted") is not True or r.get("measure_result") != "direction":
                continue
            nchk += 1
            true_a = math.degrees(math.atan2(s.y - y, s.x - x)) % 360.0
            if abs((true_a - r["svd_deg"] + 180.0) % 360.0 - 180.0) > BEARING_ERR + 1e-9:
                bad += 1
    rec("A7 真方位与示向度之差恒 <= 1°", bad == 0 and nchk > 0,
        f"{nchk} 次检测，越界 {bad} 次")

    # A8 超时拒动
    e = MockArena(seed=5, budget_s=50.0, sources=[MockSource(1, 0.0, 0.0, 1000.0)])
    e.enter()
    e.measure(0.0, 1000.0, 1)           # 200 + 5 = 205 s > 50 s
    rec("A8 超出时间预算的请求 accepted=false 且不推进时钟",
        e.virtual_time_s == 0.0 and e.finished,
        f"vtime={e.virtual_time_s}")

    if verbose:
        print(f"\n自检总结：{'全部通过' if ok_all else '存在失败项'}")
    return {"ok": ok_all, "checks": out}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="问题3 接口层自检")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    res = selfcheck()
    raise SystemExit(0 if res["ok"] else 1)
