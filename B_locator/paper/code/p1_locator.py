# -*- coding: utf-8 -*-
"""B 题问题一：交会定位区域的直径与直径圆覆盖判定（论文附录源程序）。

约定：坐标单位 m，x 轴正东、y 轴正北；示向度 theta 为 x 轴正向逆时针方位角（度）；
     示向度误差界 eps（本题 eps = 1 度）。

算法步骤：
    (1) 有界性判据：有向方位角区间 Theta_i = [theta_i-eps, theta_i+eps] 求交，
        交集非空 => 区域无界，返回 "unbounded"；
    (2) 定位区域 = 各角楔（半平面）之交，在 BOX 见方的大矩形上依次裁剪得凸多边形；
    (3) 顶点规范化：对裁剪所得顶点求一次凸包（Andrew 单调链，弹出共线点），
        消除浮点重复点并得到逆时针严格凸顶点表，该步不改变区域的几何；
    (4) 直径 = 规范化后顶点集的最远点对距离；
    (5) 覆盖判定：max_{P in V} |P - M| <= D/2，M 为直径中点。
"""
import math

EPS = 1.0        # 示向度误差界（度）
BOX = 1.0e7      # 半平面裁剪初始包围盒


def rot(v, deg):
    a = math.radians(deg)
    return (v[0] * math.cos(a) - v[1] * math.sin(a),
            v[0] * math.sin(a) + v[1] * math.cos(a))


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def bearing(p, q):
    return math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 360.0


def ang_diff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def bounded(svds, eps=EPS):
    """方位角区间公共交集为空 <=> 定位区域有界。"""
    segs = [(max(0.0, (svds[0] - eps) % 360.0), min(360.0, (svds[0] + eps) % 360.0))]
    for th in svds[1:]:
        lo, hi = (th - eps) % 360.0, (th + eps) % 360.0
        parts = [(lo, hi)] if lo <= hi else [(lo, 360.0), (0.0, hi)]
        new = []
        for a, b in segs:
            for c, d in parts:
                if max(a, c) <= min(b, d) + 1e-12:
                    new.append((max(a, c), min(b, d)))
        segs = new
        if not segs:
            return True
    return False


def clip(poly, n, b):
    """保留 {x : n . x + b >= 0}。"""
    out, k = [], len(poly)
    for i in range(k):
        p, q = poly[i], poly[(i + 1) % k]
        fp = n[0] * p[0] + n[1] * p[1] + b
        fq = n[0] * q[0] + n[1] * q[1] + b
        if fp >= 0.0:
            out.append(p)
        if (fp < 0.0 < fq) or (fp > 0.0 > fq):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def region(dets, eps=EPS):
    """角楔之交：每个检测点贡献两个半平面。dets = [(x, y, theta), ...]"""
    poly = [(-BOX, -BOX), (BOX, -BOX), (BOX, BOX), (-BOX, BOX)]
    for (x, y, th) in dets:
        for s in (-1.0, 1.0):
            a = math.radians(th + s * eps)
            r = (math.cos(a), math.sin(a))        # 边界射线方向
            n = rot(r, -90.0 * s)                 # 指向楔内的法向量
            poly = clip(poly, n, -(n[0] * x + n[1] * y))
            if not poly:
                return []
    return poly


def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def hull(pts):
    """Andrew 单调链（逆时针，弹出共线中间点）。"""
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts

    def half(seq):
        st = []
        for p in seq:
            while len(st) >= 2 and cross(st[-2], st[-1], p) <= 0:
                st.pop()
            st.append(p)
        return st

    lo, hi = half(pts), half(pts[::-1])
    return lo[:-1] + hi[:-1]


def solve(dets, eps=EPS):
    """返回问题一的全部结果量。"""
    if not bounded([d[2] for d in dets], eps):
        return {"status": "unbounded"}            # 该构型不可用于定位
    V = hull(region(dets, eps))
    if len(V) < 3:
        return {"status": "degenerate", "vertices": V}
    best, (A, B) = -1.0, (V[0], V[0])             # 直径 = 最远顶点对
    for i in range(len(V)):
        for j in range(i + 1, len(V)):
            if dist(V[i], V[j]) > best:
                best, (A, B) = dist(V[i], V[j]), (V[i], V[j])
    M = ((A[0] + B[0]) / 2.0, (A[1] + B[1]) / 2.0)
    D = best
    mx = max(dist(M, p) for p in V)
    # 覆盖判定的容差随坐标量级取相对量，避免把相切构型误判为"不覆盖"
    scale = max(1.0, max(max(abs(x), abs(y)) for (x, y, _) in dets))
    return {"status": "bounded", "vertices": V, "diameter": D,
            "endpoints": (A, B), "center": M, "radius": D / 2.0,
            "max_vertex_dist": mx, "coverage": mx <= D / 2.0 + 1e-9 * scale}


if __name__ == "__main__":
    # 数据取自问题一算例 A1（6 个检测点）
    dets = [(-432.855, -596.368, 91.86), (-290.614, -501.995, 121.82),
            (474.860, -160.806, 186.02), (461.755, 349.174, 212.80),
            (-444.749, -62.142, 269.79), (-958.142, 736.087, 298.12)]
    res = solve(dets)
    if res["status"] != "bounded":
        print("status =", res["status"])
    else:
        print("vertices        :", len(res["vertices"]))
        print("diameter  D (m) : %.4f" % res["diameter"])
        print("circle radius   : %.4f" % res["radius"])
        print("max |P-M|   (m) : %.4f" % res["max_vertex_dist"])
        print("diameter circle covers the region:", res["coverage"])
