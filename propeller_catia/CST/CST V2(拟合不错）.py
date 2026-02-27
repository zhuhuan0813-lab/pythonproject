import numpy as np
import matplotlib.pyplot as plt
from scipy.special import comb
import os

# 设置绘图风格，支持中文
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def CST_parameterization(airfoil_file, N):
    """
    CST_parameterization - 实现翼型CST参数化 (基于MATLAB逻辑复刻)

    输入:
        airfoil_file - 翼型数据文件名
        N - CST参数化的阶数
    输出:
        cst_coeffs_upper - 上表面系数
        cst_coeffs_lower - 下表面系数
        mse_upper - 上表面MSE
        mse_lower - 下表面MSE
    """

    # 1. 读取翼型数据
    print(f"正在读取文件: {airfoil_file}")
    try:
        # 对应 MATLAB: readmatrix(..., 'NumHeaderLines', 1)
        # 假设第一行是标题，跳过。如果数据以空格或Tab分隔。
        airfoil_data = np.loadtxt(airfoil_file, skiprows=1)
    except Exception as e:
        print(f"错误: 无法读取文件. {e}")
        return None, None, None, None

    x = airfoil_data[:, 0]
    y = airfoil_data[:, 1]

    # 2. 数据分割
    # 对应 MATLAB: [~, leading_edge_index] = min(x)
    leading_edge_index = np.argmin(x)

    # 对应 MATLAB: 分割上下表面
    # 注意: Python切片是左闭右开，且索引从0开始
    # MATLAB: 1:leading_edge_index (包含LE)
    # Python: 0:leading_edge_index+1 (包含LE)
    x_upper = x[:leading_edge_index + 1]
    y_upper = y[:leading_edge_index + 1]

    x_lower = x[leading_edge_index:]
    y_lower = y[leading_edge_index:]

    # 3. 归一化 x 坐标
    # 对应 MATLAB: x_norm = x / max(x)
    # 添加防止除以0的安全检查，虽然翼型数据通常不会全0
    max_x_up = np.max(x_upper)
    max_x_lo = np.max(x_lower)

    if max_x_up == 0 or max_x_lo == 0:
        print("错误：数据异常，最大弦长为0")
        return None, None, None, None

    x_norm_upper = x_upper / max_x_up
    x_norm_lower = x_lower / max_x_lo

    # 4. 定义类函数 (Class Function)
    N1 = 0.5
    N2 = 1.0

    # 对应 MATLAB: C = (x).^N1 .* (1-x).^N2
    C_upper = (x_norm_upper ** N1) * ((1 - x_norm_upper) ** N2)
    C_lower = (x_norm_lower ** N1) * ((1 - x_norm_lower) ** N2)

    # 5. 构造设计矩阵 (包含形状函数和类函数)
    # MATLAB代码中直接构建了 (A .* C) 矩阵
    # 我们这里构建矩阵 X，其中 X[:, i] = C * B_i

    num_upper = len(x_norm_upper)
    num_lower = len(x_norm_lower)

    X_upper = np.zeros((num_upper, N + 1))
    X_lower = np.zeros((num_lower, N + 1))

    for i in range(N + 1):
        # 计算组合数 nCi
        K = comb(N, i)

        # Bernstein 基函数: K * x^i * (1-x)^(N-i)
        B_upper = K * (x_norm_upper ** i) * ((1 - x_norm_upper) ** (N - i))
        B_lower = K * (x_norm_lower ** i) * ((1 - x_norm_lower) ** (N - i))

        # 将类函数融入矩阵 (对应 MATLAB: A_upper .* C_upper)
        X_upper[:, i] = C_upper * B_upper
        X_lower[:, i] = C_lower * B_lower

    # 6. 最小二乘法求解系数
    # 对应 MATLAB: coeffs = (A .* C) \ y
    # Python 使用 lstsq, rcond=None 忽略警告
    cst_coeffs_upper, _, _, _ = np.linalg.lstsq(X_upper, y_upper, rcond=None)
    cst_coeffs_lower, _, _, _ = np.linalg.lstsq(X_lower, y_lower, rcond=None)

    # 7. 计算拟合值
    y_fit_upper = X_upper @ cst_coeffs_upper
    y_fit_lower = X_lower @ cst_coeffs_lower

    # 8. 计算 MSE
    mse_upper = np.mean((y_upper - y_fit_upper) ** 2)
    mse_lower = np.mean((y_lower - y_fit_lower) ** 2)

    # 9. 输出结果
    print("-" * 40)
    print("上表面 CST 拟合系数:")
    print(cst_coeffs_upper)
    print(f"上表面 MSE: {mse_upper:.6e}")
    print("-" * 40)
    print("下表面 CST 拟合系数:")
    print(cst_coeffs_lower)
    print(f"下表面 MSE: {mse_lower:.6e}")
    print("-" * 40)

    # 10. 绘图 (完全复刻 MATLAB 绘图逻辑)
    fig = plt.figure(figsize=(10, 8))

    # 子图 1: 拟合结果
    ax1 = plt.subplot(2, 1, 1)
    ax1.plot(x_upper, y_upper, 'b-', linewidth=2, label='上表面原始数据')
    ax1.plot(x_lower, y_lower, 'g-', linewidth=2, label='下表面原始数据')
    ax1.plot(x_upper, y_fit_upper, 'r--', linewidth=2, label='上表面CST拟合')
    ax1.plot(x_lower, y_fit_lower, 'm--', linewidth=2, label='下表面CST拟合')
    ax1.legend()
    ax1.set_xlabel('x')
    ax1.set_ylabel('y')
    ax1.set_title(f'CST参数化拟合结果 (N={N})')
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.axis('equal')  # 保证翼型比例正确

    # 子图 2: 误差分布
    ax2 = plt.subplot(2, 1, 2)
    ax2.plot(x_upper, y_upper - y_fit_upper, 'b-', linewidth=2, label='上表面拟合误差')
    ax2.plot(x_lower, y_lower - y_fit_lower, 'g-', linewidth=2, label='下表面拟合误差')
    ax2.legend()
    ax2.set_xlabel('x')
    ax2.set_ylabel('误差')
    ax2.set_title('拟合误差随 x 的变化')
    ax2.grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    # 保存图片
    plt.savefig('CST_fitting_result_matlab_style.png', dpi=300)
    print("图表已保存为 CST_fitting_result_matlab_style.png")
    plt.show()

    return cst_coeffs_upper, cst_coeffs_lower, mse_upper, mse_lower


# ========== 主程序入口 ==========
if __name__ == "__main__":
    # 替换为你的文件路径
    # 注意：确保文件是标准的 .dat 格式 (Header + x y 数据)
    # 如果路径包含反斜杠 \，请在字符串前加 r，例如 r"D:\path\to\file.dat"
    airfoil_file = r'/propeller_catia/数据/naca_0012.dat'

    # 阶数设置 (MATLAB 示例用了 5，这里保持一致，你可以改为 6, 8, 10)
    N = 5

    if os.path.exists(airfoil_file):
        CST_parameterization(airfoil_file, N)
    else:
        print(f"错误: 找不到文件 {airfoil_file}")
        print("请修改代码中的 `airfoil_file` 变量为你真实的 .dat 文件路径")