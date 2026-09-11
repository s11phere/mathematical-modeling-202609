import os
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Wedge

# 1. 参数设置
a, b = 800, 600       # P2 (a,b)
x0 = 1000             # 点 (x0, 0)
R1 = 1500             # P1 扇形半径
R2 = 1200             # P2 扇形半径
theta_deg = 2.0       # 扇形全张角 (度)

half_theta_rad = np.radians(theta_deg / 2)

# 2. 创建画布
fig, ax = plt.subplots(figsize=(10, 8), dpi=100)

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

# 6. 连接 P1 与 P2，并标注 R
ax.plot([0, a], [0, b], 'k--', linewidth=1.2, zorder=3)
ax.text(a / 2 - 30, b / 2 + 30, r'$R$', fontsize=12, color='black', fontweight='bold', zorder=6)

# 7. 保持 ABCD 位置完全不变，绘制点与标注
points_info = [
    ('A', A, -25,  20, 'right', 'bottom'),  # 左上点
    ('B', B,  25,  20, 'left',   'bottom'),  # 右上点
    ('C', C,  25, -25, 'left',   'top'),     # 右下点
    ('D', D, -25, -25, 'right',  'top')      # 左下点
]

for name, pt, off_x, off_y, ha, va in points_info:
    ax.plot(pt[0], pt[1], 'ro', markersize=2.5, zorder=5)
    ax.text(pt[0] + off_x, pt[1] + off_y, name, fontsize=11, color='red', 
            fontweight='bold', ha=ha, va=va, zorder=6)

# === 连接对角线 ===
ax.plot([B[0], D[0]], [B[1], D[1]], linewidth=2, zorder=4)

# 8. 标注 P2 与 (x0, 0)
ax.plot(a, b, 'ro', markersize=3, zorder=5)
ax.text(a + 30, b + 30, r'$P_2(a, b)$', fontsize=11, color='red', fontweight='bold')

# === 改动 1: 移动 (x0, 0) 标注，避开 DC 的遮挡 ===
ax.plot(x0, 0, 'go', markersize=3, zorder=5)
ax.text(x0 - 100, -180, r'$S (x_0, 0)$', fontsize=11, color='green', fontweight='bold', ha='left', va='top')
ax.annotate('', xy=(x0, 0), xytext=(x0 - 35, -170),
            arrowprops=dict(arrowstyle='->', color='green', lw=0.8, linestyle=':'))

# 9. 图形格式设置
ax.set_aspect('equal')
ax.set_xlim(-200, 1800)
ax.set_ylim(-400, 1000)
ax.set_xlabel('X (m)')
ax.set_ylabel('Y (m)')
ax.grid(True, linestyle=':', alpha=0.6, zorder=0)

# === 改动：导出图片到当前 .py 脚本所在目录 ===
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = os.getcwd()  # 如果在Jupyter等交互式环境中运行，退回当前工作路径

output_filename = os.path.join(script_dir, 'wedge_diagram.png')
plt.savefig(output_filename, dpi=300, bbox_inches='tight')
print(f"图片已保存至脚本目录：{output_filename}")

plt.show()