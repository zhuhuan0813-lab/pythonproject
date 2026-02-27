"""
XV-15螺旋桨完整优化流程主程序
步骤1: 拉丁超立方采样生成设计方案
步骤2: CATIA批量建模导出STEP
步骤3: BEM低保真筛选
步骤4: 选出Top 200准备CFD

作者: 自动生成
日期: 2026-02-08
基于XV-15倾转旋翼机复现
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import json

# 确保所有模块可导入
sys.path.append(os.path.dirname(__file__))

print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║          XV-15螺旋桨气动优化完整流程                             ║
║                                                                  ║
║   步骤1: 拉丁超立方采样 (1000个设计)                            ║
║   步骤2: CATIA批量建模                                           ║
║   步骤3: BEM低保真筛选                                           ║
║   步骤4: 选出Top 200准备CFD                                      ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")


class XV15OptimizationWorkflow:
    """XV-15完整优化工作流"""

    def __init__(self, config: dict):
        """
        初始化工作流

        参数:
            config: 配置字典
        """
        self.config = config
        self.results = {}

        # 创建工作目录
        self.work_dir = config.get('work_dir', 'XV15_Optimization')
        os.makedirs(self.work_dir, exist_ok=True)

        # 创建子目录
        self.sampling_dir = os.path.join(self.work_dir, '1_Sampling')
        self.catia_dir = os.path.join(self.work_dir, '2_CATIA_Models')
        self.bem_dir = os.path.join(self.work_dir, '3_BEM_Screening')
        self.cfd_dir = os.path.join(self.work_dir, '4_CFD_Preparation')

        for d in [self.sampling_dir, self.catia_dir, self.bem_dir, self.cfd_dir]:
            os.makedirs(d, exist_ok=True)

        # 日志文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.work_dir, f'workflow_log_{timestamp}.txt')

        self.log("=" * 70)
        self.log("XV-15螺旋桨优化工作流初始化")
        self.log("=" * 70)
        self.log(f"工作目录: {self.work_dir}")
        self.log(f"配置: {json.dumps(config, indent=2, ensure_ascii=False)}")

    def log(self, message: str):
        """写日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')

    def step1_sampling(self, n_samples: int = 1000):
        """
        步骤1: 拉丁超立方采样

        参数:
            n_samples: 样本数量
        """
        self.log("\n" + "=" * 70)
        self.log("步骤1: 拉丁超立方采样")
        self.log("=" * 70)

        from xv15_sampling import (
            ParameterBounds, LatinHypercubeSampler, analyze_design_space
        )

        # 分析设计空间
        analyze_design_space()

        # 设计变量
        design_vars = [
            '翼根弦长',
            '翼中弦长',
            '翼尖弦长',
            '翼根扭转角',
            '翼中扭转角',
            '翼尖扭转角',
        ]

        # 获取边界
        bounds = ParameterBounds.get_bounds_array(design_vars)

        # 创建采样器
        sampler = LatinHypercubeSampler(
            param_names=design_vars,
            bounds=bounds,
            seed=42
        )

        # 生成样本
        df_samples = sampler.generate_samples(
            n_samples=n_samples,
            apply_constraints=True,
            max_attempts=20000
        )

        # 添加固定参数
        df_samples['旋翼直径'] = 7620.0
        df_samples['桨叶数'] = 3

        # 保存
        samples_file = os.path.join(self.sampling_dir, 'design_samples.csv')
        df_samples.to_csv(samples_file, index=False, encoding='utf-8-sig')

        # 可视化
        plot_file = os.path.join(self.sampling_dir, 'sampling_distribution.png')
        sampler.plot_samples(df_samples, save_path=plot_file)

        self.results['step1'] = {
            'samples_file': samples_file,
            'n_samples': len(df_samples),
            'plot_file': plot_file
        }

        self.log(f"✓ 步骤1完成")
        self.log(f"  生成样本: {len(df_samples)}")
        self.log(f"  输出文件: {samples_file}")

        return df_samples

    def step2_catia_modeling(self, df_samples: pd.DataFrame,
                             n_models: int = None,
                             test_mode: bool = False):
        """
        步骤2: CATIA批量建模

        参数:
            df_samples: 设计样本DataFrame
            n_models: 建模数量（None表示全部）
            test_mode: 测试模式（只处理前10个）
        """
        self.log("\n" + "=" * 70)
        self.log("步骤2: CATIA批量建模")
        self.log("=" * 70)

        # 检查CATIA模板
        template_file = self.config.get('catia_template')
        if not os.path.exists(template_file):
            self.log(f"✗ 错误: CATIA模板不存在: {template_file}")
            return None

        # 测试模式
        if test_mode:
            df_samples = df_samples.head(10)
            self.log("⚠️  测试模式: 只处理前10个设计")
        elif n_models:
            df_samples = df_samples.head(n_models)
            self.log(f"处理前 {n_models} 个设计")

        # 导入CATIA建模模块
        from catia_batch_modeling import CATIABatchModeler

        # 创建批量建模器
        modeler = CATIABatchModeler(
            template_path=template_file,
            output_dir=self.catia_dir
        )

        # 批量处理
        df_results = modeler.batch_process(
            df=df_samples,
            save_catia=False,  # 不保存CATIA文件以节省空间
            save_interval=20
        )

        # 保存结果
        results_file = os.path.join(self.catia_dir, 'batch_modeling_results.csv')
        df_results.to_csv(results_file, index=False, encoding='utf-8-sig')

        # 统计
        success_count = df_results['success'].sum()

        self.results['step2'] = {
            'results_file': results_file,
            'total': len(df_results),
            'success': success_count,
            'success_rate': success_count / len(df_results) * 100
        }

        self.log(f"✓ 步骤2完成")
        self.log(f"  总数: {len(df_results)}")
        self.log(f"  成功: {success_count}")
        self.log(f"  成功率: {success_count / len(df_results) * 100:.1f}%")

        return df_results

    def step3_bem_screening(self, df_samples: pd.DataFrame):
        """
        步骤3: BEM低保真筛选

        参数:
            df_samples: 设计样本DataFrame
        """
        self.log("\n" + "=" * 70)
        self.log("步骤3: BEM低保真筛选")
        self.log("=" * 70)

        from xv15_bem_screening import XV15BEMScreener

        # 创建筛选器
        screener = XV15BEMScreener(
            design_point={
                'V_inf': 77.2,  # 150 knots ≈ 77.2 m/s (巡航速度)
                'rpm': 397  # 397 RPM (飞机模式)
            }
        )

        # 批量分析
        bem_results_file = os.path.join(self.bem_dir, 'bem_analysis_results.csv')
        df_bem_results = screener.batch_analyze(
            df_samples,
            save_path=bem_results_file
        )

        # 统计
        success_count = df_bem_results['success'].sum()

        if success_count > 0:
            valid_results = df_bem_results[df_bem_results['success'] == True]
            avg_efficiency = valid_results['eta_%'].mean()
            max_efficiency = valid_results['eta_%'].max()

            self.results['step3'] = {
                'bem_results_file': bem_results_file,
                'total': len(df_bem_results),
                'success': success_count,
                'avg_efficiency': avg_efficiency,
                'max_efficiency': max_efficiency
            }

            self.log(f"✓ 步骤3完成")
            self.log(f"  分析总数: {len(df_bem_results)}")
            self.log(f"  成功: {success_count}")
            self.log(f"  平均效率: {avg_efficiency:.2f}%")
            self.log(f"  最高效率: {max_efficiency:.2f}%")
        else:
            self.log(f"✗ 步骤3失败: 没有成功的BEM分析")
            return None

        return df_bem_results

    def step4_select_top_designs(self, df_bem_results: pd.DataFrame,
                                 n_select: int = 200,
                                 min_efficiency: float = 75.0):
        """
        步骤4: 选择Top设计准备CFD

        参数:
            df_bem_results: BEM分析结果
            n_select: 选择数量
            min_efficiency: 最小效率要求
        """
        self.log("\n" + "=" * 70)
        self.log(f"步骤4: 筛选Top {n_select}设计")
        self.log("=" * 70)

        from xv15_bem_screening import XV15BEMScreener

        screener = XV15BEMScreener()
        df_selected = screener.select_top_designs(
            df_bem_results,
            n_select=n_select,
            criteria='eta_%',
            min_efficiency=min_efficiency
        )

        if len(df_selected) == 0:
            self.log(f"✗ 步骤4失败: 没有设计满足效率要求(≥{min_efficiency}%)")
            return None

        # 保存筛选结果
        selected_file = os.path.join(self.cfd_dir, f'top{n_select}_for_cfd.csv')
        df_selected.to_csv(selected_file, index=False, encoding='utf-8-sig')

        # 生成CFD准备清单
        cfd_list_file = os.path.join(self.cfd_dir, 'cfd_simulation_list.txt')
        with open(cfd_list_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("CFD仿真准备清单\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"筛选时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"设计数量: {len(df_selected)}\n")
            f.write(f"效率范围: {df_selected['eta_%'].min():.2f}% ~ {df_selected['eta_%'].max():.2f}%\n\n")

            f.write("-" * 70 + "\n")
            f.write("Top 10 高效率设计\n")
            f.write("-" * 70 + "\n\n")

            for i, row in df_selected.head(10).iterrows():
                f.write(f"设计 #{int(row['case_id'])}:\n")
                f.write(f"  效率: {row['eta_%']:.2f}%\n")
                f.write(f"  推力: {row['T_N']:.1f} N\n")
                f.write(f"  功率: {row['P_kW']:.2f} kW\n")
                f.write(f"  翼根弦长: {row['翼根弦长']:.1f} mm\n")
                f.write(f"  翼尖弦长: {row['翼尖弦长']:.1f} mm\n")
                f.write(f"  翼根扭转角: {row['翼根扭转角']:.2f}°\n")
                f.write(f"  翼尖扭转角: {row['翼尖扭转角']:.2f}°\n")
                f.write(f"  STEP文件: xv15_case_{int(row['case_id']):04d}.stp\n\n")

        self.results['step4'] = {
            'selected_file': selected_file,
            'cfd_list_file': cfd_list_file,
            'n_selected': len(df_selected),
            'efficiency_range': (df_selected['eta_%'].min(), df_selected['eta_%'].max())
        }

        self.log(f"✓ 步骤4完成")
        self.log(f"  筛选数量: {len(df_selected)}")
        self.log(f"  效率范围: {df_selected['eta_%'].min():.2f}% ~ {df_selected['eta_%'].max():.2f}%")
        self.log(f"  输出文件: {selected_file}")
        self.log(f"  CFD清单: {cfd_list_file}")

        # 显示Top 10
        self.log(f"\n🏆 Top 10 高效率设计:")
        top10 = df_selected[['case_id', '翼根弦长', '翼尖弦长',
                             '翼根扭转角', '翼尖扭转角', 'eta_%', 'T_N']].head(10)
        self.log("\n" + top10.to_string(index=False))

        return df_selected

    def generate_final_report(self):
        """生成最终报告"""
        self.log("\n" + "=" * 70)
        self.log("生成最终报告")
        self.log("=" * 70)

        report_file = os.path.join(self.work_dir, 'final_report.txt')

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("╔══════════════════════════════════════════════════════════════════╗\n")
            f.write("║                                                                  ║\n")
            f.write("║          XV-15螺旋桨气动优化最终报告                             ║\n")
            f.write("║                                                                  ║\n")
            f.write("╚══════════════════════════════════════════════════════════════════╝\n\n")

            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"工作目录: {self.work_dir}\n\n")

            f.write("=" * 70 + "\n")
            f.write("流程摘要\n")
            f.write("=" * 70 + "\n\n")

            # 步骤1
            if 'step1' in self.results:
                f.write("【步骤1】拉丁超立方采样\n")
                f.write(f"  生成样本数: {self.results['step1']['n_samples']}\n")
                f.write(f"  输出文件: {self.results['step1']['samples_file']}\n\n")

            # 步骤2
            if 'step2' in self.results:
                f.write("【步骤2】CATIA批量建模\n")
                f.write(f"  处理总数: {self.results['step2']['total']}\n")
                f.write(f"  成功数量: {self.results['step2']['success']}\n")
                f.write(f"  成功率: {self.results['step2']['success_rate']:.1f}%\n")
                f.write(f"  输出目录: {self.catia_dir}\n\n")

            # 步骤3
            if 'step3' in self.results:
                f.write("【步骤3】BEM低保真筛选\n")
                f.write(f"  分析总数: {self.results['step3']['total']}\n")
                f.write(f"  成功数量: {self.results['step3']['success']}\n")
                f.write(f"  平均效率: {self.results['step3']['avg_efficiency']:.2f}%\n")
                f.write(f"  最高效率: {self.results['step3']['max_efficiency']:.2f}%\n\n")

            # 步骤4
            if 'step4' in self.results:
                f.write("【步骤4】Top设计筛选\n")
                f.write(f"  筛选数量: {self.results['step4']['n_selected']}\n")
                f.write(f"  效率范围: {self.results['step4']['efficiency_range'][0]:.2f}% ~ "
                        f"{self.results['step4']['efficiency_range'][1]:.2f}%\n")
                f.write(f"  CFD清单: {self.results['step4']['cfd_list_file']}\n\n")

            f.write("=" * 70 + "\n")
            f.write("下一步建议\n")
            f.write("=" * 70 + "\n\n")
            f.write("1. 检查Top 200设计的STEP文件\n")
            f.write("2. 在STAR-CCM+中批量导入进行CFD验证\n")
            f.write("3. 对比BEM预测与CFD结果\n")
            f.write("4. 根据CFD结果调整BEM模型（如翼型数据）\n")
            f.write("5. 可能需要对Top 10进行详细的CFD网格收敛性研究\n\n")

            f.write("=" * 70 + "\n")
            f.write("工作流程完成\n")
            f.write("=" * 70 + "\n")

        self.log(f"✓ 最终报告已保存: {report_file}")

        return report_file

    def run_complete_workflow(self,
                              n_samples: int = 1000,
                              n_select: int = 200,
                              skip_catia: bool = False):
        """
        运行完整工作流

        参数:
            n_samples: 采样数量
            n_select: 最终筛选数量
            skip_catia: 跳过CATIA建模（用于测试BEM）
        """
        try:
            # 步骤1: 采样
            df_samples = self.step1_sampling(n_samples=n_samples)

            # 步骤2: CATIA建模（可选跳过）
            if not skip_catia:
                df_catia_results = self.step2_catia_modeling(df_samples)
            else:
                self.log("\n⚠️  跳过CATIA建模步骤")

            # 步骤3: BEM筛选
            df_bem_results = self.step3_bem_screening(df_samples)

            if df_bem_results is None:
                self.log("✗ 工作流中断: BEM筛选失败")
                return False

            # 步骤4: 选择Top设计
            df_selected = self.step4_select_top_designs(
                df_bem_results,
                n_select=n_select,
                min_efficiency=75.0
            )

            if df_selected is None:
                self.log("✗ 工作流中断: 没有满足要求的设计")
                return False

            # 生成最终报告
            report_file = self.generate_final_report()

            self.log("\n" + "╔" + "═" * 68 + "╗")
            self.log("║" + " " * 68 + "║")
            self.log("║" + "          ✅ 完整工作流成功完成!".center(68) + "║")
            self.log("║" + " " * 68 + "║")
            self.log("╚" + "═" * 68 + "╝")

            self.log(f"\n📁 工作目录: {self.work_dir}")
            self.log(f"📊 最终报告: {report_file}")
            self.log(f"🏆 Top {n_select}设计已准备好CFD仿真")

            return True

        except Exception as e:
            self.log(f"\n✗ 工作流失败: {e}")
            import traceback
            traceback.print_exc()
            return False


# ============================================================================
# 主程序入口
# ============================================================================

if __name__ == "__main__":

    # 配置
    CONFIG = {
        'work_dir': r'D:\17484\Documents\OneDrive\Desktop\XV15_Optimization',
        'catia_template': r'D:\17484\Documents\OneDrive\Desktop\XV-15桨叶总成\XV-15 ASM.CATProduct',
    }

    # 创建工作流
    workflow = XV15OptimizationWorkflow(CONFIG)

    # 运行模式选择
    print("\n请选择运行模式:")
    print("1. 完整流程 (采样1000 + CATIA建模 + BEM筛选 + Top200)")
    print("2. 快速测试 (采样100 + BEM筛选，跳过CATIA)")
    print("3. 仅BEM筛选 (使用已有采样数据)")

    choice = input("\n请输入选择 (1/2/3): ").strip()

    if choice == '1':
        print("\n⚠️  警告: 完整流程需要数小时！")
        confirm = input("确认运行完整流程? (yes/no): ")
        if confirm.lower() == 'yes':
            workflow.run_complete_workflow(
                n_samples=1000,
                n_select=200,
                skip_catia=False
            )

    elif choice == '2':
        print("\n运行快速测试...")
        workflow.run_complete_workflow(
            n_samples=100,
            n_select=50,
            skip_catia=True  # 跳过CATIA，只测试BEM
        )

    elif choice == '3':
        print("\n使用已有采样数据进行BEM筛选...")
        samples_file = input("请输入采样数据文件路径: ").strip()
        if os.path.exists(samples_file):
            df_samples = pd.read_csv(samples_file, encoding='utf-8-sig')
            df_bem_results = workflow.step3_bem_screening(df_samples)
            if df_bem_results is not None:
                workflow.step4_select_top_designs(df_bem_results, n_select=200)
                workflow.generate_final_report()
        else:
            print(f"错误: 文件不存在: {samples_file}")

    else:
        print("无效选择")