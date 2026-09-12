"""B 题问题 3：统一自检入口（决策场 + 接口层 + 在线策略）。

    python src/p3_selftest.py            # 全部自检，输出到 review/out_p3_selftest.txt
    python src/p3_selftest.py --quick    # 跳过端到端演练（只做结构与几何检查）

三层自检
--------
* T1–T7 决策场：刚体不变性 / 双线性插值 / 未覆盖取最大值 / 归一化与距离层 /
        与"精确期望"交叉验证 / 为什么必须按先验外径 t_hi 分族（反例）
* A1–A8 接口层：附件 1 表 2 的计时算例 / 切换频道规则 / 三种检测结果 / 20 m 清除半径 /
        同一源只清一次 / 误差界与"同一地点误差固定" / 超时拒动
* S1–S6 在线策略：覆盖式试探的完备性 / 端到端演练（含清除率与平均时间）/
        预算内收工 / 已清除频道不再检测 / 定位区域包含真源 / 探索兜底
* C1–C3 覆盖扫圈（`p3_sweep.py`）：一圈格点覆盖环带 / 原点+一圈覆盖全靶区 / 选点只挑未覆盖站
* T1–T6 统一航路（`p3_tour.py`）：环带未排除判据 / 骨架可覆盖 / 骨架角向单调（不折返）/
        端到端 / 完工判据与真值一致 / 行程相对"结构下界"的倍数
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Windows 控制台默认 GBK：自检文本里有 ⇒ 等 GBK 无法编码的符号，`main()` 的
# `print(text)` 会先抛 UnicodeEncodeError —— 而写文件在 print **之后**，于是连
# review/out_p3_selftest.txt 都写不出来。与 src/p3_run.py 保持同一处理：
# 统一 UTF-8 输出，并且永不因为编码问题中断。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import p3_arena  # noqa: E402
import p3_expect_field  # noqa: E402
import p3_robot  # noqa: E402


def run_all(quick=False, verbose=True):
    t0 = time.time()
    blocks = []
    res_field = p3_expect_field.selfcheck(verbose=verbose)
    blocks.append(("决策场 p3_expect_field", res_field))
    if verbose:
        print()
    res_arena = p3_arena.selfcheck(verbose=verbose)
    blocks.append(("接口层 p3_arena", res_arena))
    if verbose:
        print()
    if quick:
        res_robot = {"ok": True, "checks": [], "skipped": "quick 模式跳过端到端演练"}
    else:
        res_robot = p3_robot.selfcheck_mock(verbose=verbose, cases=3)
    blocks.append(("在线策略 p3_robot", res_robot))
    if verbose:
        print()
    import p3_sweep
    res_sweep = p3_sweep.selfcheck(verbose=verbose)
    blocks.append(("覆盖扫圈 p3_sweep", res_sweep))
    if verbose:
        print()
    import p3_tour
    res_tour = p3_tour.selfcheck(verbose=verbose, cases=(1 if quick else 3))
    blocks.append(("统一航路 p3_tour", res_tour))

    ok = all(b["ok"] for _n, b in blocks)
    n_ok = sum(1 for _n, b in blocks for c in b["checks"] if c["ok"])
    n_all = sum(len(b["checks"]) for _n, b in blocks)
    if verbose:
        print(f"\n===== 问题3 自检总览 =====")
        for name, b in blocks:
            print(f"  {name:28s} {'通过' if b['ok'] else '失败'}"
                  f"  ({sum(1 for c in b['checks'] if c['ok'])}/{len(b['checks'])})")
        print(f"  合计 {n_ok}/{n_all} 项；耗时 {time.time() - t0:.1f} s")
    return {"ok": ok, "n_ok": n_ok, "n_all": n_all,
            "seconds": round(time.time() - t0, 2),
            "blocks": [{"name": n, **b} for n, b in blocks]}


def main():
    ap = argparse.ArgumentParser(description="问题3 自检")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=os.path.normpath(
        os.path.join(_HERE, "..", "review", "out_p3_selftest.txt")))
    args = ap.parse_args()
    import io
    buf = io.StringIO()
    old = sys.stdout
    try:
        sys.stdout = buf
        res = run_all(quick=args.quick, verbose=True)
    finally:
        sys.stdout = old
    text = buf.getvalue()
    print(text)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
            f.write("\n" + json.dumps({"ok": res["ok"], "n_ok": res["n_ok"],
                                       "n_all": res["n_all"]}, ensure_ascii=False) + "\n")
        print(f"\n已写入 {args.out}")
    except OSError as e:
        print(f"\n（写文件失败：{e}）")
    raise SystemExit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
