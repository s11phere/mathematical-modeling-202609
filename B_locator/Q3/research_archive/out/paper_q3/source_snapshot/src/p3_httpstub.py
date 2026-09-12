"""本地 HTTP 桩：把 `MockArena` 按官方协议暴露成 http://127.0.0.1:<port>。

用途：**不消耗任何演练/正式测试次数**，先把 `--mode live` 的整条代码路径
（HttpArena 客户端 → 串行请求 → /enter 等待 → 计时 → protocol.jsonl → summary.json）
完整跑通，再去连真模拟器。

用法（终端 A 起桩，终端 B 跑真实入口）::

    python B_locator/Q3/src/p3_httpstub.py --seed 20260913 --port 2027 --delay-open 8
    python B_locator/Q3/src/p3_run.py --mode live --url http://127.0.0.1:2027 --robot-id TEST0001 \
           --out B_locator/Q3/out/p3_preflight

与真模拟器的差异（只影响"逼真度"，不影响协议路径）：
* 源位/误差来自 `MockArena`，不是官方案例分布；
* `/enter` 的 `remaining_real_duration_s` 按 `--real-budget`（默认 1200 s）返回，
  与附件 1 的"程序运行最长 20 分钟"一致（`MockArena` 自己会返回虚拟上限 360000）；
* `--delay-open` 秒后才开始监听，用来复现"5 秒倒计时期间接口未开放、连接被拒"
  这一段的客户端重试行为。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from p3_arena import MockArena  # noqa: E402

STATE = {"arena": None, "log": None, "real_budget": 1200.0, "n": 0, "lock": threading.Lock()}


def _log(rec):
    rec["wall_ms"] = int(time.time() * 1000)
    path = STATE["log"]
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  [stub] {rec.get('path')} -> {json.dumps(rec.get('resp', {}), ensure_ascii=False)[:160]}",
          flush=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):        # 关掉默认的每请求 stderr 噪声
        return

    def _send(self, payload, code=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):                # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8") if n else "{}"
        try:
            req = json.loads(raw or "{}")
        except Exception:
            return self._send({"accepted": False, "reason": "bad_json"}, 400)
        arena = STATE["arena"]
        pos = req.get("position") or {}
        with STATE["lock"]:
            STATE["n"] += 1
            if self.path == "/enter":
                resp = dict(arena.enter())
                # 真模拟器这里给的是**现实时间**预算（附件1 4.5：最长 20 分钟）
                resp["max_real_duration_s"] = int(STATE["real_budget"])
                resp["remaining_real_duration_s"] = int(STATE["real_budget"])
            elif self.path == "/measure":
                resp = arena.measure(float(pos.get("x", 0.0)), float(pos.get("y", 0.0)),
                                     int(req.get("channel", 1)))
            elif self.path == "/clear":
                resp = arena.clear(float(pos.get("x", 0.0)), float(pos.get("y", 0.0)),
                                   int(req.get("channel", 1)))
            elif self.path == "/exit":
                resp = dict(arena.exit())
                resp.setdefault("exit_reason", "user_exit")
            else:
                resp = {"accepted": False, "reason": "not_found"}
        _log({"path": self.path, "request_id": req.get("request_id"), "req": req, "resp": resp})
        self._send(resp)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--port", type=int, default=2027)
    ap.add_argument("--delay-open", type=float, default=0.0,
                    help="秒；模拟 5 秒倒计时期间接口未开放")
    ap.add_argument("--real-budget", type=float, default=1200.0,
                    help="/enter 返回的现实时间预算（真模拟器 1200 s）")
    ap.add_argument("--log", default="")
    args = ap.parse_args()

    arena = MockArena(seed=args.seed)
    STATE["arena"] = arena
    STATE["real_budget"] = args.real_budget
    STATE["log"] = args.log
    n_src = len(arena.sources)
    n_dir = sum(1 for s in arena.sources if s.cone_half < 180.0)
    print(f"桩已就绪：seed={args.seed}  干扰源 {n_src}（全向 {n_src - n_dir}、定向 {n_dir}）"
          f"  端口 {args.port}  现实预算 {args.real_budget:.0f}s")
    print(f"veto: 这是本地桩，不是官方模拟器；案例真值仅用于写这份提示。")

    if args.delay_open > 0:
        print(f"接口 {args.delay_open:.0f} s 后才开放（复现倒计时期间连接被拒）...", flush=True)
        time.sleep(args.delay_open)

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    srv.daemon_threads = True
    print(f"监听 http://127.0.0.1:{args.port} —— 现在可以运行 p3_run.py --mode live 了", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    truth = arena.truth()
    print(f"\n结束：请求 {STATE['n']} 次；清除 {truth['n_cleared']}/{truth['n_sources']}；"
          f"虚拟时间 {arena.virtual_time_s:.1f} s；行程 {arena.stats['travel_m']:.0f} m；"
          f"检测 {arena.stats['n_measure']} 次")


if __name__ == "__main__":
    main()
