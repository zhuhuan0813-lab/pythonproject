"""
简化 BEM 求解器 (低保真筛选用途)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any, Sequence

import numpy as np


@dataclass
class PropellerGeometry:
    D: float
    n_blades: int
    hub_ratio: float
    pitch: float
    chord: np.ndarray
    twist: np.ndarray
    radius: np.ndarray


@dataclass
class FlowConditions:
    V_inf: float
    rpm: float
    rho: float = 1.225
    mu: float = 1.81e-5


class AirfoilData:
    """
    简化翼型极曲线: Cl = 2*pi*alpha(rad) 截断, Cd = Cd0 + k*Cl^2
    """

    def __init__(self, name: str, cd0: float = 0.01, k: float = 0.02, cl_max: float = 1.4):
        self.name = name
        self.cd0 = cd0
        self.k = k
        self.cl_max = cl_max

    def cl_cd(self, alpha_deg: float, re: float | None = None) -> Tuple[float, float]:
        alpha_rad = np.deg2rad(alpha_deg)
        cl = 2.0 * np.pi * alpha_rad
        cl = float(np.clip(cl, -self.cl_max, self.cl_max))
        cd = self.cd0 + self.k * cl * cl
        return cl, cd


class PolarTable:
    """
    简单极曲线表 (alpha -> Cl/Cd)，用于插值
    """

    def __init__(self, alpha_deg: Sequence[float], cl: Sequence[float], cd: Sequence[float]):
        self.alpha_deg = np.asarray(alpha_deg, dtype=float)
        self.cl = np.asarray(cl, dtype=float)
        self.cd = np.asarray(cd, dtype=float)

        if len(self.alpha_deg) < 2:
            raise ValueError("PolarTable 需要至少两个攻角点")

        order = np.argsort(self.alpha_deg)
        self.alpha_deg = self.alpha_deg[order]
        self.cl = self.cl[order]
        self.cd = self.cd[order]

    def cl_cd(self, alpha_deg: float, re: float | None = None) -> Tuple[float, float]:
        cl = np.interp(alpha_deg, self.alpha_deg, self.cl)
        cd = np.interp(alpha_deg, self.alpha_deg, self.cd)
        return float(cl), float(cd)


def _try_import_pyfoil():
    try:
        import pyfoil  # type: ignore
        return pyfoil
    except Exception:
        return None


def _extract_polar_arrays(res: Any) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    尝试从不同返回格式中提取 alpha/cl/cd
    """
    if res is None:
        return None

    # dict-like
    for keys in (("alpha", "cl", "cd"), ("alpha_deg", "cl", "cd"), ("a", "cl", "cd")):
        if isinstance(res, dict) and all(k in res for k in keys):
            return np.asarray(res[keys[0]]), np.asarray(res[keys[1]]), np.asarray(res[keys[2]])

    # object with attributes
    for keys in (("alpha", "cl", "cd"), ("alpha_deg", "cl", "cd")):
        if all(hasattr(res, k) for k in keys):
            return (
                np.asarray(getattr(res, keys[0])),
                np.asarray(getattr(res, keys[1])),
                np.asarray(getattr(res, keys[2])),
            )

    return None


def build_pyfoil_polar(
    dat_path: Optional[str] = None,
    airfoil_name: Optional[str] = None,
    xfoil_path: Optional[str] = None,
    re: float = 1.0e6,
    mach: float = 0.1,
    alpha_start: float = -10.0,
    alpha_end: float = 20.0,
    alpha_step: float = 1.0,
) -> Optional[PolarTable]:
    """
    使用 pyfoil 生成极曲线 (若不可用则返回 None)
    """
    pyfoil = _try_import_pyfoil()
    if pyfoil is None:
        return None

    # 尝试获取 xfoil 模块
    xfoil_mod = None
    try:
        import pyfoil.xfoil as xfoil_mod  # type: ignore
    except Exception:
        xfoil_mod = getattr(pyfoil, "xfoil", None)

    if xfoil_mod is None:
        return None

    # 尝试找到 XFoil 类
    xfoil_cls = None
    for name in ("XFoil", "Xfoil", "XFOIL"):
        if hasattr(xfoil_mod, name):
            xfoil_cls = getattr(xfoil_mod, name)
            break
    if xfoil_cls is None:
        return None

    try:
        if xfoil_path:
            xf = xfoil_cls(xfoil_path)
        else:
            xf = xfoil_cls()
    except Exception:
        return None

    # 尝试加载翼型
    loaded = False
    if dat_path:
        for m in ("points_from_dat", "load_dat", "read_dat", "set_airfoil_from_dat", "load_airfoil"):
            if hasattr(xf, m):
                try:
                    getattr(xf, m)(dat_path)
                    loaded = True
                    break
                except Exception:
                    continue
    if not loaded and airfoil_name:
        for m in ("set_airfoil", "load_airfoil", "from_airfoil", "set_geometry"):
            if hasattr(xf, m):
                try:
                    getattr(xf, m)(airfoil_name)
                    loaded = True
                    break
                except Exception:
                    continue

    if not loaded:
        return None

    # 尝试运行极曲线
    res = None
    if hasattr(xf, "run_polar"):
        for kwargs in (
            dict(almin=alpha_start, almax=alpha_end, alint=alpha_step, mach=mach, Re=re),
            dict(alpha_start=alpha_start, alpha_end=alpha_end, alpha_step=alpha_step, mach=mach, Re=re),
            dict(alpha_start=alpha_start, alpha_end=alpha_end, alpha_step=alpha_step, mach=mach, re=re),
        ):
            try:
                res = xf.run_polar(**kwargs)
                break
            except Exception:
                continue

    if res is None and hasattr(xf, "polar"):
        try:
            res = xf.polar(alpha_start, alpha_end, alpha_step, re, mach)
        except Exception:
            res = None

    data = _extract_polar_arrays(res)
    if data is None:
        return None

    alpha, cl, cd = data
    return PolarTable(alpha, cl, cd)


class BEMSolver:
    def __init__(
        self,
        geom: PropellerGeometry,
        flow: FlowConditions,
        airfoil,
        n_iter: int = 60,
        tol: float = 1e-4,
    ):
        self.geom = geom
        self.flow = flow
        self.airfoil = airfoil
        self.n_iter = n_iter
        self.tol = tol

    def solve(self, verbose: bool = False) -> Dict[str, float]:
        rho = self.flow.rho
        V_inf = self.flow.V_inf
        omega = 2.0 * np.pi * self.flow.rpm / 60.0

        r = self.geom.radius
        chord = self.geom.chord
        twist = self.geom.twist
        B = self.geom.n_blades
        R = self.geom.D / 2.0

        dr = np.gradient(r)
        T = 0.0
        Q = 0.0

        for i in range(len(r)):
            ri = r[i]
            if ri <= 1e-6:
                continue

            sigma = B * chord[i] / (2.0 * np.pi * ri)
            a = 0.3
            a_prime = 0.01

            for _ in range(self.n_iter):
                V_axial = V_inf * (1 - a)
                V_tan = omega * ri * (1 + a_prime)
                phi = np.arctan2(V_axial, V_tan)
                alpha = twist[i] - np.rad2deg(phi)

                if callable(self.airfoil):
                    cl, cd = self.airfoil(alpha, ri / R)
                else:
                    cl, cd = self.airfoil.cl_cd(alpha)
                cn = cl * np.cos(phi) - cd * np.sin(phi)
                ct = cl * np.sin(phi) + cd * np.cos(phi)

                a_new = 1.0 / (1.0 + (4.0 * np.sin(phi) ** 2) / (sigma * cn + 1e-9))
                a_prime_new = 1.0 / (
                    (4.0 * np.sin(phi) * np.cos(phi)) / (sigma * ct + 1e-9) - 1.0
                )

                if abs(a_new - a) < self.tol and abs(a_prime_new - a_prime) < self.tol:
                    a, a_prime = a_new, a_prime_new
                    break
                a, a_prime = a_new, a_prime_new

            V_rel = np.sqrt(V_axial**2 + V_tan**2)
            dL = 0.5 * rho * V_rel**2 * chord[i] * cl * dr[i]
            dD = 0.5 * rho * V_rel**2 * chord[i] * cd * dr[i]

            dT = (dL * np.cos(phi) - dD * np.sin(phi)) * B
            dQ = (dL * np.sin(phi) + dD * np.cos(phi)) * ri * B
            T += dT
            Q += dQ

        P = Q * omega
        A = np.pi * R**2
        J = V_inf / (self.flow.rpm / 60.0 * self.geom.D + 1e-9)
        CT = T / (rho * (self.flow.rpm / 60.0) ** 2 * self.geom.D**4 + 1e-9)
        CP = P / (rho * (self.flow.rpm / 60.0) ** 3 * self.geom.D**5 + 1e-9)
        eta = T * V_inf / (P + 1e-9)

        return {
            "T": float(T),
            "Q": float(Q),
            "P": float(P),
            "CT": float(CT),
            "CP": float(CP),
            "J": float(J),
            "eta": float(np.clip(eta, 0.0, 1.0)),
        }
