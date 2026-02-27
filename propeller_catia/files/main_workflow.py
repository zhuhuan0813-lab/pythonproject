"""
XV-15 螺旋桨参数化采样 + CATIA 批量建模 + BEM 低保真筛选 + Top 200 输出

使用步骤:
1) 运行采样 (LHS)
2) 可选: CATIA 批量建模导出 STEP
3) BEM 批量分析并筛选 Top 200
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Optional

import pandas as pd


class XV15OptimizationWorkflow:
    def __init__(self, config: Dict):
        self.config = config
        self.results = {}

        self.work_dir = config.get("work_dir", "XV15_Optimization")
        os.makedirs(self.work_dir, exist_ok=True)

        self.sampling_dir = os.path.join(self.work_dir, "1_Sampling")
        self.catia_dir = os.path.join(self.work_dir, "2_CATIA_Models")
        self.bem_dir = os.path.join(self.work_dir, "3_BEM_Screening")
        self.cfd_dir = os.path.join(self.work_dir, "4_CFD_Preparation")

        for d in (self.sampling_dir, self.catia_dir, self.bem_dir, self.cfd_dir):
            os.makedirs(d, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.work_dir, f"workflow_log_{ts}.txt")

        self.log("=" * 70)
        self.log("XV-15 螺旋桨优化流程初始化")
        self.log("=" * 70)
        self.log(f"工作目录: {self.work_dir}")
        self.log(f"配置: {json.dumps(config, indent=2, ensure_ascii=False)}")

    def log(self, message: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{ts}] {message}"
        print(msg)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    def step1_sampling(self, n_samples: int = 1000) -> pd.DataFrame:
        self.log("\n" + "=" * 70)
        self.log("步骤1: LHS 采样")
        self.log("=" * 70)

        from xv15_sampling import (
            ParameterBounds,
            LatinHypercubeSampler,
            analyze_design_space,
        )

        analyze_design_space()

        design_vars = [
            "翼根弦长",
            "翼中弦长",
            "翼尖弦长",
            "翼根扭转角",
            "翼中扭转角",
            "翼尖扭转角",
        ]

        bounds = ParameterBounds.get_bounds_array(design_vars)

        sampler = LatinHypercubeSampler(
            param_names=design_vars,
            bounds=bounds,
            seed=42,
        )

        df_samples = sampler.generate_samples(
            n_samples=n_samples,
            apply_constraints=True,
            max_attempts=20000,
        )

        df_samples["旋翼直径"] = 7620.0
        df_samples["叶片数"] = 3

        samples_file = os.path.join(self.sampling_dir, "design_samples.csv")
        df_samples.to_csv(samples_file, index=False, encoding="utf-8-sig")

        plot_file = os.path.join(self.sampling_dir, "sampling_distribution.png")
        sampler.plot_samples(df_samples, save_path=plot_file)

        self.results["step1"] = {
            "samples_file": samples_file,
            "n_samples": len(df_samples),
            "plot_file": plot_file,
        }

        self.log("✓ 步骤1完成")
        self.log(f"  生成样本: {len(df_samples)}")
        self.log(f"  输出文件: {samples_file}")
        return df_samples

    def step2_catia_modeling(
        self,
        df_samples: pd.DataFrame,
        n_models: Optional[int] = None,
        test_mode: bool = False,
    ) -> Optional[pd.DataFrame]:
        self.log("\n" + "=" * 70)
        self.log("步骤2: CATIA 批量建模")
        self.log("=" * 70)

        template_file = self.config.get("catia_template")
        if not template_file or not os.path.exists(template_file):
            self.log(f"✗ CATIA 模板不存在: {template_file}")
            return None

        if test_mode:
            df_samples = df_samples.head(10)
            self.log("测试模式: 仅处理前 10 个样本")
        elif n_models:
            df_samples = df_samples.head(n_models)
            self.log(f"处理前 {n_models} 个样本")

        from catia_batch_modeling import CATIABatchModeler

        modeler = CATIABatchModeler(
            template_path=template_file,
            output_dir=self.catia_dir,
        )

        df_results = modeler.batch_process(
            df=df_samples,
            save_catia=False,
            save_interval=20,
        )

        results_file = os.path.join(self.catia_dir, "batch_modeling_results.csv")
        df_results.to_csv(results_file, index=False, encoding="utf-8-sig")

        success_count = int(df_results["success"].sum())
        self.results["step2"] = {
            "results_file": results_file,
            "total": len(df_results),
            "success": success_count,
            "success_rate": success_count / max(len(df_results), 1) * 100.0,
        }

        self.log("✓ 步骤2完成")
        self.log(f"  总数: {len(df_results)}")
        self.log(f"  成功: {success_count}")
        return df_results

    def step3_bem_screening(self, df_samples: pd.DataFrame) -> Optional[pd.DataFrame]:
        self.log("\n" + "=" * 70)
        self.log("步骤3: BEM 低保真筛选")
        self.log("=" * 70)

        from xv15_bem_screening import XV15BEMScreener

        screener = XV15BEMScreener(
            design_point={
                "V_inf": 77.2,
                "rpm": 397,
                "rho": 1.225,
                "mu": 1.81e-5,
            }
        )

        bem_results_file = os.path.join(self.bem_dir, "bem_analysis_results.csv")
        df_bem_results = screener.batch_analyze(df_samples, save_path=bem_results_file)

        success_count = int(df_bem_results["success"].sum())
        if success_count == 0:
            self.log("✗ 步骤3失败: 没有成功的BEM结果")
            return None

        valid = df_bem_results[df_bem_results["success"] == True]
        self.results["step3"] = {
            "bem_results_file": bem_results_file,
            "total": len(df_bem_results),
            "success": success_count,
            "avg_efficiency": float(valid["eta_%"].mean()),
            "max_efficiency": float(valid["eta_%"].max()),
        }

        self.log("✓ 步骤3完成")
        self.log(f"  成功: {success_count}")
        self.log(f"  平均效率: {self.results['step3']['avg_efficiency']:.2f}%")
        self.log(f"  最高效率: {self.results['step3']['max_efficiency']:.2f}%")
        return df_bem_results

    def step4_select_top_designs(
        self,
        df_bem_results: pd.DataFrame,
        n_select: int = 200,
        min_efficiency: float = 75.0,
    ) -> Optional[pd.DataFrame]:
        self.log("\n" + "=" * 70)
        self.log(f"步骤4: 筛选 Top {n_select}")
        self.log("=" * 70)

        from xv15_bem_screening import XV15BEMScreener

        screener = XV15BEMScreener()
        df_selected = screener.select_top_designs(
            df_bem_results,
            n_select=n_select,
            min_efficiency=min_efficiency,
        )

        if len(df_selected) == 0:
            self.log("✗ 步骤4失败: 无设计满足效率阈值")
            return None

        selected_file = os.path.join(self.cfd_dir, f"top{n_select}_for_cfd.csv")
        df_selected.to_csv(selected_file, index=False, encoding="utf-8-sig")

        cfd_list_file = os.path.join(self.cfd_dir, "cfd_simulation_list.txt")
        with open(cfd_list_file, "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("CFD 仿真准备清单\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"筛选时间: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            f.write(f"设计数量: {len(df_selected)}\n")
            f.write(
                f"效率范围: {df_selected['eta_%'].min():.2f}% ~ "
                f"{df_selected['eta_%'].max():.2f}%\n\n"
            )

        self.results["step4"] = {
            "selected_file": selected_file,
            "cfd_list_file": cfd_list_file,
            "n_selected": len(df_selected),
            "efficiency_range": (
                float(df_selected["eta_%"].min()),
                float(df_selected["eta_%"].max()),
            ),
        }

        self.log("✓ 步骤4完成")
        self.log(f"  输出: {selected_file}")
        return df_selected

    def generate_final_report(self) -> str:
        self.log("\n" + "=" * 70)
        self.log("生成最终报告")
        self.log("=" * 70)

        report_file = os.path.join(self.work_dir, "final_report.txt")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("XV-15 螺旋桨优化最终报告\n")
            f.write("=" * 70 + "\n")
            f.write(f"生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            f.write(f"工作目录: {self.work_dir}\n\n")

            if "step1" in self.results:
                f.write("【步骤1】LHS 采样\n")
                f.write(f"样本数: {self.results['step1']['n_samples']}\n")
                f.write(f"文件: {self.results['step1']['samples_file']}\n\n")

            if "step2" in self.results:
                f.write("【步骤2】CATIA 批量建模\n")
                f.write(f"总数: {self.results['step2']['total']}\n")
                f.write(f"成功: {self.results['step2']['success']}\n\n")

            if "step3" in self.results:
                f.write("【步骤3】BEM 筛选\n")
                f.write(f"成功: {self.results['step3']['success']}\n")
                f.write(
                    f"效率: {self.results['step3']['avg_efficiency']:.2f}% "
                    f"~ {self.results['step3']['max_efficiency']:.2f}%\n\n"
                )

            if "step4" in self.results:
                f.write("【步骤4】Top 设计\n")
                f.write(f"数量: {self.results['step4']['n_selected']}\n")
                f.write(f"文件: {self.results['step4']['selected_file']}\n\n")

        self.log(f"✓ 报告已保存: {report_file}")
        return report_file

    def run_complete_workflow(
        self,
        n_samples: int = 1000,
        n_select: int = 200,
        skip_catia: bool = False,
    ) -> bool:
        try:
            df_samples = self.step1_sampling(n_samples=n_samples)

            if not skip_catia:
                self.step2_catia_modeling(df_samples)
            else:
                self.log("跳过 CATIA 批量建模")

            df_bem_results = self.step3_bem_screening(df_samples)
            if df_bem_results is None:
                self.log("✗ 工作流中断: BEM 筛选失败")
                return False

            df_selected = self.step4_select_top_designs(
                df_bem_results,
                n_select=n_select,
                min_efficiency=75.0,
            )
            if df_selected is None:
                self.log("✗ 工作流中断: 无合格设计")
                return False

            self.generate_final_report()
            self.log("✓ 完整流程结束")
            return True
        except Exception as e:
            self.log(f"✗ 工作流异常: {e}")
            return False


if __name__ == "__main__":
    CONFIG = {
        "work_dir": r"D:\17484\Documents\OneDrive\Desktop\XV15_Optimization",
        "catia_template": r"D:\17484\Documents\OneDrive\Desktop\XV-15叶片总成\XV-15 ASM.CATProduct",
    }

    workflow = XV15OptimizationWorkflow(CONFIG)

    print("\n请选择运行模式:")
    print("1. 完整流程 (采样1000 + CATIA建模 + BEM筛选 + Top200)")
    print("2. 快速测试 (采样100 + BEM筛选，跳过CATIA)")
    print("3. 仅BEM筛选 (使用已有采样数据)")

    choice = input("\n请输入选择 (1/2/3): ").strip()

    if choice == "1":
        confirm = input("确认运行完整流程? (yes/no): ").strip().lower()
        if confirm == "yes":
            workflow.run_complete_workflow(
                n_samples=1000,
                n_select=200,
                skip_catia=False,
            )
    elif choice == "2":
        workflow.run_complete_workflow(
            n_samples=100,
            n_select=50,
            skip_catia=True,
        )
    elif choice == "3":
        samples_file = input("请输入采样数据CSV路径: ").strip()
        if os.path.exists(samples_file):
            df_samples = pd.read_csv(samples_file, encoding="utf-8-sig")
            df_bem_results = workflow.step3_bem_screening(df_samples)
            if df_bem_results is not None:
                workflow.step4_select_top_designs(df_bem_results, n_select=200)
                workflow.generate_final_report()
        else:
            print(f"文件不存在: {samples_file}")
    else:
        print("无效选择")
