"""问题 4 的本地模拟测试入口：把问题 4 案例按官方协议挂到 http://127.0.0.1:<port>。

**目的**：在连官方模拟器之前，用真实 `--mode live` 入口把整条在线代码路径跑一遍，
**不消耗任何演练/正式测试次数**（演练不限次，但正式每问题只有 3 次，且"中止"也占一次）。

和 `p3_httpstub.py` 是同一个桩（共用 `serve()`），区别只在于案例怎么造：
这里用 `p4_arena_ext.make_arena`，所以**含定向源**（覆盖半角 90°、朝向可任意），
与问题 4 的口径一致。

用法（终端 A 起桩，终端 B 跑真实入口）::

    python B_locator/Q4/src/p4_httpstub.py --scenario directed --seed 20260914 --port 2028 --delay-open 6
    python B_locator/Q4/src/p4_run.py --mode live --url http://127.0.0.1:2028 --robot-id TEST0001 \
           --out B_locator/Q4/out/p4_preflight

默认策略就是当前最优：`--policy compact --tier strict`（21 站严格布局，100% 档）。
要对照可以显式写 `--policy joint`（上一版）或 `--policy grid`（原始策略）。

与真模拟器的差异（只影响逼真度，不影响协议路径）：
* 源位/朝向/接收半径由本地生成器给出，不等于官方案例分布；
* `/enter` 的 `remaining_real_duration_s` 按 `--real-budget`（默认 1200 s）返回，
  与附件 1 的"程序运行最长 20 分钟"一致；
* `--delay-open` 秒后才监听，用来复现"5 秒倒计时期间接口未开放、连接被拒"的重试行为。
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from p3_httpstub import serve  # noqa: E402
from p4_arena_ext import SCENARIOS, make_arena  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="directed", choices=list(SCENARIOS),
                    help="directed=全向/定向混合（默认）| directed_only=全定向 | "
                         "directed_edge=贴边朝外 | omni=全向 | uniform=全定向随机朝向 | "
                         "mixed_uniform=混合 | minrange=接收半径全 1000 m")
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--port", type=int, default=2028,
                    help="默认 2028，避开问题 3 桩的 2027 与官方模拟器的 2026")
    ap.add_argument("--n-sources", type=int, default=0, help="0 = 随机 10–16 个")
    ap.add_argument("--directed-frac", type=float, default=0.5)
    ap.add_argument("--delay-open", type=float, default=0.0,
                    help="秒；模拟 5 秒倒计时期间接口未开放")
    ap.add_argument("--real-budget", type=float, default=1200.0)
    ap.add_argument("--every", type=int, default=25,
                    help="每 N 个请求打印一行（问题 4 请求多，默认 25）")
    ap.add_argument("--log", default="")
    args = ap.parse_args()

    arena = make_arena(args.scenario, args.seed,
                       n_sources=(args.n_sources or None),
                       directed_frac=args.directed_frac)
    srcs = arena.sources
    n_dir = sum(1 for s in srcs if s.cone_half < 180.0)
    print(f"问题 4 桩已就绪：scenario={args.scenario}  seed={args.seed}  "
          f"干扰源 {len(srcs)}（全向 {len(srcs) - n_dir}、定向 {n_dir}）  "
          f"端口 {args.port}  现实预算 {args.real_budget:.0f}s")
    print("提示：这是本地桩，不是官方模拟器；演练界面上的案例真值在这里只用于提示。")
    print("      默认策略 compact/strict（21 站，100% 档）；正式测试前请用本桩验通 live 路径。")
    serve(arena, port=args.port, real_budget=args.real_budget, log=args.log,
          delay_open=args.delay_open, every=args.every,
          open_hint="现在可以运行 p4_run.py --mode live 了")


if __name__ == "__main__":
    main()
