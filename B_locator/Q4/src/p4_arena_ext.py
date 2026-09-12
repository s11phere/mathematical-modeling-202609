"""问题 4 的场景生成（定向 / 全向混合案例）。

单独成一个模块，是为了让 `p4_run.py`（演练/正式测试入口）、`p4_selftest.py`（自检）
与 `p4_diag.py`（诊断）用**同一套**案例定义 —— 否则"自检通过但演练漏源"这类问题
会被掩盖。

题目口径（附件 2 第 2.2 节 + 附录 1）：
* 定向源的**有效覆盖角度范围是 180°** ⇒ 覆盖半角 ``cone_half = 90°``；
* 定向方向未知，可以是任意角度；
* 有效接收半径在 1000–1500 m 之间；
* 干扰源总数 10–16 个（本题按 10–16 均匀取）。
"""
from __future__ import annotations

import math

import numpy as np

from p3_arena import MockArena, MockSource, R_ARENA, R_RECV_MAX, R_RECV_MIN

SCENARIOS = ("directed", "directed_only", "directed_edge", "omni", "uniform", "mixed_uniform", "minrange")


def directed_case(seed=0, n=None, spec=None, directed_frac=0.5,
                  r_recv=(R_RECV_MIN, R_RECV_MAX), budget=360000.0,
                  outward_frac=0.5):
    """造一个案例；返回 ``(arena, sources)``。

    * ``spec`` 给定 ``[(channel, x, y, r_recv, dir_deg), ...]`` 时直接照做（自检用）；
    * ``n`` 不给就随机取 10–16 个源；
    * ``directed_frac``：定向源比例；``outward_frac``：其中"朝向背离原点"的比例
      （这是最难的一类：靶区里的点几乎都落在它背后）。
    """
    if spec is not None:
        srcs = [MockSource(int(c), float(x), float(y), float(rr),
                           cone_half=90.0, dir_deg=float(dd))
                for (c, x, y, rr, dd) in spec]
        return MockArena(seed=int(seed), budget_s=float(budget), sources=srcs), srcs

    rng = np.random.default_rng(int(seed))
    k = int(n) if n else int(rng.integers(10, 17))
    k = max(1, min(k, 20))
    chans = rng.choice(np.arange(1, 21), size=k, replace=False)
    srcs = []
    for ch in chans:
        r = R_ARENA * math.sqrt(float(rng.random()))
        a = float(rng.uniform(0.0, 2.0 * math.pi))
        x, y = r * math.cos(a), r * math.sin(a)
        if float(rng.random()) < float(directed_frac):
            d = (math.degrees(a) % 360.0) if float(rng.random()) < float(outward_frac) \
                else float(rng.uniform(0.0, 360.0))
            srcs.append(MockSource(int(ch), x, y, float(rng.uniform(*r_recv)),
                                   cone_half=90.0, dir_deg=d))
        else:
            srcs.append(MockSource(int(ch), x, y, float(rng.uniform(*r_recv))))
    return MockArena(seed=int(seed), budget_s=float(budget), sources=srcs), srcs


def make_arena(scenario, seed, n_sources=None, budget=360000.0,
               directed_frac=0.5, r_recv=(R_RECV_MIN, R_RECV_MAX)):
    """按场景名造案例（`p4_run.py` 的入口用）。

    ``directed``：全向/定向混合；``directed_only``：全部定向；
    ``directed_edge``：源偏外圈 r ∈ [1500, 1800]（专打"贴边朝外"的弱点）；
    ``omni``：全向（作为对照，检验策略没有为定向源牺牲全向性能）。
    """
    if scenario in ('uniform','mixed_uniform','minrange'):
        return directed_case(seed,n=n_sources,directed_frac=.5 if scenario=='mixed_uniform' else 1.,
                             outward_frac=0.,budget=budget,
                             r_recv=(1000.,1000.) if scenario=='minrange' else r_recv)[0]
    if scenario == "omni":
        arena, _ = directed_case(seed, n=n_sources, directed_frac=0.0,
                                 budget=budget, r_recv=r_recv)
        return arena
    if scenario == "directed_only":
        arena, _ = directed_case(seed, n=n_sources, directed_frac=1.0,
                                 budget=budget, r_recv=r_recv)
        return arena
    if scenario == "directed_edge":
        rng = np.random.default_rng(int(seed) + 991)
        k = int(n_sources) if n_sources else int(rng.integers(10, 17))
        k = max(1, min(k, 20))
        chans = rng.choice(np.arange(1, 21), size=k, replace=False)
        srcs = []
        for ch in chans:
            r = math.sqrt(rng.uniform(1500.0 ** 2, R_ARENA ** 2))
            a = float(rng.uniform(0.0, 2.0 * math.pi))
            x, y = r * math.cos(a), r * math.sin(a)
            if float(rng.random()) < float(directed_frac):
                d = (math.degrees(a) % 360.0) if float(rng.random()) < 0.5 \
                    else float(rng.uniform(0.0, 360.0))
                srcs.append(MockSource(int(ch), x, y, float(rng.uniform(*r_recv)),
                                       cone_half=90.0, dir_deg=d))
            else:
                srcs.append(MockSource(int(ch), x, y, float(rng.uniform(*r_recv))))
        return MockArena(seed=int(seed), budget_s=float(budget), sources=srcs)
    arena, _ = directed_case(seed, n=n_sources, directed_frac=directed_frac,
                             budget=budget, r_recv=r_recv)
    return arena
