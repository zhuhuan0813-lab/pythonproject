"""
XV-15 参数化采样 (LHS) 与约束检查
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - optional
    plt = None


@dataclass
class XV15Parameters:
    # 基准几何
    旋翼直径: float = 7620.0  # mm
    翼根弦长: float = 431.8
    翼中弦长: float = 368.3
    翼尖弦长: float = 304.8
    翼根扭转角: float = 40.25  # deg
    翼中扭转角: float = 18.25
    翼尖扭转角: float = -3.75
    叶片数: int = 3

    def __post_init__(self):
        if not (self.翼根弦长 >= self.翼中弦长 >= self.翼尖弦长 > 0):
            raise ValueError("弦长应从根部到尖部递减")
        if not (self.翼根扭转角 > self.翼中扭转角 > self.翼尖扭转角):
            raise ValueError("扭转角应从根部到尖部递减")


class ParameterBounds:
    """
    参数上下限 (由用户指定)
    """

    BOUNDS: Dict[str, Tuple[float, float]] = {
        "翼根弦长": (300.0, 560.0),
        "翼中弦长": (250.0, 480.0),
        "翼尖弦长": (210.0, 400.0),
        "翼根扭转角": (30.0, 50.0),
        "翼中扭转角": (10.0, 25.0),
        "翼尖扭转角": (-10.0, 5.0),
    }

    CONSTRAINTS = {
        "chord_taper": lambda p: (
            p["翼根弦长"] >= p["翼中弦长"] >= p["翼尖弦长"]
        ),
        "twist_taper": lambda p: (
            p["翼根扭转角"] > p["翼中扭转角"] > p["翼尖扭转角"]
        ),
        "taper_ratio": lambda p: (p["翼尖弦长"] / p["翼根弦长"] >= 0.4),
        "twist_gradient": lambda p: (
            (p["翼根扭转角"] - p["翼尖扭转角"]) <= 60.0
        ),
        "avg_chord": lambda p: (
            250.0
            <= (p["翼根弦长"] + p["翼中弦长"] + p["翼尖弦长"]) / 3
            <= 450.0
        ),
    }

    @classmethod
    def get_bounds_array(cls, param_names: List[str]) -> np.ndarray:
        bounds = []
        for name in param_names:
            if name not in cls.BOUNDS:
                raise ValueError(f"参数 {name} 没有边界定义")
            bounds.append(cls.BOUNDS[name])
        return np.asarray(bounds, dtype=float)

    @classmethod
    def check_constraints(cls, params: Dict[str, float], verbose: bool = False) -> bool:
        all_ok = True
        for name, func in cls.CONSTRAINTS.items():
            ok = bool(func(params))
            if not ok:
                all_ok = False
                if verbose:
                    print(f"约束失败: {name}, params={params}")
        return all_ok


def _lhs_unit(n: int, d: int, rng: np.random.Generator) -> np.ndarray:
    """
    简单 LHS: 每维分成 n 个箱, 每箱取一个随机点, 打乱组合
    """
    cut = np.linspace(0.0, 1.0, n + 1)
    u = rng.random((n, d))
    a = cut[:n]
    b = cut[1:]
    rd = u * (b - a)[:, None] + a[:, None]
    out = np.zeros_like(rd)
    for j in range(d):
        order = rng.permutation(n)
        out[:, j] = rd[order, j]
    return out


class LatinHypercubeSampler:
    def __init__(self, param_names: List[str], bounds: np.ndarray, seed: int = 42):
        self.param_names = param_names
        self.bounds = bounds
        self.n_params = len(param_names)
        self.rng = np.random.default_rng(seed)

    def generate_samples(
        self,
        n_samples: int,
        apply_constraints: bool = True,
        max_attempts: int = 10000,
    ) -> pd.DataFrame:
        print("=" * 70)
        print("Latin Hypercube Sampling")
        print("=" * 70)
        print(f"目标样本数: {n_samples}")
        print(f"变量数: {self.n_params}")

        if not apply_constraints:
            unit = _lhs_unit(n_samples, self.n_params, self.rng)
            samples = self._scale(unit)
            return pd.DataFrame(samples, columns=self.param_names)

        valid = []
        attempts = 0
        batch_size = max(100, n_samples * 5)

        while len(valid) < n_samples and attempts < max_attempts:
            unit = _lhs_unit(batch_size, self.n_params, self.rng)
            samples = self._scale(unit)

            for row in samples:
                params = dict(zip(self.param_names, row))
                if ParameterBounds.check_constraints(params):
                    valid.append(row)
                    if len(valid) >= n_samples:
                        break

            attempts += batch_size
            if len(valid) % 100 == 0:
                print(f"进度: {len(valid)}/{n_samples} (尝试: {attempts})")

        if len(valid) < n_samples:
            print(
                f"警告: 仅生成 {len(valid)} 个有效样本, "
                f"可考虑放宽约束或提高 max_attempts"
            )

        valid = np.asarray(valid[:n_samples], dtype=float)
        return pd.DataFrame(valid, columns=self.param_names)

    def _scale(self, unit: np.ndarray) -> np.ndarray:
        lower = self.bounds[:, 0]
        upper = self.bounds[:, 1]
        return lower + unit * (upper - lower)

    def plot_samples(self, df: pd.DataFrame, save_path: str | None = None):
        if plt is None:
            print("matplotlib 不可用, 跳过绘图")
            return

        n = len(self.param_names)
        fig, axes = plt.subplots(n, n, figsize=(3 * n, 3 * n))

        for i in range(n):
            for j in range(n):
                ax = axes[i, j] if n > 1 else axes
                if i == j:
                    ax.hist(df[self.param_names[i]], bins=20, edgecolor="black", alpha=0.7)
                else:
                    ax.scatter(
                        df[self.param_names[j]],
                        df[self.param_names[i]],
                        alpha=0.5,
                        s=10,
                    )

                if i == n - 1:
                    ax.set_xlabel(self.param_names[j])
                if j == 0:
                    ax.set_ylabel(self.param_names[i])

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches="tight")
            print(f"采样分布图已保存: {save_path}")
        plt.show()


def create_baseline_xv15() -> XV15Parameters:
    return XV15Parameters()


def analyze_design_space():
    print("\n" + "=" * 70)
    print("XV-15 设计空间概览")
    print("=" * 70)

    base = create_baseline_xv15()
    print("\n【基准参数】")
    for k, v in asdict(base).items():
        print(f"  {k}: {v}")

    print("\n【参数边界】")
    for k, (lo, hi) in ParameterBounds.BOUNDS.items():
        print(f"  {k}: {lo:.2f} ~ {hi:.2f}")

    print("\n【约束】")
    for i, name in enumerate(ParameterBounds.CONSTRAINTS.keys(), 1):
        print(f"  {i}. {name}")


if __name__ == "__main__":
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
    sampler = LatinHypercubeSampler(design_vars, bounds, seed=42)
    df_samples = sampler.generate_samples(
        n_samples=1000, apply_constraints=True, max_attempts=20000
    )

    df_samples["旋翼直径"] = 7620.0
    df_samples["叶片数"] = 3
    df_samples.to_csv("xv15_design_samples.csv", index=False, encoding="utf-8-sig")
    sampler.plot_samples(df_samples, "xv15_sampling_distribution.png")
    print("采样完成")
