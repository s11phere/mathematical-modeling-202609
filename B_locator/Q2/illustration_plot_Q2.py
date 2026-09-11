"""
无线电干扰源定位模型 - Q2 双测点楔形区域几何分析图 (含右上角局部放大图)
输出文件：wedge_diagram.png
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, Polygon

# ==================== 全局配置 ====================
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial']  # 支持中文与中英文混排
plt.rcParams['axes.unicode_minus'] = False  # 正常显示负号


def get_output_dir():
    """获取脚本所在的路径，确保输出相对路径稳定"""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def draw_q2_wedge_diagram(save_fig=True, show_fig=False):
    """绘制问题二/理论近似分析中的双测点楔形交会几何图（右上角含局部放大图）"""
    print("正在绘制 Q2 双测点楔形区域几何分析图(含局部放大)...")
    
    # 1. 参数设置
    a, b = 800, 600       # P2 (a,b)
    x0 = 1000             # 点 (x0, 0)
    R1 = 1500             # P1 扇形半径
    R2 = 1200             # P2 扇形半径
    theta_deg = 2.0       # 扇形全张角 (度)

    half_theta_rad = np.radians(theta_deg / 2)

    # 2. 创建画布
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)

    # 3. 绘制坐标轴与 P1
    ax.axhline(0, color='black', linewidth=1.2, zorder=0)
    ax.axvline(0, color='black', linewidth=1.2, zorder=0)
    ax.plot(0, 0, 'ko', markersize=3, zorder=5)
    ax.text(-50, -50, r'$P_1(0,0)$', fontsize=11, fontweight='bold', va='top', ha='right')

    # P2 的中心方向角
    dx, dy = x0 - a, 0 - b
    p2_center_angle_rad = np.arctan2(dy, dx)
    p2_center_angle_deg = np.degrees(p2_center_angle_rad)

    # 4. 绘制两个扇形
    wedge1 = Wedge(center=(0, 0), r=R1, theta1=-theta_deg/2, theta2=theta_deg/2,
                   facecolor='lightblue', edgecolor='blue', alpha=0.3, zorder=1)
    wedge2 = Wedge(center=(a, b), r=R2, 
                   theta1=p2_center_angle_deg - theta_deg/2, 
                   theta2=p2_center_angle_deg + theta_deg/2,
                   facecolor='moccasin', edgecolor='orange', alpha=0.3, zorder=1)
    ax.add_patch(wedge1)
    ax.add_patch(wedge2)

    # 5. 纯解析几何方法求解交点
    def line_intersection(p1, angle1, p2, angle2):
        x1, y1 = p1
        x2, y2 = p2
        k1 = np.tan(angle1)
        k2 = np.tan(angle2)
        x_int = (y2 - y1 + k1 * x1 - k2 * x2) / (k1 - k2)
        y_int = y1 + k1 * (x_int - x1)
        return x_int, y_int

    # P1 与 P2 的两条射线角度
    phi1_u, phi1_l = half_theta_rad, -half_theta_rad
    phi2_u = p2_center_angle_rad + half_theta_rad
    phi2_l = p2_center_angle_rad - half_theta_rad

    # 计算四个交点顶点
    A = line_intersection((0,0), phi1_u, (a,b), phi2_u) # 上 - 上
    B = line_intersection((0,0), phi1_u, (a,b), phi2_l) # 上 - 下
    C = line_intersection((0,0), phi1_l, (a,b), phi2_l) # 下 - 下
    D = line_intersection((0,0), phi1_l, (a,b), phi2_u) # 下 - 上

    # 6. 主图：连接 P1 与 P2，并标注 R
    ax.plot([0, a], [0, b], 'k--', linewidth=1.2, zorder=3)
    ax.text(a / 2 - 30, b / 2 + 30, r'$R$', fontsize=12, color='black', fontweight='bold', zorder=6)

    # 主图：只在主图画 ABCD 点（字母标注交由局部放大图显示）
    for pt in [A, B, C, D]:
        ax.plot(pt[0], pt[1], 'ro', markersize=2.5, zorder=5)

    # 主图：连接对角线 BD
    ax.plot([B[0], D[0]], [B[1], D[1]], linewidth=2, zorder=4)

    # 7. 主图：标注 P2 与干扰源 S
    ax.plot(a, b, 'ro', markersize=3, zorder=5)
    ax.text(a + 30, b + 30, r'$P_2(a, b)$', fontsize=11, color='red', fontweight='bold')

    ax.plot(x0, 0, 'go', markersize=3, zorder=5)
    ax.text(x0 - 100, -180, r'$S (x_0, 0)$', fontsize=11, color='green', fontweight='bold', ha='left', va='top')
    ax.annotate('', xy=(x0, 0), xytext=(x0 - 35, -170),
                arrowprops=dict(arrowstyle='->', color='green', lw=0.8, linestyle=':'))

    # 主图格式设置
    ax.set_aspect('equal')
    ax.set_xlim(-200, 1800)
    ax.set_ylim(-400, 1000)
    ax.set_xlabel('X (m)', fontsize=11)
    ax.set_ylabel('Y (m)', fontsize=11)
    ax.set_title(r'双测点示向度楔形交会几何分析示意图', fontsize=13, fontweight='bold', pad=12)
    ax.grid(True, linestyle=':', alpha=0.6, zorder=0)

    # ================= 8. 右上角局部放大图 =================
    # 配置右上方视口位置 [x, y, width, height]
    ax_inset = ax.inset_axes([0.58, 0.58, 0.38, 0.38])

    # 8.1 在局部图中绘制填充的扇形/角楔边界 (不画中心线)
    inset_wedge1 = Wedge(center=(0, 0), r=R1, theta1=-theta_deg/2, theta2=theta_deg/2,
                         facecolor='lightblue', edgecolor='blue', linestyle='--', linewidth=0.8, alpha=0.35, zorder=1)
    inset_wedge2 = Wedge(center=(a, b), r=R2, 
                         theta1=p2_center_angle_deg - theta_deg/2, 
                         theta2=p2_center_angle_deg + theta_deg/2,
                         facecolor='moccasin', edgecolor='orange', linestyle='--', linewidth=0.8, alpha=0.35, zorder=1)
    ax_inset.add_patch(inset_wedge1)
    ax_inset.add_patch(inset_wedge2)

    # 8.2 局部图绘制交会四边形 ABCD 与对角线
    quad_poly = Polygon([A, B, C, D], facecolor='crimson', edgecolor='darkred', alpha=0.25, linewidth=1.2, zorder=2)
    ax_inset.add_patch(quad_poly)
    ax_inset.plot([B[0], D[0]], [B[1], D[1]], 'k-', linewidth=1.2, zorder=3)

    # 8.3 局部图绘制并精准贴近标注顶点 A, B, C, D
    pts_labels = [
        ('A', A, -4,  4, 'right', 'bottom'),
        ('B', B,  4,  4, 'left',   'bottom'),
        ('C', C,  4, -4, 'left',   'top'),
        ('D', D, -4, -4, 'right',  'top')
    ]
    for name, pt, off_x, off_y, ha, va in pts_labels:
        ax_inset.plot(pt[0], pt[1], 'ro', markersize=3.5, zorder=5)
        ax_inset.text(pt[0] + off_x, pt[1] + off_y, name, fontsize=9.5, color='red',
                      fontweight='bold', ha=ha, va=va, zorder=6)

    # 8.4 局部图绘制干扰源 S
    ax_inset.plot(x0, 0, 'go', markersize=4, zorder=5)
    ax_inset.text(x0 + 4, -4, r'$S$', fontsize=9.5, color='green', fontweight='bold', ha='left', va='top', zorder=6)

    # 8.5 计算中心与视角范围
    center_x = (A[0] + B[0] + C[0] + D[0]) / 4.0
    center_y = (A[1] + B[1] + C[1] + D[1]) / 4.0
    margin = 80.0

    ax_inset.set_xlim(center_x - margin, center_x + margin)
    ax_inset.set_ylim(center_y - margin, center_y + margin)
    ax_inset.set_aspect('equal')
    ax_inset.set_title('局部放大图', fontsize=9.5, fontweight='bold', pad=4)
    ax_inset.grid(True, linestyle=':', alpha=0.5)

    # 9. 保存图片
    if save_fig:
        out_path = os.path.join(get_output_dir(), 'wedge_diagram.png')
        plt.savefig(out_path, dpi=300, bbox_inches='tight')
        print(f"└─ 图片已成功保存至: {out_path}")

    if show_fig:
        plt.show()
    else:
        plt.close()


if __name__ == '__main__':
    draw_q2_wedge_diagram(save_fig=True, show_fig=False)