"""B 题问题 1 参考实现：交会定位区域的直径 + 直径圆覆盖判定。

输入：p1_case*.csv（det_id,x_m,y_m,svd_deg,...）
方法：每条示向度展开为 ±1° 的角锥（两个半平面），对所有半平面做凸多边形裁剪，
      得到定位区域（凸多边形）；直径用旋转卡壳 O(n)；再判定直径圆是否覆盖。
"""
import csv, json, math, os, sys
import numpy as np

BEARING_ERR = 1.0
CLIP = 1e9


def bearing(p, q):
    return math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 360.0


def ang_diff(a, b):
    """a-b 归一化到 (-180,180]"""
    return (a - b + 180.0) % 360.0 - 180.0


def clip_halfplane(poly, a, b, tol=1e-9):
    """保留 {x : a.x + b <= 0}"""
    if not poly:
        return []
    out = []
    n = len(poly)
    for i in range(n):
        P = poly[i]
        Q = poly[(i + 1) % n]
        fp = a @ P + b
        fq = a @ Q + b
        if fp <= tol:
            out.append(P)
        if (fp < -tol < fq) or (fp > tol > -fq):
            t = fp / (fp - fq)
            out.append(P + t * (Q - P))
    # 去掉重复点
    ded = []
    for v in out:
        if not ded or np.linalg.norm(v - ded[-1]) > 1e-9:
            ded.append(v)
    if len(ded) > 1 and np.linalg.norm(ded[0] - ded[-1]) < 1e-9:
        ded.pop()
    return ded


def region_from_bearings(pts, svds, err=BEARING_ERR, tol=1e-7):
    """定位区域 = 所有 ±err 示向度锥（角楔）的交集。

    角楔的边界是 2k 条直线（射线所在直线），交集凸多边形 → 顶点必落在
    两条边界线的交点上。故枚举 O((2k)^2) 个交点，再用"到每条示向度的角差
    都在 ±err 内"筛出可行顶点，最后取凸包。
    这样避免了半平面裁剪的数值退化，且天然给出有界性判据。
    """
    k = len(pts)
    if k == 0:
        return np.zeros((0, 2)), "empty"
    lines = []
    for p, th in zip(pts, svds):
        for s in (-1.0, 1.0):
            a = math.radians((th + s * err) % 360.0)
            lines.append((np.array(p, float), np.array([math.cos(a), math.sin(a)])))
    cand = []
    for i in range(len(lines)):
        A, dA = lines[i]
        for j in range(i + 1, len(lines)):
            B, dB = lines[j]
            det = dA[0] * (-dB[1]) - (-dB[0]) * dA[1]
            if abs(det) < 1e-12:
                continue
            rhs = B - A
            t = (rhs[0] * (-dB[1]) - (-dB[0]) * rhs[1]) / det
            X = A + t * dA
            if not np.all(np.isfinite(X)):
                continue
            good = True
            for p, th in zip(pts, svds):
                d = math.hypot(X[0] - p[0], X[1] - p[1])
                if d < 1e-9:
                    good = False; break
                if abs(ang_diff(bearing(p, X), th)) > err + tol:
                    good = False; break
            if good:
                cand.append(X)
    if len(cand) == 0:
        return np.zeros((0, 2)), "empty"
    # 去重 + 凸包
    P = np.array(cand)
    order = np.lexsort((P[:, 1], P[:, 0]))
    P = P[order]
    ded = [P[0]]
    for v in P[1:]:
        if np.linalg.norm(v - ded[-1]) > 1e-7:
            ded.append(v)
    P = np.array(ded)
    if len(P) < 3:
        return P, "degenerate"
    hull = convex_hull(P)
    return hull, "bounded"


def convex_hull(P):
    """Andrew monotone chain，逆时针"""
    def half(pts):
        st = []
        for p in pts:
            while len(st) >= 2 and _cross2(st[-1] - st[-2], p - st[-2]) <= 0:
                st.pop()
            st.append(p)
        return st
    P = P[np.lexsort((P[:, 1], P[:, 0]))]
    lo = half(P); hi = half(P[::-1])
    return np.array(lo[:-1] + hi[:-1])


def _cross2(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


def diameter(P):
    """凸多边形直径。

    定位区域的顶点数至多 2k（k 为示向度个数，k ≤ 20），故直接 O(n^2) 枚举
    最远点对，数值上最稳健；仅当 n 很大（>400）时才退回旋转卡壳。
    """
    n = len(P)
    if n == 0:
        return 0.0, None
    if n == 1:
        return 0.0, (P[0], P[0])
    if n == 2:
        return float(np.linalg.norm(P[0] - P[1])), (P[0], P[1])
    best = -1.0; bestpair = (P[0], P[1])
    for i in range(n):
        if i + 1 >= n:
            break
        d = np.linalg.norm(P[i + 1:] - P[i], axis=1)
        k = int(np.argmax(d))
        if d[k] > best:
            best = float(d[k]); bestpair = (P[i], P[i + 1 + k])
    return best, bestpair


def analyse(pts, svds):
    P, status = region_from_bearings(pts, svds)
    if len(P) == 0:
        return {"status": "empty",
                "reason": "所有示向度锥无公共交集（数据不一致或误差超界）"}
    if len(P) < 3:
        return {"status": "degenerate",
                "reason": "公共交集退化为线段或点（示向度接近共点/近平行）",
                "vertices": [[round(float(v[0]), 4), round(float(v[1]), 4)] for v in P]}
    D, (A, B) = diameter(P)
    c = 0.5 * (A + B)
    maxr = float(max(np.linalg.norm(v - c) for v in P))
    return {"status": status,
            "n_vertices": int(len(P)),
            "vertices": [[round(float(v[0]), 4), round(float(v[1]), 4)] for v in P],
            "diameter_m": round(D, 4),
            "diameter_endpoints": [[round(float(A[0]), 4), round(float(A[1]), 4)],
                                   [round(float(B[0]), 4), round(float(B[1]), 4)]],
            "circle_center": [round(float(c[0]), 4), round(float(c[1]), 4)],
            "circle_radius_m": round(D / 2.0, 4),
            "max_vertex_dist_m": round(maxr, 4),
            "diameter_circle_covers": bool(maxr <= D / 2.0 + 1e-9),
            "area_m2": round(abs(0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1)
                                                    - np.roll(P[:, 0], -1) * P[:, 1]))), 4)}


def run_case_csv(path, truth_path=None):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    pts = [(float(r["x_m"]), float(r["y_m"])) for r in rows]
    svds = [float(r["svd_deg"]) for r in rows]
    res = analyse(pts, svds)
    res["n_bearings"] = len(rows)
    if truth_path and os.path.exists(truth_path):
        truth = json.load(open(truth_path, encoding="utf-8"))
        G = truth["source_xy"]
        res["truth_xy"] = G
        if "circle_center" in res:
            res["center_error_vs_truth_m"] = round(math.dist(res["circle_center"], G), 3)
        if "vertices" in res and len(res["vertices"]) >= 3:
            inside = all(
                abs(ang_diff(bearing(p, G), th)) <= BEARING_ERR + 1e-6
                for p, th in zip(pts, svds))
            res["truth_inside_region"] = bool(inside)
    return res


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "data")
    out = []
    for fn in sorted(os.listdir(d)):
        if not (fn.startswith("p1_case") and fn.endswith(".csv")):
            continue
        res = run_case_csv(os.path.join(d, fn),
                           os.path.join(d, fn.replace(".csv", ".truth.json")))
        res["case"] = fn
        out.append(res)
    # 统一落盘（避免 PowerShell 重定向写成 UTF-16）
    jl = os.path.join(d, "p1_results.jsonl")
    with open(jl, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    bounded = [r for r in out if r["status"] == "bounded"]
    summary = {
        "n_cases": len(out),
        "n_bounded": len(bounded),
        "diameter_m_range": [min((r["diameter_m"] for r in bounded), default=None),
                             max((r["diameter_m"] for r in bounded), default=None)],
        "n_diameter_circle_misses": sum(1 for r in bounded
                                        if not r["diameter_circle_covers"]),
        "n_truth_inside_region": sum(1 for r in bounded
                                     if r.get("truth_inside_region")),
    }
    with open(os.path.join(d, "p1_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    for r in out:
        print("%-16s %-9s D=%8.3f m  cover=%-5s n=%d  center_err=%s"
              % (r["case"], r["status"], r.get("diameter_m", -1),
                 r.get("diameter_circle_covers"), r.get("n_bearings"),
                 r.get("center_error_vs_truth_m")))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
