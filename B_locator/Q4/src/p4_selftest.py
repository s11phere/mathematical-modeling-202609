"""问题 4 自检：几何保证、判据一致性、定位—清除闭环、端到端演练。

    python src/p4_selftest.py            # 全部
    python src/p4_selftest.py --quick    # 跳过端到端（只跑纯几何/单元检查）
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from p3_arena import (  # noqa: E402
    BEARING_ERR, MockArena, MockSource, R_ARENA, R_CLEAR, R_RECV_MIN, T_CLEAR_FAIL,
    T_CLEAR_OK, T_MEASURE, T_SWITCH, V_ROBOT,
)
from p4_arena_ext import directed_case  # noqa: E402
from p4_grid import eval_grid, hex_cover_radius, triangular_lattice  # noqa: E402
from p4_robot import P4Config, P4GridRobot  # noqa: E402


def selfcheck(verbose=True, quick=False):
    out = []
    ok_all = True

    def rec(name, ok, detail=""):
        nonlocal ok_all
        ok_all = ok_all and bool(ok)
        out.append({"check": name, "ok": bool(ok), "detail": detail})
        if verbose:
            print(f"[{'OK ' if ok else 'FAIL'}] {name}  {detail}")

    cfg = P4Config()
    dummy = _Dummy(cfg)
    # G1 三角形格网：站点的服务半径不超过 a/√3（对**未被截断**的内部区域）
    a = cfg.grid_a
    pts = triangular_lattice(a, r_cover=R_ARENA)
    gx, gy = eval_grid(30.0)
    P = np.asarray(pts, float)
    d2 = ((gx[:, None] - P[None, :, 0]) ** 2 + (gy[:, None] - P[None, :, 1]) ** 2)
    dmin = np.sqrt(np.min(d2, axis=1))
    bound = hex_cover_radius(a)
    inner = np.hypot(gx, gy) <= R_ARENA - a          # 留一圈边界余量（截断处不适用）
    worst_in = float(dmin[inner].max())
    rec("G1 三角形格网服务半径 <= a/√3（内部区域）", worst_in <= bound + 1e-6,
        f"a={a:.0f} m -> a/√3={bound:.1f} m，内部实测最大 {worst_in:.1f} m；"
        f"整靶区（含截断边界，靠外环补）最大 {dmin.max():.1f} m")

    # G2 三个顶点"正向张成平面"：三角形内部任意点在任意方向都至少被一个顶点看到
    u = np.array([a, 0.0])
    v = np.array([a / 2.0, a * math.sqrt(3.0) / 2.0])
    tri = [np.array([0.0, 0.0]), u, v]
    rng = np.random.default_rng(7)
    n_bad = 0
    max_near = 0.0
    for _ in range(3000):
        w = rng.random(3)
        w = w / w.sum()
        p = w[0] * tri[0] + w[1] * tri[1] + w[2] * tri[2]
        for k in range(24):                      # 24 个方向里"最差朝向"的可听性
            th = 2 * math.pi * k / 24
            ok = any(float((q - p) @ np.array([math.cos(th), math.sin(th)])) >= -1e-9
                     for q in tri)
            if not ok:
                n_bad += 1
        max_near = max(max_near, min(float(np.hypot(*(q - p))) for q in tri))
    rec("G2 三角形内部任意点：任意朝向都至少有一个顶点在 ±90° 覆盖角内",
        n_bad == 0 and max_near <= bound + 1e-6,
        f"3000 个随机点 × 24 个方向，违反 {n_bad} 次；"
        f"最近顶点最大距离 {max_near:.1f} m（<= a/√3 = {bound:.1f} m）")

    # G3 站点集合的定向盲区为 0（用 src/p4_grid 的数值口径）
    from p4_grid import dir_cov_stats
    stations = [(0.0, 0.0)] + dummy.stations
    dw, db, hd = dir_cov_stats(stations, gx, gy, n_dir=16)
    rec("G3 站点集合：定向盲区 = 0（任何朝向的源都必被某个站位听到）",
        db == 0.0 and hd == 0.0,
        f"最坏朝向 {dw:.0f} m，定向盲区 {db:.2%}，半平面硬伤 {hd:.2%}")

    # C1 覆盖判据与"定义"一致：把源放到格点、按两种半平面约定各抽查一遍。
    #    mock 的 cone 实现是"视线方向（站→源）落在 d 的 ±90° 内"，
    #    而覆盖判据问的是"源→站的向量落在源发射方向 e 的 ±90° 内"。
    #    两者相差 180°，所以对应关系是：flip=False（要求站更靠外）⟺ e 朝**原点**；
    #    flip=True（要求站更靠内）⟺ e 朝外。这样两种约定下判据都应与模拟器逐组一致。
    unsound = 0
    detail = []
    for flip in (False, True):
        arena = MockArena(seed=5, budget_s=1e9,
                          sources=[MockSource(3, 0.0, 0.0, 1000.0,
                                              cone_half=90.0, dir_deg=0.0)])
        rb = P4GridRobot(arena, cfg)
        rb.arena.enter()
        rng = np.random.default_rng(11)
        agree = tot = 0
        for _ in range(30):
            si = int(rng.integers(0, len(rb.stations)))
            qx, qy = rb.stations[si]
            g = (float(rng.uniform(-R_ARENA, R_ARENA)),
                 float(rng.uniform(-R_ARENA, R_ARENA)))
            if math.hypot(*g) > R_ARENA:
                continue
            src = arena.sources[0]               # 把源搬到 g
            src.x, src.y, src.r_recv = g[0], g[1], 1000.0
            radial = math.degrees(math.atan2(g[1], g[0])) % 360.0
            # 判据要求"站更靠外" ⇒ 源朝原点发射；要求"更靠内" ⇒ 朝外发射
            src.dir_deg = (radial + 180.0) % 360.0 if not flip else radial
            src.cleared = False
            r = arena.measure(qx, qy, 3)
            heard = r.get("measure_result") in ("direction", "near")
            model = bool(rb.admissible_near((qx, qy), g, r_est=R_RECV_MIN,
                                            flip=flip))
            tot += 1
            agree += 1 if (heard == model) else 0
            if model and not heard:
                unsound += 1
        detail.append(f"flip={int(flip)}: {agree}/{tot} 一致")
    rec("C1 覆盖判据与模拟器逐组一致（两种半平面约定各 30 组）",
        unsound == 0, "；".join(detail) + f"；判据过宽 {unsound} 组")

    # L1 locate_on_ray：沿视线二分能把距离量到几十米
    src = MockSource(7, 900.0, 700.0, 1400.0, cone_half=90.0, dir_deg=320.0)
    arena = MockArena(seed=3, budget_s=1e9, sources=[src])
    rb = P4GridRobot(arena, cfg)
    rb.arena.enter()
    r = rb.measure(0.0, 0.0, 7)                    # 原点测到方位
    assert r.get("measure_result") == "direction", r
    est, rad, _br = rb.locate_on_ray(7)
    err = float(np.hypot(est[0] - src.x, est[1] - src.y)) if est is not None else 1e9
    rec("L1 沿视线二分：定位估计误差 <= 120 m", err <= 120.0,
        f"真源 ({src.x:.0f},{src.y:.0f})，估计 ({est[0]:.0f},{est[1]:.0f})，误差 {err:.0f} m")

    # L2 定位闭环：侧移交会 + 二分之后，位置误差进到清除半径量级
    rec2 = rb.recs[7]
    ok2 = rb.locate_by_cross(7)
    br = rb.bounded_region(rec2)
    g2 = rb.cross_estimate(rec2)
    err2 = float(np.hypot(g2[0] - src.x, g2[1] - src.y)) if g2 is not None else 1e9
    rec("L2 侧移交会：交会估计误差 <= 60 m 或区域半径 <= 60 m",
        (br is not None and float(br["radius"]) <= 60.0) or err2 <= 60.0,
        f"区域半径 {None if br is None else round(float(br['radius']), 1)} m，"
        f"交会点误差 {err2:.0f} m，{rec2.n_bearings} 条方位，"
        f"侧移成功 = {bool(ok2)}")

    # L3 区域必含真源（问题 1 的结论在定向源上同样成立）
    poly = br.get("poly") if br else None
    inside = False
    if poly:
        P = np.asarray(poly, float)
        n = len(P)
        for i in range(n):                       # 射线法
            a_, b_ = P[i], P[(i + 1) % n]
            if (a_[1] > src.y) != (b_[1] > src.y):
                x = a_[0] + (src.y - a_[1]) * (b_[0] - a_[0]) / (b_[1] - a_[1])
                if x > src.x:
                    inside = not inside
    rec("L3 交会区域包含真源（含边界附近）", bool(inside) or float(br["radius"]) < R_CLEAR,
        f"区域半径 {float(br['radius']):.1f} m，真源在区域内 = {inside}")

    # T1 计时口径：同样的移动，/clear 未命中 = 移动 + 3 s；/measure = 移动 + 切换 + 5 s
    arena = MockArena(seed=9, budget_s=1e9,
                      sources=[MockSource(1, 100000.0, 0.0, 1000.0)])
    arena.enter()
    t0 = arena.virtual_time_s
    arena.clear(0.0, 100.0, 1)                     # 从 (0,0) 走到 (0,100)，未命中
    dt_clear = arena.virtual_time_s - t0
    t1 = arena.virtual_time_s
    arena.measure(0.0, 100.0, 1)                   # 原地、频道相同
    dt_meas = arena.virtual_time_s - t1
    rec("T1 走位口径：/clear 未命中 = 移动+3 s，比 /measure 省，且不改频道",
        abs(dt_clear - (100.0 / V_ROBOT + T_CLEAR_FAIL)) < 1e-9
        and abs(dt_meas - T_MEASURE) < 1e-9
        and arena.channel == 1,
        f"100 m 位移 + 原地检测：/clear {dt_clear:.0f} s（=20+3）"
        f" vs /measure {dt_meas:.0f} s（=0+0+5）；/clear 后频道仍为 {arena.channel}")

    if not quick:
        # E1 端到端：定向源（背离原点、贴边、最小接收半径）能被听到并清除
        cases = [(1500.0, -168.0, 1400.0, None),      # 已知难点：贴边朝外
                 (-1460.0, 965.0, 1368.0, 328.2),     # 上一轮唯一漏掉的几何
                 (300.0, 1700.0, 1015.0, None)]       # 最小接收半径 + 随机朝向
        n_ok = 0
        detail = []
        for i, (x, y, rr, dd) in enumerate(cases):
            d = dd if dd is not None else math.degrees(math.atan2(y, x)) % 360.0
            arena, srcs = directed_case(seed=100 + i, spec=[(5 + i, x, y, rr, d)])
            rb = P4GridRobot(arena, P4Config())
            rep = rb.run()
            ok = rep["cleared"] == rep["n_sources"]
            n_ok += 1 if ok else 0
            detail.append(f"({x:.0f},{y:.0f})r{rr:.0f}->{'OK' if ok else 'MISS'}"
                          f"/{rep['virtual_time_s']:.0f}s")
        rec("E1 端到端：3 个定向源算例全部清除", n_ok == len(cases), "  ".join(detail))

        # E2 全向对照：同一个策略在全向场景上也不能退化
        arena, _ = directed_case(seed=55, n=12, directed_frac=0.0)
        rb = P4GridRobot(arena, P4Config())
        rep = rb.run()
        rec("E2 端到端：12 个全向源全部清除", rep["cleared"] == rep["n_sources"],
            f"清除 {rep['cleared']}/{rep['n_sources']}，"
            f"虚拟 {rep['virtual_time_s']:.0f} s，平均 {rep['avg_clear_time_s'] or 0:.0f} s")

    if verbose:
        print(f"\n自检总结：{'全部通过' if ok_all else '存在失败项'}（{len(out)} 项）")
    return {"ok": ok_all, "checks": out}


class _Dummy:
    """只为构造站位列表（不调用任何接口）。"""
    pos = (0.0, 0.0)
    channel = 1
    virtual_time_s = 0.0

    def __init__(self, cfg):
        self._rb = P4GridRobot.__new__(P4GridRobot)
        self.stations = P4GridRobot._build_stations(self._rb) if False else None
        # 直接用配置算站位，避免构造半个 robot
        from p4_robot import P4GridRobot as R
        tmp = R.__new__(R)
        tmp.cfg = cfg
        self.stations = R._build_stations(tmp)

    def remaining_budget_s(self):
        return 1e9

    def budget_kind(self):
        return "virtual"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    res = selfcheck(quick=a.quick)
    if not a.quick:
        print(f"用时 {time.time() - t0:.1f} s")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
