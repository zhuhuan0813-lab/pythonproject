"""
XV-15倾转旋翼螺旋桨参数化设计与优化
包含参数定义、拉丁超立方采样、约束检查

作者: 自动生成
日期: 2026-02-08
参考: XV-15倾转旋翼机原型数据
"""

import numpy as np
from scipy.stats import qmc
import pandas as pd
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


@dataclass
class XV15Parameters:
    """XV-15螺旋桨设计参数"""
    
    # 基本几何
    旋翼直径: float = 7620.0  # mm (原型值)
    
    # 三个截面的弦长
    翼根弦长: float = 431.8   # mm
    翼中弦长: float = 368.3   # mm
    翼尖弦长: float = 304.8   # mm
    
    # 三个截面的扭转角
    翼根扭转角: float = 40.25  # deg
    翼中扭转角: float = 18.25  # deg
    翼尖扭转角: float = -3.75  # deg
    
    # 桨叶固定参数（通常不变）
    桨叶数: int = 3
    桨根直径: float = 1.5  # deg (实际可能是尺寸，需核实)
    翼根所在位置比例: float = 0.5
    桨根去除部分长度: float = 350  # mm
    桨叶固定翼根x方向去除比例: float = 0.5
    桨叶固定翼根y轴方向去除比例: float = 0.25
    
    def __post_init__(self):
        """参数验证"""
        # 检查弦长递减
        if not (self.翼根弦长 >= self.翼中弦长 >= self.翼尖弦长 > 0):
            raise ValueError("弦长应从根部到尖部递减")
        
        # 检查扭转角递减（根部大，尖部小甚至负）
        if not (self.翼根扭转角 > self.翼中扭转角 > self.翼尖扭转角):
            raise ValueError("扭转角应从根部到尖部递减")


class ParameterBounds:
    """参数上下限定义（基于文献和工程经验）"""
    
    # 参考: NASA Technical Memorandum 81244 "XV-15 Tilt Rotor Research Aircraft"
    # 参考: Prouty "Helicopter Performance, Stability and Control"
    
    BOUNDS = {
        # 弦长 (基于原型 ±30%，保证气动性能)
        '翼根弦长': (300.0, 560.0),   # 原型431.8 mm
        '翼中弦长': (250.0, 480.0),   # 原型368.3 mm
        '翼尖弦长': (210.0, 400.0),   # 原型304.8 mm
        
        # 扭转角 (基于倾转旋翼设计经验)
        '翼根扭转角': (30.0, 50.0),   # 原型40.25 deg (桨叶根部需要大迎角)
        '翼中扭转角': (10.0, 25.0),   # 原型18.25 deg
        '翼尖扭转角': (-10.0, 5.0),   # 原型-3.75 deg (叶尖可以负扭以减小噪音)
        
        # 旋翼直径（通常固定，但可微调 ±5%）
        '旋翼直径': (7200.0, 8000.0), # 原型7620 mm (25英尺)
    }
    
    # 约束条件
    CONSTRAINTS = {
        # 1. 弦长递减约束
        'chord_taper': lambda p: (
            p['翼根弦长'] >= p['翼中弦长'] >= p['翼尖弦长']
        ),
        
        # 2. 扭转角递减约束
        'twist_taper': lambda p: (
            p['翼根扭转角'] > p['翼中扭转角'] > p['翼尖扭转角']
        ),
        
        # 3. 锥削比约束（避免过度尖削）
        'taper_ratio': lambda p: (
            p['翼尖弦长'] / p['翼根弦长'] >= 0.4  # 锥削比 > 0.4
        ),
        
        # 4. 扭转角变化率约束（避免突变）
        'twist_gradient': lambda p: (
            (p['翼根扭转角'] - p['翼尖扭转角']) <= 60.0  # 总扭转变化 < 60度
        ),
        
        # 5. 平均弦长约束（保持实度合理）
        'avg_chord': lambda p: (
            250.0 <= (p['翼根弦长'] + p['翼中弦长'] + p['翼尖弦长'])/3 <= 450.0
        ),
    }
    
    @classmethod
    def get_bounds_array(cls, param_names: List[str]) -> np.ndarray:
        """
        获取参数边界数组
        
        返回:
            bounds: (n_params, 2) 数组，[下限, 上限]
        """
        bounds = []
        for name in param_names:
            if name in cls.BOUNDS:
                bounds.append(cls.BOUNDS[name])
            else:
                raise ValueError(f"参数 {name} 没有定义边界")
        return np.array(bounds)
    
    @classmethod
    def check_constraints(cls, params: Dict[str, float], verbose: bool = False) -> bool:
        """
        检查参数是否满足所有约束
        
        参数:
            params: 参数字典
            verbose: 是否打印详细信息
        
        返回:
            是否满足所有约束
        """
        all_satisfied = True
        
        for constraint_name, constraint_func in cls.CONSTRAINTS.items():
            satisfied = constraint_func(params)
            if not satisfied:
                all_satisfied = False
                if verbose:
                    print(f"✗ 约束失败: {constraint_name}")
                    print(f"  参数: {params}")
        
        return all_satisfied


class LatinHypercubeSampler:
    """拉丁超立方采样器"""
    
    def __init__(self, param_names: List[str], bounds: np.ndarray, 
                 seed: int = 42):
        """
        初始化采样器
        
        参数:
            param_names: 参数名称列表
            bounds: 参数边界 (n_params, 2)
            seed: 随机种子
        """
        self.param_names = param_names
        self.bounds = bounds
        self.n_params = len(param_names)
        self.seed = seed
        
        # 创建拉丁超立方采样器
        self.sampler = qmc.LatinHypercube(d=self.n_params, seed=seed)
    
    def generate_samples(self, n_samples: int, 
                        apply_constraints: bool = True,
                        max_attempts: int = 10000) -> pd.DataFrame:
        """
        生成样本
        
        参数:
            n_samples: 样本数量
            apply_constraints: 是否应用约束（会增加计算时间）
            max_attempts: 最大尝试次数
        
        返回:
            DataFrame包含所有样本
        """
        print(f"\n{'='*70}")
        print(f"拉丁超立方采样")
        print(f"{'='*70}")
        print(f"目标样本数: {n_samples}")
        print(f"设计变量数: {self.n_params}")
        print(f"应用约束: {apply_constraints}")
        
        if not apply_constraints:
            # 不考虑约束，直接生成
            samples_unit = self.sampler.random(n_samples)
            samples = qmc.scale(samples_unit, self.bounds[:, 0], self.bounds[:, 1])
            
            df = pd.DataFrame(samples, columns=self.param_names)
            print(f"✓ 生成 {n_samples} 个样本")
            return df
        
        # 考虑约束，需要筛选
        valid_samples = []
        attempts = 0
        
        # 使用更大的批次生成
        batch_size = n_samples * 5
        
        while len(valid_samples) < n_samples and attempts < max_attempts:
            # 生成一批候选样本
            samples_unit = self.sampler.random(batch_size)
            samples = qmc.scale(samples_unit, self.bounds[:, 0], self.bounds[:, 1])
            
            # 检查每个样本
            for sample in samples:
                params = dict(zip(self.param_names, sample))
                
                if ParameterBounds.check_constraints(params):
                    valid_samples.append(sample)
                    
                    if len(valid_samples) >= n_samples:
                        break
            
            attempts += batch_size
            
            if len(valid_samples) % 100 == 0:
                print(f"  进度: {len(valid_samples)}/{n_samples} (尝试: {attempts})")
        
        if len(valid_samples) < n_samples:
            print(f"⚠️  警告: 仅生成 {len(valid_samples)} 个有效样本（目标{n_samples}）")
            print(f"   考虑放宽约束或增加max_attempts")
        else:
            print(f"✓ 成功生成 {n_samples} 个有效样本")
        
        # 只取需要的数量
        valid_samples = valid_samples[:n_samples]
        
        df = pd.DataFrame(valid_samples, columns=self.param_names)
        return df
    
    def save_samples(self, df: pd.DataFrame, filename: str):
        """保存样本到CSV"""
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"✓ 样本已保存至: {filename}")
    
    def plot_samples(self, df: pd.DataFrame, save_path: str = None):
        """可视化样本分布"""
        n_params = len(self.param_names)
        
        fig, axes = plt.subplots(n_params, n_params, 
                                figsize=(3*n_params, 3*n_params))
        
        for i in range(n_params):
            for j in range(n_params):
                ax = axes[i, j] if n_params > 1 else axes
                
                if i == j:
                    # 对角线：直方图
                    ax.hist(df[self.param_names[i]], bins=20, 
                           edgecolor='black', alpha=0.7)
                    ax.set_ylabel('频数')
                else:
                    # 非对角线：散点图
                    ax.scatter(df[self.param_names[j]], 
                             df[self.param_names[i]], 
                             alpha=0.5, s=10)
                
                if i == n_params - 1:
                    ax.set_xlabel(self.param_names[j])
                if j == 0:
                    ax.set_ylabel(self.param_names[i])
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✓ 采样分布图已保存至: {save_path}")
        
        plt.show()


def create_baseline_xv15() -> XV15Parameters:
    """创建XV-15原型参数"""
    return XV15Parameters()


def analyze_design_space():
    """分析设计空间"""
    print("\n" + "="*70)
    print("XV-15螺旋桨设计空间分析")
    print("="*70)
    
    baseline = create_baseline_xv15()
    
    print("\n【原型参数】")
    for key, value in asdict(baseline).items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
    
    print("\n【设计变量边界】")
    for param, (lower, upper) in ParameterBounds.BOUNDS.items():
        print(f"  {param}:")
        print(f"    下限: {lower:.2f}")
        print(f"    上限: {upper:.2f}")
        print(f"    范围: {upper - lower:.2f}")
    
    print("\n【约束条件】")
    for i, constraint_name in enumerate(ParameterBounds.CONSTRAINTS.keys(), 1):
        print(f"  {i}. {constraint_name}")
    
    # 检查原型是否满足约束
    print("\n【原型约束检查】")
    baseline_dict = {
        '翼根弦长': baseline.翼根弦长,
        '翼中弦长': baseline.翼中弦长,
        '翼尖弦长': baseline.翼尖弦长,
        '翼根扭转角': baseline.翼根扭转角,
        '翼中扭转角': baseline.翼中扭转角,
        '翼尖扭转角': baseline.翼尖扭转角,
        '旋翼直径': baseline.旋翼直径,
    }
    
    if ParameterBounds.check_constraints(baseline_dict, verbose=True):
        print("✓ 原型满足所有约束")
    else:
        print("✗ 原型不满足某些约束（需要调整约束定义）")


# ============================================================================
# 主程序
# ============================================================================

if __name__ == "__main__":
    
    # 1. 分析设计空间
    analyze_design_space()
    
    # 2. 设置采样参数
    print("\n" + "="*70)
    print("设置采样参数")
    print("="*70)
    
    # 设计变量（可根据研究重点选择）
    design_vars = [
        '翼根弦长',
        '翼中弦长', 
        '翼尖弦长',
        '翼根扭转角',
        '翼中扭转角',
        '翼尖扭转角',
        # '旋翼直径',  # 可选：如果直径也要优化
    ]
    
    print(f"设计变量 ({len(design_vars)}个):")
    for var in design_vars:
        print(f"  - {var}")
    
    # 获取边界
    bounds = ParameterBounds.get_bounds_array(design_vars)
    
    # 3. 创建采样器
    sampler = LatinHypercubeSampler(
        param_names=design_vars,
        bounds=bounds,
        seed=42
    )
    
    # 4. 生成样本
    n_samples = 1000  # 生成1000个候选方案
    
    df_samples = sampler.generate_samples(
        n_samples=n_samples,
        apply_constraints=True,  # 应用约束
        max_attempts=20000
    )
    
    # 5. 添加固定参数
    df_samples['旋翼直径'] = 7620.0  # 固定直径
    df_samples['桨叶数'] = 3
    
    # 6. 保存样本
    sampler.save_samples(df_samples, 'xv15_design_samples.csv')
    
    # 7. 可视化
    sampler.plot_samples(df_samples, 'xv15_sampling_distribution.png')
    
    # 8. 统计信息
    print("\n" + "="*70)
    print("样本统计")
    print("="*70)
    print(df_samples.describe())
    
    print("\n" + "="*70)
    print("采样完成！")
    print("="*70)
    print(f"生成样本数: {len(df_samples)}")
    print(f"输出文件: xv15_design_samples.csv")
    print(f"可视化图: xv15_sampling_distribution.png")
