# 核心指标

在Q2中我们需要的关键**衡量指标**是在第一个探测器P1扫描结果确定的情况下，摆放P2探测后获得**探测域直径的期望**

# 模型建立

- 将第一个探测器$P_1$置于原点，探测得到方位指定为x轴正方向建立平面直角坐标系
- 将第二个探测器$P_2$置于(a,b)处
在已知探测器$P_1$信息的情况下，实际源点的位置$S(x_S,y_S)$存在一个后验概率分布
$$
S \sim \mathrm{P_{S}}(S\big|P_1)
$$
而给定实际源点$S$位置与探测器$P_2$位置，$P_2$探测得到方位角$\theta_2$由于测量误差存在一个概率分布
$$
\theta_2 \sim \mathrm{P_{\theta}}(\theta_2\big|S,a,b)
$$
若确定了位形参数$\theta_2$,a,b，核心指标探测域直径$D$即可通过几何关系得到
$$
D = D(\theta_2,a,b)
$$
故即探测域直径$D$服从一个由几何参量a,b控制的概率分布，则我们关心的核心参量即为
$$
\bar{D}(a,b) = \iint\mathrm{d}^2\vec{r_S} \mathrm{P_S}(S\big|P_1)\int \mathrm{d}\theta_2 D(\theta_2,a,b)\mathrm{P_{\theta}}(\theta_2\big|S,a,b)
$$
是一个二维价值函数，当该函数值越低，在该点设置第二个探测器的
# 理论近似分析
![楔形区域几何分析图](wedge_diagram.png)
由于模型中涉及多次概率分布的积分求取期望值，在理论处理中会带来诸多不便，故我们在理论分析中进行以下近似：
- 探测器$P_2$距离$P_1$距离$R$不太小，其合理性并不是天然正确的，但是由于直观地我们当$P_2$距离$P_1$太近，所得探测域必然较大，这是我们所不希望的，所以$R$较小的区域我们是不关心的，在我们关心的区域内该近似是成立的
- 近似认为实际源点$S$恰好精准分布在$x$轴上，其位置可以只由一个参数$x_S$描述，该近似合理因为当$R$不太小，源点纵坐标$y_S$是小量，故$\mathrm{P_{\theta}}(\theta_2\big|x_S,y_S,a,b)\sim\mathrm{P_{\theta}}(\theta_2\big|x_S,0,a,b)+\frac{\mathrm{d}}{\mathrm{d}y_S}\mathrm{P_{\theta}}(\theta_2\big|x_S,y_S,a,b)\big|_{y_S=0}y_S+o(y_S)$，而在积分时积分区间$y_s$对称，一阶项将抵消。故源点纵坐标$y_S$对直径期望$\bar{D}(a,b)$的影响是高阶的，可以忽略
- 考虑扇形区域的面积，可认为$\mathrm{P_S}(x_S\big|P_1)\propto x_S$
- 由于与第二条近似相似的原因，也可以忽略给定$a,b,x_S,y_S$时$\theta_2$分布的影响，而直接认为$\theta_2$正对源点$S$
**这将我们的价值函数的表达式精简为以下形式：**
$$
\bar{D}(a,b) = \int_0^{x_{max}} \mathrm{d}x_s \mathrm{P_S}(x_S\big|P_1) D(x_s,a,b)
$$
由模型近似我们可以得到
$$
\mathrm{P_S}(x_S\big|P_1) = \frac{2x_S}{x_{max}^2}
$$
 **探测域直径 $D(x_S,a,b)$ 的解析推导** 
 两窄扇形束在空间相交形成近似平行四边形区域 $ABCD$。定义探测域直径 $D(x_S,a,b)$ 为该交点区域沿主伸展方向的长对角线长度。 对于张角极小（$\Delta\theta = 2^\circ \approx 0.0349 \text{ rad} \ll 1$）的探测束，源点 $S(x_S, 0)$ 处的 $P_1$ 扫幅横向宽度为 $w_1 = x_S \Delta\theta$。两探测器观测视线在源点处的交角为 $\alpha$，满足： $$\sin\alpha = \frac{|b|}{r_{2S}}, \quad \text{其中 } r_{2S} = \sqrt{(x_S - a)^2 + b^2}$$ 在小量一阶近似下，交叉区域沿轴向（射线长轴）的几何拉伸跨度占绝对主导，故探测域直径 $D(x_S,a,b)$ 可近似表示为： $$D(x_S,a,b) \approx \frac{w_1}{\sin\alpha} = \frac{x_S r_{2S} \Delta\theta}{|b|} = \frac{\Delta\theta \cdot x_S \sqrt{(x_S - a)^2 + b^2}}{|b|}$$ 将 $\Delta\theta = 2^\circ = \frac{\pi}{90} \text{ rad}$ 代入，得到直径函数的最终解析表达式： $$D(x_S, a, b) \approx \frac{\pi}{90 \cdot |b|} x_S \sqrt{(x_S - a)^2 + b^2}$$ 代入价值函数 $\bar{D}(a,b)$ 中，即可得到可用于高效数值积分与优化的目标函数： $$\bar{D}(a,b) = \frac{\pi}{45 x_{max}^2 |b|} \int_0^{x_{max}} x_S^2 \sqrt{(x_S - a)^2 + b^2} \, \mathrm{d}x_S$$

**价值函数的精确闭合解**
引入无量纲变量 $u = \frac{x_S}{x_{max}} \in [0, 1]$ 以及归一化位置参数 $\hat{a} = \frac{a}{x_{max}}, \, \hat{b} = \frac{b}{x_{max}}$，原式可表示为：
$$\bar{D}(a,b) = \frac{\pi x_{max}}{45 |\hat{b}|} \int_0^1 u^2 \sqrt{(u - \hat{a})^2 + \hat{b}^2} \, \mathrm{d}u$$
**不定积分的精确求积**
做平移变量代换 $t = x_S - a$（即 $x_S = t + a$），被积无理项可展开为三个标准积分项：
$$I(x_S) = \int x_S^2 \sqrt{(x_S - a)^2 + b^2} \, \mathrm{d}x_S = \int (t^2 + 2at + a^2) \sqrt{t^2 + b^2} \, \mathrm{d}t$$

利用标准积分公式精确积出并按代数无理项与超越对数项合并，求得原函数 $F(t; a, b)$ 为：
$$F(t; a, b) = \left( \frac{t^3}{4} + \frac{a t^2}{3} + \frac{2a^2 + b^2}{8}t + \frac{a b^2}{3} \right) \sqrt{t^2 + b^2} + \frac{b^2(4a^2 - b^2)}{8} \ln \left( t + \sqrt{t^2 + b^2} \right)$$
代入积分上下限 $t = x_{max} - a$ 与 $t = -a$，即可消去积分号获得**绝对精确的闭合解析解**
$$\bar{D}(a,b) = \frac{\pi}{45 x_{max}^2 |b|} \Big[ F(x_{max} - a; a, b) - F(-a; a, b) \Big]$$得到
$$\bar{D}(a,b) = \left[ \frac{(x_{max}-a)^3}{4} + \frac{a(x_{max}-a)^2}{3} + \frac{(2a^2+b^2)(x_{max}-a)}{8} + \frac{a b^2}{3} \right] \sqrt{(x_{max}-a)^2 + b^2} + \frac{b^2(4a^2 - b^2)}{8} \ln \left( x_{max} - a + \sqrt{(x_{max}-a)^2 + b^2} \right)$$

绘制理论解，可以得到$\bar{D}(a,b)$的函数图像
![定位直径期望热力图](Q2_expected_diameter_heatmap.png)
使用了非线性颜色映射，重点关注50-100区间
# 数值模拟求解

