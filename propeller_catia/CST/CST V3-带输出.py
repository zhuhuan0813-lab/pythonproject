import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.special import comb
import os

# ================= 配置区 =================
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


# ==========================================

def calculate_errors(y_true, y_fit):
    """计算误差指标"""
    error = y_true - y_fit
    mse = np.mean(error ** 2)
    rmse = np.sqrt(mse)
    max_error = np.max(np.abs(error))
    return mse, rmse, max_error, error


def CST_parameterization(airfoil_file, N=5):
    """
    核心 CST 参数化函数
    """
    print(f"正在处理文件: {airfoil_file}")

    # 1. 读取数据
    try:
        data = np.loadtxt(airfoil_file, skiprows=1)
    except Exception as e:
        print(f"读取失败: {e}")
        return None

    # ===== 统计原始数据点数 =====
    total_raw_points = len(data)
    print(f"原始翼型文件总点数: {total_raw_points}")

    x = data[:, 0]
    y = data[:, 1]

    # 2. 分离上下翼面
    le_idx = np.argmin(x)
    print(f"前缘点索引 le_idx: {le_idx}")

    # 提取原始数据
    x_up_raw = x[:le_idx + 1]
    y_up_raw = y[:le_idx + 1]
    x_lo_raw = x[le_idx:]
    y_lo_raw = y[le_idx:]

    # ===== 关键修复：反转上翼面数据，确保x从前缘到尾缘递增 =====
    x_up_raw = x_up_raw[::-1]
    y_up_raw = y_up_raw[::-1]

    print(f"上表面x范围: [{x_up_raw[0]:.6f}, {x_up_raw[-1]:.6f}]")
    print(f"下表面x范围: [{x_lo_raw[0]:.6f}, {x_lo_raw[-1]:.6f}]")

    # ===== 统计上下表面原始点数 =====
    up_raw_points = len(x_up_raw)
    lo_raw_points = len(x_lo_raw)
    print(f"上表面原始点数: {up_raw_points}")
    print(f"下表面原始点数: {lo_raw_points}")

    # 归一化处理（确保弦长为1）
    chord = max(np.max(x), 1e-6)
    x_up = x_up_raw / chord
    y_up = y_up_raw / chord
    x_lo = x_lo_raw / chord
    y_lo = y_lo_raw / chord

    # ===== 额外检查：确保没有负值 =====
    print(f"上表面归一化后x范围: [{np.min(x_up):.6f}, {np.max(x_up):.6f}]")
    print(f"下表面归一化后x范围: [{np.min(x_lo):.6f}, {np.max(x_lo):.6f}]")

    if np.any(x_up < 0) or np.any(x_lo < 0):
        print("警告：发现负的x坐标值！")
        # 将负值钳位到0
        x_up = np.clip(x_up, 0, 1)
        x_lo = np.clip(x_lo, 0, 1)

    # 3. 构建 CST 矩阵
    def build_cst_matrix(x_arr, order):
        m = len(x_arr)
        X = np.zeros((m, order + 1))

        # 确保x_arr在[0,1]范围内
        x_arr = np.clip(x_arr, 1e-10, 1.0)  # 避免0和1的边界问题

        C = (x_arr ** 0.5) * ((1 - x_arr) ** 1.0)

        for i in range(order + 1):
            K = comb(order, i)
            B = K * (x_arr ** i) * ((1 - x_arr) ** (order - i))
            X[:, i] = C * B

        # 检查是否有NaN或Inf
        if np.any(~np.isfinite(X)):
            print("警告：CST矩阵中存在NaN或Inf值！")
            print(f"x_arr范围: [{np.min(x_arr)}, {np.max(x_arr)}]")

        return X

    X_up = build_cst_matrix(x_up, N)
    X_lo = build_cst_matrix(x_lo, N)

    # 检查矩阵是否有效
    print(f"X_up矩阵是否有效: {np.all(np.isfinite(X_up))}")
    print(f"X_lo矩阵是否有效: {np.all(np.isfinite(X_lo))}")

    # 4. 求解系数 (最小二乘)
    try:
        w_up, _, _, _ = np.linalg.lstsq(X_up, y_up, rcond=None)
        w_lo, _, _, _ = np.linalg.lstsq(X_lo, y_lo, rcond=None)
    except np.linalg.LinAlgError as e:
        print(f"最小二乘求解失败: {e}")
        return None

    # 5. 重构曲线与计算误差
    y_up_fit = X_up @ w_up
    y_lo_fit = X_lo @ w_lo

    mse_u, rmse_u, max_u, err_u = calculate_errors(y_up, y_up_fit)
    mse_l, rmse_l, max_l, err_l = calculate_errors(y_lo, y_lo_fit)

    # ===== 统计拟合后点数 =====
    up_fit_points = len(y_up_fit)
    lo_fit_points = len(y_lo_fit)
    total_fit_points = up_fit_points + lo_fit_points - 1  # 去重前缘点
    print(f"拟合后上表面点数: {up_fit_points}")
    print(f"拟合后下表面点数: {lo_fit_points}")
    print(f"输出总点数（去重前缘点）: {total_fit_points}")

    # 打包所有结果
    results = {
        'N': N,
        'coeffs_up': w_up,
        'coeffs_lo': w_lo,
        'errors': {
            'upper': {'mse': mse_u, 'rmse': rmse_u, 'max': max_u, 'error_vec': err_u},
            'lower': {'mse': mse_l, 'rmse': rmse_l, 'max': max_l, 'error_vec': err_l}
        },
        'coords': {
            'x_up': x_up, 'y_up': y_up_fit,
            'x_lo': x_lo, 'y_lo': y_lo_fit
        },
        'raw': {
            'x_up': x_up, 'y_up': y_up,
            'x_lo': x_lo, 'y_lo': y_lo
        },
        # 点数统计结果
        'point_count': {
            'raw_total': total_raw_points,
            'up_raw': up_raw_points,
            'lo_raw': lo_raw_points,
            'fit_total': total_fit_points,
            'up_fit': up_fit_points,
            'lo_fit': lo_fit_points
        }
    }
    return results


def save_and_report(results, output_prefix="CST_Result"):
    """
    保存坐标文件、报告文件并绘制详细分析图
    """
    if not results: return

    # ================= 1. 生成详细文本报告 (.txt) =================
    report_file = f"{output_prefix}_Report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 50 + "\n")
        f.write(f"CST 参数化拟合报告 (阶数 N={results['N']})\n")
        f.write("=" * 50 + "\n\n")

        # ===== 点数统计 =====
        f.write("0. 点数统计:\n")
        f.write("-" * 50 + "\n")
        point_count = results['point_count']
        f.write(f"原始总点数: {point_count['raw_total']}\n")
        f.write(f"上表面原始点数: {point_count['up_raw']}\n")
        f.write(f"下表面原始点数: {point_count['lo_raw']}\n")
        f.write(f"拟合后输出总点数（去重前缘点）: {point_count['fit_total']}\n\n")

        f.write("1. 拟合误差分析:\n")
        f.write("-" * 50 + "\n")
        f.write(f"{'指标':<10} | {'上表面':<15} | {'下表面':<15}\n")
        f.write("-" * 50 + "\n")
        err = results['errors']
        f.write(f"{'MSE':<10} | {err['upper']['mse']:<15.6e} | {err['lower']['mse']:<15.6e}\n")
        f.write(f"{'RMSE':<10} | {err['upper']['rmse']:<15.6e} | {err['lower']['rmse']:<15.6e}\n")
        f.write(f"{'Max Abs':<10} | {err['upper']['max']:<15.6e} | {err['lower']['max']:<15.6e}\n")
        f.write("\n")

        f.write("2. CST 拟合参数 (系数):\n")
        f.write("-" * 50 + "\n")
        f.write("上表面系数 A_upper (从 A0 到 An):\n")
        f.write(str(list(results['coeffs_up'])) + "\n\n")
        f.write("下表面系数 A_lower (从 A0 到 An):\n")
        f.write(str(list(results['coeffs_lo'])) + "\n\n")

    print(f"✅ 分析报告已保存: {report_file}")

    # ================= 2. 生成 3D 坐标文件 (.dat) =================
    coord_file = f"{output_prefix}_3D_Coords.dat"
    x_up, y_up = results['coords']['x_up'], results['coords']['y_up']
    x_lo, y_lo = results['coords']['x_lo'], results['coords']['y_lo']

    # 统计写入文件的点数
    write_count = 0
    with open(coord_file, 'w') as f:
        # 上表面
        for i in range(len(x_up)):
            f.write(f"{x_up[i]:.6f}  {y_up[i]:.6f}  0.000000\n")
            write_count += 1

        # 下表面 (去重前缘点)
        start_idx = 0
        if len(x_lo) > 0 and len(x_up) > 0:
            dist = (x_lo[0] - x_up[-1]) ** 2 + (y_lo[0] - y_up[-1]) ** 2
            if dist < 1e-9: start_idx = 1

        for i in range(start_idx, len(x_lo)):
            f.write(f"{x_lo[i]:.6f}  {y_lo[i]:.6f}  0.000000\n")
            write_count += 1

    print(f"✅ 3D坐标文件已保存: {coord_file} (实际写入点数: {write_count})")

    # ================= 3. 高级可视化绘图 (4图合1) =================
    N = results['N']
    x_up, y_fit_up = results['coords']['x_up'], results['coords']['y_up']
    x_lo, y_fit_lo = results['coords']['x_lo'], results['coords']['y_lo']
    x_raw_u, y_raw_u = results['raw']['x_up'], results['raw']['y_up']
    x_raw_l, y_raw_l = results['raw']['x_lo'], results['raw']['y_lo']
    err_u = results['errors']['upper']['error_vec']
    err_l = results['errors']['lower']['error_vec']

    rmse_u = results['errors']['upper']['rmse']
    rmse_l = results['errors']['lower']['rmse']
    max_u = results['errors']['upper']['max']
    max_l = results['errors']['lower']['max']

    all_errors = np.concatenate([err_u, err_l])

    fig = plt.figure(figsize=(15, 10))
    gs = gridspec.GridSpec(2, 2, hspace=0.3, wspace=0.25)

    # --- 图1: 几何拟合对比 (左上) ---
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(x_raw_u, y_raw_u, 'ok', ms=3, fillstyle='none', alpha=0.4, label='Raw Data')
    ax1.plot(x_raw_l, y_raw_l, 'ok', ms=3, fillstyle='none', alpha=0.4)
    ax1.plot(x_up, y_fit_up, 'r-', lw=1.5, label='CST Upper')
    ax1.plot(x_lo, y_fit_lo, 'b-', lw=1.5, label='CST Lower')

    stats_box = (f"Order N={N}\n"
                 f"RMSE(Up): {rmse_u:.1e}\n"
                 f"RMSE(Lo): {rmse_l:.1e}\n"
                 f"Total Points: {write_count}")
    ax1.text(0.05, 0.05, stats_box, transform=ax1.transAxes, fontsize=10,
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.9))

    ax1.set_title('几何拟合效果对比', fontweight='bold')
    ax1.set_xlabel('x/c')
    ax1.set_ylabel('y/c')
    ax1.axis('equal')
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='upper right')

    # --- 图2: 残差分布曲线 (右上) ---
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(x_up, err_u, 'r-', lw=1, label='Upper Error')
    ax2.plot(x_lo, err_l, 'b-', lw=1, label='Lower Error')
    ax2.axhline(0, color='k', ls='--', lw=0.8)

    max_idx_u = np.argmax(np.abs(err_u))
    ax2.plot(x_up[max_idx_u], err_u[max_idx_u], 'rx', ms=10, label=f'Max: {max_u:.1e}')

    ax2.set_title('拟合残差分布 (Residuals)', fontweight='bold')
    ax2.set_xlabel('x/c')
    ax2.set_ylabel('Error')
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend()

    # --- 图3: 误差直方图 (左下) ---
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.hist(all_errors, bins=40, color='gray', alpha=0.6, density=True, edgecolor='black')

    mu, std = np.mean(all_errors), np.std(all_errors)
    xmin, xmax = ax3.get_xlim()
    x_pdf = np.linspace(xmin, xmax, 100)
    p_pdf = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_pdf - mu) / std) ** 2)
    ax3.plot(x_pdf, p_pdf, 'r--', lw=2, label=f'Normal Fit\n$\sigma$={std:.1e}')

    ax3.set_title('误差频率分布直方图', fontweight='bold')
    ax3.set_xlabel('Error Value')
    ax3.set_ylabel('Density')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # --- 图4: 空间误差热力图 (右下) ---
    ax4 = fig.add_subplot(gs[1, 1])
    x_all = np.concatenate([x_up, x_lo])
    y_all = np.concatenate([y_fit_up, y_fit_lo])
    abs_err_all = np.abs(np.concatenate([err_u, err_l]))

    sc = ax4.scatter(x_all, y_all, c=abs_err_all, cmap='jet', s=20, edgecolor='none')
    cbar = plt.colorbar(sc, ax=ax4)
    cbar.set_label('Absolute Error Magnitude')

    ax4.set_title('空间误差热力图 (红色代表高误差区)', fontweight='bold')
    ax4.set_xlabel('x/c')
    ax4.set_ylabel('y/c')
    ax4.axis('equal')
    ax4.grid(True, linestyle=':', alpha=0.3)

    plt.suptitle(f'CST 参数化拟合详细分析 (Order={N}, Total Points={write_count})', fontsize=16, y=0.96)

    # 保存图片
    output_img = f"{output_prefix}_Analysis.png"
    plt.savefig(output_img, dpi=300, bbox_inches='tight')
    print(f"✅ 可视化图表已保存: {output_img}")
    plt.show()


# ==========================================
# 主程序入口
# ==========================================
if __name__ == "__main__":
    FILE_PATH = r'D:\PythonProject\propeller_catia\NACA64-118_300.dat'
    ORDER = 6  # CST 阶数 (建议 5-10)

    if os.path.exists(FILE_PATH):
        res = CST_parameterization(FILE_PATH, N=ORDER)
        if res:
            save_and_report(res, output_prefix="NACA0012_CST_V4_Detailed")

            print("\n" + "=" * 40)
            print("所有任务完成！")
            print(f"1. 报告文件: NACA0012_CST_V4_Detailed_Report.txt")
            print(f"2. 3D坐标文件: NACA0012_CST_V4_Detailed_3D_Coords.dat (点数: {res['point_count']['fit_total']})")
            print(f"3. 分析图表: NACA0012_CST_V4_Detailed_Analysis.png")
            print("=" * 40)
    else:
        print(f"错误：找不到文件 {FILE_PATH}")