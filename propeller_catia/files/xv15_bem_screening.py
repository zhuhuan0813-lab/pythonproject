"""
XV-15 螺旋桨 BEM 低保真筛选
"""

from __future__ import annotations

import os
from typing import Dict

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None

from bem_propeller import (
    PropellerGeometry,
    FlowConditions,
    BEMSolver,
    AirfoilData,
    build_pyfoil_polar,
    PolarTable,
)


class XV15GeometryExtractor:
    @staticmethod
    def extract_from_params(params: Dict[str, float], n_stations: int = 30) -> PropellerGeometry:
        D = params.get("旋翼直径", 7620.0) / 1000.0
        n_blades = int(params.get("叶片数", 3))
        hub_ratio = 0.15

        c_root = params.get("翼根弦长", 431.8) / 1000.0
        c_mid = params.get("翼中弦长", 368.3) / 1000.0
        c_tip = params.get("翼尖弦长", 304.8) / 1000.0

        twist_root = params.get("翼根扭转角", 40.25)
        twist_mid = params.get("翼中扭转角", 18.25)
        twist_tip = params.get("翼尖扭转角", -3.75)

        R = D / 2.0
        r_hub = R * hub_ratio
        r_tip = R

        r_root = 0.25 * R
        r_mid = 0.625 * R

        radius = np.linspace(r_hub, r_tip, n_stations)
        chord = np.zeros(n_stations)
        twist = np.zeros(n_stations)

        for i, r in enumerate(radius):
            if r <= r_root:
                chord[i] = c_root
                twist[i] = twist_root
            elif r <= r_mid:
                t = (r - r_root) / (r_mid - r_root)
                chord[i] = c_root * (1 - t) + c_mid * t
                twist[i] = twist_root * (1 - t) + twist_mid * t
            else:
                t = (r - r_mid) / (r_tip - r_mid)
                chord[i] = c_mid * (1 - t) + c_tip * t
                twist[i] = twist_mid * (1 - t) + twist_tip * t

        idx_75 = np.argmin(np.abs(radius / R - 0.75))
        beta_75 = np.deg2rad(twist[idx_75])
        pitch = 2 * np.pi * radius[idx_75] * np.tan(beta_75)

        return PropellerGeometry(
            D=D,
            n_blades=n_blades,
            hub_ratio=hub_ratio,
            pitch=pitch,
            chord=chord,
            twist=twist,
            radius=radius,
        )


class XV15BEMScreener:
    def __init__(self, design_point: Dict[str, float] | None = None):
        if design_point is None:
            design_point = {"V_inf": 77.2, "rpm": 397, "rho": 1.225, "mu": 1.81e-5}
        self.design_point = design_point

        # 优先使用 pyfoil 生成极曲线，失败则回退到简化模型
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "数据"))
        root_dat = os.path.join(base_dir, "NACA64-528_300.dat")
        mid_dat = os.path.join(base_dir, "NACA64-118_300.dat")
        tip_dat = os.path.join(base_dir, "NACA64-208_300.dat")

        xfoil_path = r"E:\XFOIL6.99\xfoil.exe"
        self.airfoil_root = build_pyfoil_polar(root_dat, xfoil_path=xfoil_path) or AirfoilData(
            "NACA64-528", cd0=0.010, k=0.020
        )
        self.airfoil_mid = build_pyfoil_polar(mid_dat, xfoil_path=xfoil_path) or AirfoilData(
            "NACA64-118", cd0=0.010, k=0.020
        )
        self.airfoil_tip = build_pyfoil_polar(tip_dat, xfoil_path=xfoil_path) or AirfoilData(
            "NACA64-208", cd0=0.012, k=0.025
        )

    def analyze_single(self, case_id: int, params: Dict[str, float]) -> Dict:
        result = {
            "case_id": case_id,
            "success": False,
            "翼根弦长": params.get("翼根弦长", np.nan),
            "翼中弦长": params.get("翼中弦长", np.nan),
            "翼尖弦长": params.get("翼尖弦长", np.nan),
            "翼根扭转角": params.get("翼根扭转角", np.nan),
            "翼中扭转角": params.get("翼中扭转角", np.nan),
            "翼尖扭转角": params.get("翼尖扭转角", np.nan),
        }

        try:
            geom = XV15GeometryExtractor.extract_from_params(params)
            flow = FlowConditions(
                V_inf=self.design_point["V_inf"],
                rpm=self.design_point["rpm"],
                rho=self.design_point.get("rho", 1.225),
                mu=self.design_point.get("mu", 1.81e-5),
            )

            def airfoil_selector(alpha_deg: float, r_ratio: float):
                if r_ratio <= 0.45:
                    return self.airfoil_root.cl_cd(alpha_deg)
                if r_ratio <= 0.8:
                    return self.airfoil_mid.cl_cd(alpha_deg)
                return self.airfoil_tip.cl_cd(alpha_deg)

            solver = BEMSolver(geom, flow, airfoil=airfoil_selector, n_iter=60, tol=1e-4)
            bem = solver.solve(verbose=False)

            result.update(
                {
                    "T_N": bem["T"],
                    "P_kW": bem["P"] / 1000.0,
                    "eta_%": bem["eta"] * 100.0,
                    "CT": bem["CT"],
                    "CP": bem["CP"],
                    "J": bem["J"],
                    "success": True,
                }
            )
        except Exception as e:
            result["error"] = str(e)

        return result

    def batch_analyze(self, df_designs: pd.DataFrame, save_path: str | None = None) -> pd.DataFrame:
        results = []
        for i in range(len(df_designs)):
            params = df_designs.iloc[i].to_dict()
            results.append(self.analyze_single(i + 1, params))

        df_results = pd.DataFrame(results)
        if save_path:
            df_results.to_csv(save_path, index=False, encoding="utf-8-sig")
        return df_results

    def select_top_designs(
        self,
        df_results: pd.DataFrame,
        n_select: int = 200,
        min_efficiency: float = 75.0,
    ) -> pd.DataFrame:
        df_valid = df_results[df_results["success"] == True].copy()
        df_valid = df_valid[df_valid["eta_%"] >= min_efficiency]
        df_sorted = df_valid.sort_values("eta_%", ascending=False)
        return df_sorted.head(n_select)

    def plot_results(self, df_results: pd.DataFrame, output_dir: str | None = None):
        if plt is None:
            return
        df_valid = df_results[df_results["success"] == True]
        if df_valid.empty:
            return
        plt.figure(figsize=(8, 6))
        plt.hist(df_valid["eta_%"], bins=30, edgecolor="black", alpha=0.7)
        plt.xlabel("效率 (%)")
        plt.ylabel("频数")
        plt.title("BEM 效率分布")
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            path = os.path.join(output_dir, "screening_results.png")
            plt.savefig(path, dpi=200, bbox_inches="tight")
        plt.show()


if __name__ == "__main__":
    # 优先使用当前目录采样文件，否则使用默认输出路径
    candidates = [
        os.path.join(os.getcwd(), "xv15_design_samples.csv"),
        os.path.join(os.path.dirname(__file__), "xv15_design_samples.csv"),
        os.path.join(os.path.dirname(__file__), "..", "1_Sampling", "design_samples.csv"),
    ]
    samples_path = None
    for p in candidates:
        if os.path.exists(p):
            samples_path = p
            break
    if samples_path is None:
        raise FileNotFoundError(
            "未找到采样文件，请先运行 xv15_sampling.py 生成 "
            "xv15_design_samples.csv 或 1_Sampling/design_samples.csv"
        )

    df = pd.read_csv(samples_path, encoding="utf-8-sig")
    screener = XV15BEMScreener()
    df_res = screener.batch_analyze(df, save_path="bem_results.csv")
    top = screener.select_top_designs(df_res, n_select=200, min_efficiency=75.0)
    top.to_csv("top200.csv", index=False, encoding="utf-8-sig")
