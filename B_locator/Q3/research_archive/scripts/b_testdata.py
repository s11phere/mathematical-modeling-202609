"""B 题问题 1 / 问题 2 自测数据生成器。

题目**没有**给出问题 1、2 的任何数据（附件 1、附件 2 只讲问题 3、4 的模拟器）。
因此这两个问题的算例必须自行构造。本脚本按题目正文与附录给出的全部约定生成算例，
并同时输出「带误差的观测数据」（选手算法看到的）与「真值」（仅用于自检评分）。

约定来源：
  题目正文附录 1、附录 2；模拟器通信接口说明「1.1 目标区域与坐标系」「1.2 角度约定」
  坐标：米，(0,0) 为半径 1800 m 圆域中心，x 轴正东、y 轴正北
  示向度：x 轴正向逆时针为正，[0,360)，单位度，保留两位小数，误差范围 [-1°, 1°]
  有效接收半径：1000~1500 m（逐干扰源不同）
  频道：1..20 的整数，每个频道最多一个干扰源
  定向干扰源：覆盖角度 = 定向方向两侧各 90°（含边界）；全向为 360°

输出（UTF-8 CSV + JSON）：
  p1_<case>.csv    问题 1 算例：det_id,x_m,y_m,svd_deg,true_svd_deg,true_az_err_deg
  p1_<case>.truth.json
  p2_scan_<case>.csv 问题 2/3 自测扫描：robot_x_m,robot_y_m,channel,measure_result,svd_deg
  p2_case_<case>.json 案例真值：全部干扰源

用法：
  python b_testdata.py --out ../data --seed 20260901
"""
from __future__ import annotations
import argparse, csv, json, math, os
import numpy as np

R_ARENA = 1800.0
CHANNELS = list(range(1, 21))
BEARING_ERR = 1.0                 # 度，[-1,1]
R_RECV_MIN, R_RECV_MAX = 1000.0, 1500.0
NEAR_R = 5.0
CLEAR_R = 20.0
DIR_HALF = 90.0                   # 定向覆盖半角


def wrap360(a):
    return a % 360.0


def bearing(p, q):
    """p 处指向 q 的方位角（度，[0,360)）"""
    return wrap360(math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])))


def ang_diff(a, b):
    """a-b 归一化到 (-180,180]"""
    return (a - b + 180.0) % 360.0 - 180.0


def in_cone(src, p, half_deg):
    """点 p 是否落在以 src 为顶点、沿定向方向的 ±half_deg 锥内（全向 half=180）"""
    if half_deg >= 180.0:
        return True
    return abs(ang_diff(bearing(src["xy"], p), src["dir_deg"])) <= half_deg + 1e-12


def measure(src, p):
    """按附录规则返回一个检测结果（不含示向度误差，误差在调用处加）"""
    d = math.dist(p, src["xy"])
    if d > src["r_recv"]:
        return "no_signal", None
    if not in_cone(src, p, src["cone_half"]):
        return "no_signal", None
    if d <= NEAR_R:
        return "near", None
    return "direction", bearing(p, src["xy"])   # 由检测点指向干扰源


# --------------------------------------------------------------------------
# 问题 1：单个干扰源 + 若干检测点（检测点已知、示向度已知）
# --------------------------------------------------------------------------
def make_case_p1(rng, n_pts=3, n_extra=2, min_az_gap=25.0, min_dist=150.0,
                 max_dist=1300.0, spread=140.0):
    """返回 (观测记录, 真值)。

    检测点需"良态"：分布在干扰源四周一定的方位张角内，否则示向度锥近似平行，
    交集会退化成细长/无界区域。这里强制最小方位间隔与最小距离。
    """
    ang = rng.uniform(0, 2 * math.pi)
    rad = rng.uniform(50, 0.75 * R_ARENA)
    G = (rad * math.cos(ang), rad * math.sin(ang))
    src = {"xy": G, "r_recv": rng.uniform(R_RECV_MIN, R_RECV_MAX),
           "cone_half": 180.0, "dir_deg": None}

    n = max(2, n_pts)
    base = rng.uniform(0, 360)
    # 在 [base-spread, base+spread] 内均匀铺开方位，间隔 >= min_az_gap
    span = 2 * spread
    while n * min_az_gap > span:
        min_az_gap *= 0.85
    offs = np.sort(rng.uniform(-spread, spread, size=n))
    for _ in range(200):
        gaps = np.diff(offs)
        if len(gaps) == 0 or gaps.min() >= min_az_gap:
            break
        offs = np.sort(rng.uniform(-spread, spread, size=n))

    pts, azs = [], []
    for o in offs:
        a = math.radians((base + o) % 360.0)
        for _try in range(80):
            d = rng.uniform(min_dist, min(max_dist, src["r_recv"]))
            p = (G[0] + d * math.cos(a), G[1] + d * math.sin(a))
            if math.hypot(*p) <= R_ARENA:
                pts.append(p); azs.append(bearing(p, G))
                break
    if len(pts) < 2:
        return [], {"error": "failed to build well-conditioned case"}

    errs = rng.uniform(-BEARING_ERR, BEARING_ERR, size=len(pts))
    rows = []
    for i, (p, e) in enumerate(zip(pts, errs), start=1):
        res, svd = measure(src, p)
        if res != "direction":
            continue
        rows.append({
            "det_id": i,
            "x_m": round(p[0], 3),
            "y_m": round(p[1], 3),
            "svd_deg": round(wrap360(svd + e), 2),
            "true_svd_deg": round(svd, 4),
            "true_az_err_deg": round(e, 4),
            "dist_m": round(math.dist(p, G), 3),
        })
    truth = {"source_xy": [round(G[0], 3), round(G[1], 3)],
             "r_recv_m": round(src["r_recv"], 3),
             "type": "omnidirectional", "dir_deg": None,
             "bearing_error_bound_deg": BEARING_ERR,
             "azimuth_span_deg": round(float(max(azs) - min(azs)), 2),
             "min_azimuth_gap_deg": round(float(np.min(np.diff(np.sort(azs)))), 2)
             if len(azs) > 1 else None,
             "n_detection_points": len(rows)}
    return rows, truth


# --------------------------------------------------------------------------
# 问题 2：已知一个检测点的示向度，求第二个检测点
# --------------------------------------------------------------------------
def make_case_p2(rng):
    """给出第一个检测点、其示向度（含误差）与各种候选第二点的可达性网格。"""
    ang = rng.uniform(0, 2 * math.pi)
    G = (rng.uniform(300, 1200) * math.cos(ang), rng.uniform(300, 1200) * math.sin(ang))
    src = {"xy": G, "r_recv": rng.uniform(R_RECV_MIN, R_RECV_MAX),
           "cone_half": 180.0, "dir_deg": None}
    S1 = (rng.uniform(-1200, 1200), rng.uniform(-1200, 1200))
    while math.dist(S1, G) > src["r_recv"] or math.dist(S1, G) < 100:
        S1 = (rng.uniform(-1500, 1500), rng.uniform(-1500, 1500))
    e1 = rng.uniform(-BEARING_ERR, BEARING_ERR)
    res1, svd1 = measure(src, S1)
    truth = {"source_xy": [round(G[0], 3), round(G[1], 3)],
             "r_recv_m": round(src["r_recv"], 3)}
    first = {"det_id": 1, "x_m": round(S1[0], 3), "y_m": round(S1[1], 3),
             "svd_deg": round(wrap360(svd1 + e1), 2), "true_svd_deg": round(svd1, 4)}
    return truth, first


# --------------------------------------------------------------------------
# 问题 3/4 自测：满场干扰源 + 一条扫描轨迹
# --------------------------------------------------------------------------
def make_case_p3(rng, n_src=None, n_directed=0, track="grid", step=400.0):
    n_src = n_src or int(rng.integers(10, 17))
    n_directed = min(n_directed, n_src)
    chans = rng.choice(CHANNELS, size=n_src, replace=False)
    srcs = []
    for i in range(n_src):
        while True:
            p = (rng.uniform(-R_ARENA, R_ARENA), rng.uniform(-R_ARENA, R_ARENA))
            if math.hypot(*p) <= R_ARENA:
                break
        directed = i < n_directed
        srcs.append({
            "channel": int(chans[i]),
            "xy": p,
            "r_recv": rng.uniform(R_RECV_MIN, R_RECV_MAX),
            "type": "directional" if directed else "omnidirectional",
            "dir_deg": round(rng.uniform(0, 360), 2) if directed else None,
            "cone_half": DIR_HALF if directed else 180.0,
        })
    # 扫描轨迹（默认方形栅格，覆盖圆域）
    pts = []
    if track == "grid":
        xs = np.arange(-R_ARENA, R_ARENA + 1e-9, step)
        for k, x in enumerate(xs):
            ys = np.arange(-R_ARENA, R_ARENA + 1e-9, step)
            if k % 2:
                ys = ys[::-1]
            for y in ys:
                if math.hypot(x, y) <= R_ARENA:
                    pts.append((float(x), float(y)))
    elif track == "spiral":
        for th in np.arange(0, 40 * math.pi, 0.15):
            r = 60.0 * th
            if r > R_ARENA:
                break
            pts.append((r * math.cos(th), r * math.sin(th)))

    rows = []
    for (x, y) in pts:
        for s in srcs:
            res, svd = measure(s, (x, y))
            if res == "no_signal":
                continue
            e = rng.uniform(-BEARING_ERR, BEARING_ERR)
            rows.append({
                "robot_x_m": round(x, 3), "robot_y_m": round(y, 3),
                "channel": s["channel"], "measure_result": res,
                "svd_deg": "" if svd is None else round(wrap360(svd + e), 2),
            })
    truth = {"n_sources": n_src,
             "n_directional": n_directed,
             "sources": [{"channel": s["channel"],
                          "x_m": round(s["xy"][0], 3), "y_m": round(s["xy"][1], 3),
                          "r_recv_m": round(s["r_recv"], 3),
                          "type": s["type"], "dir_deg": s["dir_deg"]} for s in srcs]}
    return rows, truth


def write_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--n-p1", type=int, default=5)
    ap.add_argument("--n-p3", type=int, default=3)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    out = os.path.abspath(args.out)
    manifest = {"seed": args.seed, "arena_radius_m": R_ARENA,
                "bearing_error_bound_deg": BEARING_ERR,
                "r_recv_range_m": [R_RECV_MIN, R_RECV_MAX],
                "channels": [1, 20], "files": []}

    for k in range(args.n_p1):
        rows, truth = make_case_p1(rng, n_pts=int(rng.integers(3, 7)))
        name = "p1_case%02d" % (k + 1)
        write_csv(os.path.join(out, name + ".csv"), rows,
                  ["det_id", "x_m", "y_m", "svd_deg", "true_svd_deg",
                   "true_az_err_deg", "dist_m"])
        with open(os.path.join(out, name + ".truth.json"), "w", encoding="utf-8") as f:
            json.dump(truth, f, ensure_ascii=False, indent=2)
        manifest["files"] += [name + ".csv", name + ".truth.json"]

    for k in range(3):
        t, s1 = make_case_p2(rng)
        name = "p2_case%02d" % (k + 1)
        with open(os.path.join(out, name + ".truth.json"), "w", encoding="utf-8") as f:
            json.dump({"source": t, "first_detection": s1}, f,
                      ensure_ascii=False, indent=2)
        manifest["files"].append(name + ".truth.json")

    for k in range(args.n_p3):
        rows, truth = make_case_p3(rng, n_directed=0)
        name = "p3_scan%02d" % (k + 1)
        write_csv(os.path.join(out, name + ".csv"), rows,
                  ["robot_x_m", "robot_y_m", "channel", "measure_result", "svd_deg"])
        with open(os.path.join(out, name + ".truth.json"), "w", encoding="utf-8") as f:
            json.dump(truth, f, ensure_ascii=False, indent=2)
        manifest["files"] += [name + ".csv", name + ".truth.json"]

    rows, truth = make_case_p3(rng, n_directed=4)
    write_csv(os.path.join(out, "p4_scan01.csv"), rows,
              ["robot_x_m", "robot_y_m", "channel", "measure_result", "svd_deg"])
    with open(os.path.join(out, "p4_scan01.truth.json"), "w", encoding="utf-8") as f:
        json.dump(truth, f, ensure_ascii=False, indent=2)
    manifest["files"] += ["p4_scan01.csv", "p4_scan01.truth.json"]

    with open(os.path.join(out, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("wrote %d files to %s" % (len(manifest["files"]) + 1, out))

    # 顺带打印 p1_case01 供人工核对
    with open(os.path.join(out, "p1_case01.csv"), encoding="utf-8") as f:
        print("\n--- p1_case01.csv ---")
        print(f.read())


if __name__ == "__main__":
    main()
