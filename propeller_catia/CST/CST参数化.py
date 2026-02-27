import numpy as np
import matplotlib.pyplot as plt
from scipy.special import comb
import os

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def CSTfit_weight(n, x, y, dz, N1=0.5, N2=1.0):
    """
    CST拟合权重计算 (修正版)
    参数:
        n: Bernstein多项式阶数
        x, y: 坐标点
        dz: 后缘厚度修正量 (y_TE)
        N1, N2: 类函数指数 (默认 0.5, 1.0)
    """
    num_points = len(x)
    X = np.zeros((num_points, n + 1))

    # 构建设计矩阵
    # CST公式: y = C(x)*S(x) + x*dz
    # y - x*dz = C(x)*S(x) = x^N1 * (1-x)^N2 * sum(w_i * B_i)
    # 每一项: w_i * [K * x^i * (1-x)^(n-i) * x^N1 * (1-x)^N2]
    # 合并指数: x^(i+N1) * (1-x)^(n-i+N2)

    for j in range(num_points):
        for ii in range(n + 1):
            K = comb(n, ii, exact=True)
            # 修正处的关键：指数必须严格匹配公式
            term_x = x[j] ** (ii + N1)
            term_one_minus_x = (1 - x[j]) ** (n - ii + N2)
            X[j, ii] = K * term_x * term_one_minus_x

    # 最小二乘法求解 w
    # 目标: X * w = y_actual - x * dz
    rhs = y - x * dz

    # 使用 lstsq 比 inv 更稳定
    w, residuals, rank, s = np.linalg.lstsq(X, rhs, rcond=None)
    return w


def ClassShape(w, x, dz, N1=0.5, N2=1.0):
    """
    计算类函数和形函数 (修正版)
    不再需要手动传入 r，因为 r 包含在 w[0] 中
    """
    n = len(w) - 1
    num_points = len(x)

    y_construct = np.zeros(num_points)

    # 向量化计算，速度更快且不易出错
    for i in range(num_points):
        # 计算形状函数 S(x)
        S_val = 0
        for j in range(n + 1):
            K = comb(n, j, exact=True)
            # Bernstein 多项式: B_{j,n}(x)
            B_val = K * (x[i] ** j) * ((1 - x[i]) ** (n - j))
            S_val += w[j] * B_val

        # 计算类函数 C(x)
        C_val = (x[i] ** N1) * ((1 - x[i]) ** N2)

        # 组合
        y_construct[i] = C_val * S_val + x[i] * dz

    return y_construct


def auto_estimate_parameters(x, y):
    """
    自动估计翼型参数 (仅用于显示，不影响拟合)
    """
    # 1. 估计前缘半径
    # 对于标准翼型，前缘附近满足 y = sqrt(2*R*x) => R = y^2 / (2x)
    # 取最靠近前缘的一个非零点进行估算
    idx_check = 1 if len(x) > 1 else 0
    if idx_check < len(x) and x[idx_check] > 1e-6:
        r_estimated = (y[idx_check] ** 2) / (2 * x[idx_check])
    else:
        r_estimated = 0.01

    # 2. 估计后缘厚度
    # 假设输入数据已经包含了后缘点 x=1
    if abs(x[-1] - 1.0) < 0.01:
        dz_estimated = y[-1]
    else:
        # 如果数据没到1，简单外推
        dz_estimated = y[-1]

    return r_estimated, dz_estimated


def improved_CST_fit(filename, m_order=8, n_order=8):
    print(f"正在读取翼型数据: {filename}")

    try:
        data = np.loadtxt(filename, skiprows=0)  # 有些dat文件不需要skiprows=1，视情况而定
    except Exception as e:
        print(f"错误：无法读取文件 - {e}")
        return None

    # 数据预处理：确保按x排序，并分离上下翼面
    # 很多dat文件是从 后缘->前缘->后缘 排列的
    # 找到x最小的点作为前缘分界
    le_idx = np.argmin(data[:, 0])

    # 拆分并确保x从0到1排序
    # 上翼面 (通常在文件中靠前，或者y值为正)
    # 注意：如果原始数据是 TE -> LE，那么上翼面数据 x 是递减的，需要反转
    upper_raw = data[:le_idx + 1]
    lower_raw = data[le_idx:]

    # 确保上翼面 x 从 0->1
    if upper_raw[0, 0] > upper_raw[-1, 0]:
        upper_raw = upper_raw[::-1]

    # 确保下翼面 x 从 0->1
    if lower_raw[0, 0] < lower_raw[-1, 0]:
        pass  # 已经是 0->1
    else:
        lower_raw = lower_raw[::-1]  # 翻转以防万一

    x_up, y_up = upper_raw[:, 0], upper_raw[:, 1]
    x_low, y_low = lower_raw[:, 0], lower_raw[:, 1]

    # 归一化检查 (确保 Chord = 1)
    max_chord = max(np.max(x_up), np.max(x_low))
    if abs(max_chord - 1.0) > 1e-4:
        print(f"检测到弦长为 {max_chord}，正在归一化...")
        x_up /= max_chord
        y_up /= max_chord
        x_low /= max_chord
        y_low /= max_chord

    # 估计参数 (用于dz)
    _, dzu = auto_estimate_parameters(x_up, y_up)
    _, dzl = auto_estimate_parameters(x_low, y_low)  # dzl 通常为负或0，这里取原始值

    print(f"上翼面后缘 z = {dzu:.6f}")
    print(f"下翼面后缘 z = {dzl:.6f}")

    # ========== 拟合计算 ==========
    print(f"\n正在进行CST拟合 (Order={m_order}/{n_order})...")

    # 计算权重
    wu = CSTfit_weight(m_order, x_up, y_up, dzu)
    wl = CSTfit_weight(n_order, x_low, y_low, dzl)  # dzl直接传入，包含符号

    # 反算前缘半径 (R = w0^2 / 2)
    r_up_fit = (wu[0] ** 2) / 2
    r_low_fit = (wl[0] ** 2) / 2
    print(f"拟合反推前缘半径 (上): {r_up_fit:.6f}")
    print(f"拟合反推前缘半径 (下): {r_low_fit:.6f}")

    # 重构曲线
    ynewup = ClassShape(wu, x_up, dzu)
    ynewlow = ClassShape(wl, x_low, dzl)

    # 拼接结果用于画图
    xall = np.concatenate([x_up[::-1], x_low[1:]])  # 拼成 TE->LE->TE
    y_original_plot = np.concatenate([y_up[::-1], y_low[1:]])

    y_recon_plot = np.concatenate([ynewup[::-1], ynewlow[1:]])

    # ========== 误差分析 ==========
    error = y_recon_plot - y_original_plot
    rmse = np.sqrt(np.mean(error ** 2))

    print(f"\n拟合质量:")
    print(f"  RMSE = {rmse:.6e}")
    print(f"  Max Error = {np.max(np.abs(error)):.6e}")

    # ========== 可视化 ==========
    plt.figure(figsize=(10, 6))
    plt.plot(xall, y_original_plot, 'ko', markersize=3, fillstyle='none', label='原始数据')
    plt.plot(xall, y_recon_plot, 'r-', linewidth=1.5, label='CST 重构')
    plt.title(f'CST Airfoil Fitting (Order {m_order})\nRMSE: {rmse:.2e}', fontsize=14)
    plt.xlabel('x/c')
    plt.ylabel('y/c')
    plt.legend()
    plt.axis('equal')
    plt.grid(True, alpha=0.3)
    plt.savefig('CST_Result_Fixed.png', dpi=300)
    plt.show()

    return wu, wl


if __name__ == "__main__":
    # 请修改为你的实际路径
    filename = r'/propeller_catia/数据/naca_0012.dat'

    if os.path.exists(filename):
        # 使用 8 阶或 10 阶通常对 NACA0012 足够
        improved_CST_fit(filename, m_order=8, n_order=8)
    else:
        # 生成测试数据 (如果没有文件)
        print("未找到文件，使用生成的 NACA0012 数据测试...")
        t = 0.12
        x = np.linspace(0, 1, 100)
        yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1015 * x ** 4)

        # 伪造一个文件写入
        with open('temp_naca0012.dat', 'w') as f:
            f.write("NACA 0012 TEST\n")
            # 上表面 (1 -> 0)
            for i in range(len(x) - 1, -1, -1):
                f.write(f"{x[i]:.6f}  {yt[i]:.6f}\n")
            # 下表面 (0 -> 1) 剔除重复的0点
            for i in range(1, len(x)):
                f.write(f"{x[i]:.6f}  {-yt[i]:.6f}\n")

        improved_CST_fit('temp_naca0012.dat', m_order=8, n_order=8)