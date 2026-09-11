"""
无线电干扰源定位模型 - 5.1.2 节多检测点示向度交会定位图 (含局部放大图)
输出文件：multi_sensor_wedge_diagram.png
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle

# ==================== 全局配置 ====================
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial']  # 支持中文与中英文混排
plt.rcParams['axes.unicode_minus'] = False  # 正常显示负号


def get_output_dir():
    """获取脚本所在的路径，确保输出相对路径稳定"""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def draw_p1_multi_sensor_diagram(save_fig=True, show_fig=False):
    """绘制 5.1.2 节多检测点示向度交会定位图"""
    print("正在绘制 5.1.2 节多检测点交会凸多边形定位图...")

    # 1. 检测点与参数配置 (标记为 P1, P2, P3)
    sensors = [
        {'name': r'$P_1$', 'pos': (100, 100),   'theta': 45.0},
        {'name': r'$P_2$', 'pos': (1200, 200),  'theta': 135.0},
        {'name': r'$P_3$', 'pos': (600, -500),  'theta': 85.0}
    ]
    eps_deg = 1.0     # 误差界 \epsilon = 1°
    ray_length = 2000

    # 2. 纯几何多边形裁剪算法 (Sutherland-Hodgman)
    def clip_polygon_with_halfplane(poly, normal, point):
        if len(poly) == 0:
            return []
        def inside(p):
            return np.dot(normal, np.array(p) - np.array(point)) >= -1e-9
        def intersect(p1, p2):
            v = np.array(p2) - np.array(p1)
            t = np.dot(normal, np.array(point) - np.array(p1)) / np.dot(normal, v)
            return (np.array(p1) + t * v).tolist()

        out_poly = []
        for i in range(len(poly)):
            cur, prev = poly[i], poly[i - 1]
            if inside(cur):
                if not inside(prev):
                    out_poly.append(intersect(prev, cur))
                out_poly.append(cur)
            elif inside(prev):
                out_poly.append(intersect(prev, cur))
        return out_poly

    box_size = 5000.0
    poly = [[-box_size, -box_size], [box_size, -box_size], [box_size, box_size], [-box_size, box_size]]

    for s in sensors:
        x0, y0 = s['pos']
        th = s['theta']
        for offset, sign in zip([-eps_deg, eps_deg], [1.0, -1.0]):
            rad = np.radians(th + offset)
            r_dir = np.array([np.cos(rad), np.sin(rad)])
            n_vec = sign * np.array([-r_dir[1], r_dir[0]])
            poly = clip_polygon_with_halfplane(poly, n_vec, [x0, y0])

    vertices = np.array(poly)

    # 求解区域直径 D、圆心 M 以及质心（干扰源 S）
    max_dist = 0
    best_pair = (None, None)
    n_v = len(vertices)
    for i in range(n_v):
        for j in range(i + 1, n_v):
            d = np.linalg.norm(vertices[i] - vertices[j])
            if d > max_dist:
                max_dist = d
                best_pair = (vertices[i], vertices[j])

    A, B = best_pair
    M = (A + B) / 2.0
    radius = max_dist / 2.0
    S_source = np.mean(vertices, axis=0)

    # 3. 直线交点计算例程
    def line_intersection(p1, dir1, p2, dir2):
        x1, y1 = p1
        dx1, dy1 = dir1
        x2, y2 = p2
        dx2, dy2 = dir2
        det = dx1 * dy2 - dy1 * dx2
        if abs(det) < 1e-9:
            return None
        t1 = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / det
        return np.array([x1 + t1 * dx1, y1 + t1 * dy1])

    boundary_lines = []
    for s in sensors:
        x0, y0 = s['pos']
        th = s['theta']
        for offset in [-eps_deg, eps_deg]:
            rad = np.radians(th + offset)
            boundary_lines.append(((x0, y0), (np.cos(rad), np.sin(rad))))

    all_intersections = []
    for i in range(len(boundary_lines)):
        for j in range(i + 1, len(boundary_lines)):
            pt = line_intersection(boundary_lines[i][0], boundary_lines[i][1],
                                   boundary_lines[j][0], boundary_lines[j][1])
            if pt is not None:
                if np.linalg.norm(pt - M) < radius * 2.0:
                    if not any(np.linalg.norm(pt - existing) < 1e-3 for existing in all_intersections):
                        all_intersections.append(pt)

    # 4. 创建主画布
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    ax.axhline(0, color='black', linewidth=0.8, linestyle=':', zorder=1)
    ax.axvline(0, color='black', linewidth=0.8, linestyle=':', zorder=1)

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']

    # 绘制传感器 (P_1, P_2, P_3)、淡色角楔着色与边界线
    for i, s in enumerate(sensors):
        x0, y0 = s['pos']
        th = s['theta']
        c = colors[i % len(colors)]
        
        ax.plot(x0, y0, 'ks', markersize=6, zorder=5)
        ax.text(x0 - 40, y0 - 50, s['name'], fontsize=12, fontweight='bold', zorder=6)
        
        rad_l = np.radians(th - eps_deg)
        rad_h = np.radians(th + eps_deg)
        wedge_poly = [
            (x0, y0),
            (x0 + ray_length * np.cos(rad_l), y0 + ray_length * np.sin(rad_l)),
            (x0 + ray_length * np.cos(rad_h), y0 + ray_length * np.sin(rad_h))
        ]
        ax.add_patch(Polygon(wedge_poly, facecolor=c, alpha=0.10, zorder=1))

        for offset, style in zip([-eps_deg, 0, eps_deg], ['--', '-', '--']):
            rad = np.radians(th + offset)
            x_end = x0 + ray_length * np.cos(rad)
            y_end = y0 + ray_length * np.sin(rad)
            lw = 1.0 if offset == 0 else 0.7
            alp = 0.8 if offset == 0 else 0.4
            ax.plot([x0, x_end], [y0, y_end], color=c, linestyle=style, linewidth=lw, alpha=alp, zorder=2)

    # 主图绘制定位区域 R 与干扰源 S
    poly_patch = Polygon(vertices, facecolor='crimson', edgecolor='darkred', alpha=0.35, linewidth=1.5, zorder=3, label=r'定位区域 $\mathcal{R}$')
    ax.add_patch(poly_patch)

    ax.plot(S_source[0], S_source[1], '*', color='gold', markeredgecolor='darkred', markersize=12, zorder=7, label=r'干扰源 $S$')
    ax.text(S_source[0] + 30, S_source[1] + 30, r'干扰源 $S$', fontsize=11, color='darkred', fontweight='bold', zorder=8)

    ax.set_aspect('equal')
    ax.set_xlim(-100, 1400)
    ax.set_ylim(-600, 1000)
    ax.set_xlabel('X (m)', fontsize=11)
    ax.set_ylabel('Y (m)', fontsize=11)
    ax.set_title(r'多检测点示向度交会定位与凸多边形区域 $\mathcal{R}$ 示意图', fontsize=13, fontweight='bold', pad=12)
    ax.grid(True, linestyle=':', alpha=0.5)
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)

    # ================= 5. 右下角局部放大图 =================
    ax_inset = ax.inset_axes([0.56, 0.06, 0.40, 0.40])
    
    # 5.1 局部图：填充角楔淡颜色，只画边界虚线
    for i, s in enumerate(sensors):
        x0, y0 = s['pos']
        th = s['theta']
        c = colors[i % len(colors)]
        
        rad_l = np.radians(th - eps_deg)
        rad_h = np.radians(th + eps_deg)
        wedge_poly = [
            (x0, y0),
            (x0 + ray_length * np.cos(rad_l), y0 + ray_length * np.sin(rad_l)),
            (x0 + ray_length * np.cos(rad_h), y0 + ray_length * np.sin(rad_h))
        ]
        ax_inset.add_patch(Polygon(wedge_poly, facecolor=c, alpha=0.12, zorder=1))

        for offset in [-eps_deg, eps_deg]:
            rad = np.radians(th + offset)
            x_end = x0 + ray_length * np.cos(rad)
            y_end = y0 + ray_length * np.sin(rad)
            ax_inset.plot([x0, x_end], [y0, y_end], color=c, linestyle='--', linewidth=0.8, alpha=0.6, zorder=2)

    # 5.2 局部图：绘制区域 R 阴影
    inset_poly = Polygon(vertices, facecolor='crimson', edgecolor='darkred', alpha=0.35, linewidth=1.5, zorder=3)
    ax_inset.add_patch(inset_poly)
    
    # 5.3 局部图：极度贴近地绘制 S 和 M 标记
    # 绘制干扰源 S (向左下方贴近)
    ax_inset.plot(S_source[0], S_source[1], '*', color='gold', markeredgecolor='darkred', markersize=9, zorder=7)
    ax_inset.text(S_source[0] - 1.5, S_source[1] - 3.5, r'$S$', fontsize=9.5, color='darkred', fontweight='bold', ha='right', va='top', zorder=8)

    # 绘制圆心 M (向右上方贴近)
    ax_inset.plot(M[0], M[1], 'k+', markersize=6, markeredgewidth=1.2, zorder=6)
    ax_inset.text(M[0] + 1.5, M[1] + 1.5, r'$M$', fontsize=9.5, fontweight='bold', ha='left', va='bottom', zorder=7)

    # 5.4 局部图：精细贴近标注边界交点 V_1, V_2, ...
    for idx, pt in enumerate(all_intersections):
        ax_inset.plot(pt[0], pt[1], 'ro', markersize=3.5, zorder=6)
        
        dir_vec = pt - S_source
        norm = np.linalg.norm(dir_vec)
        dir_vec = dir_vec / norm if norm > 0 else np.array([1.0, 0.0])
        
        label_pos = pt + dir_vec * 2.5
        ha = 'left' if dir_vec[0] >= 0 else 'right'
        va = 'bottom' if dir_vec[1] >= 0 else 'top'
        
        ax_inset.text(label_pos[0], label_pos[1], f'$V_{{{idx+1}}}$', fontsize=8.5, 
                      color='darkred', fontweight='bold', ha=ha, va=va, zorder=8)

    # 5.5 局部图：绘制直径 D 与直径圆
    ax_inset.plot([A[0], B[0]], [A[1], B[1]], 'k-', linewidth=1.2, zorder=5)

    inset_circle = Circle(M, radius, fill=False, edgecolor='navy', linestyle='-.', linewidth=1.0, zorder=4)
    ax_inset.add_patch(inset_circle)

    # 5.6 设置局部放大图视口与标题
    margin = radius * 1.6
    ax_inset.set_xlim(M[0] - margin, M[0] + margin)
    ax_inset.set_ylim(M[1] - margin, M[1] + margin)
    ax_inset.set_aspect('equal')
    ax_inset.set_title('局部放大图', fontsize=9.5, fontweight='bold', pad=4)
    ax_inset.grid(True, linestyle=':', alpha=0.5)

    # 6. 保存图片
    if save_fig:
        out_path = os.path.join(get_output_dir(), 'multi_sensor_wedge_diagram.png')
        plt.savefig(out_path, dpi=300, bbox_inches='tight')
        print(f"└─ 图片已成功保存至: {out_path}")

    if show_fig:
        plt.show()
    else:
        plt.close()


if __name__ == '__main__':
    draw_p1_multi_sensor_diagram(save_fig=True, show_fig=False)