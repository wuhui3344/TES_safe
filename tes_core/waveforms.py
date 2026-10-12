"""公式计算引擎（需求模块 2）。

按“波形族”分别计算电流指标与电荷指标，避免把不同波形简化成同一个公式。
本模块只做物理量计算，不做安全性判定。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .models import (
    CURRENT_DEFINITIONS,
    DEF_PP,
    DEF_RMS,
    MODE_CUSTOM,
    MODE_PULSE,
    MODE_TACS,
    MODE_TDCS,
    MODE_TI,
    MODE_TRNS,
    SampleAnalysis,
    StimulationParameters,
    WF_DC,
    WF_SINE,
)

# --- 波形族 ---------------------------------------------------------------
FAMILY_DC = "dc"
FAMILY_SINE = "sine"
FAMILY_NOISE = "noise"
FAMILY_PULSE = "pulse"
FAMILY_TI = "ti"
FAMILY_CUSTOM = "custom"

FAMILY_LABELS = {
    FAMILY_DC: "恒定直流",
    FAMILY_SINE: "正弦交流",
    FAMILY_NOISE: "随机噪声",
    FAMILY_PULSE: "脉冲/双相",
    FAMILY_TI: "TI/tTIS 多频",
    FAMILY_CUSTOM: "自定义",
}


def waveform_family(mode: str, waveform: str) -> str:
    """把“刺激类型 + 波形定义”映射到统一的波形族。"""
    if mode == MODE_PULSE or "脉冲" in waveform:
        return FAMILY_PULSE
    if mode == MODE_TI or "多频" in waveform:
        return FAMILY_TI
    if mode == MODE_TRNS or "噪声" in waveform:
        return FAMILY_NOISE
    if mode == MODE_TACS or waveform == WF_SINE:
        return FAMILY_SINE
    if mode == MODE_TDCS or waveform == WF_DC:
        return FAMILY_DC
    return FAMILY_CUSTOM


@dataclass
class CalculationResult:
    """计算输出。数值为 ``None`` 表示“当前波形下不可由简化公式得到”。"""

    family: str = FAMILY_DC
    family_label: str = ""

    peak_current_mA: Optional[float] = None
    rms_current_mA: Optional[float] = None
    pp_current_mA: Optional[float] = None
    mean_abs_current_mA: Optional[float] = None

    current_density_peak_mA_cm2: Optional[float] = None
    current_density_rms_mA_cm2: Optional[float] = None
    current_density_peak_A_m2: Optional[float] = None

    net_charge_mC: Optional[float] = None
    absolute_charge_mC: Optional[float] = None
    charge_per_phase_mC: Optional[float] = None
    charge_density_net_mC_cm2: Optional[float] = None
    charge_density_absolute_mC_cm2: Optional[float] = None

    peak_voltage_V: Optional[float] = None
    power_W: Optional[float] = None
    energy_J: Optional[float] = None
    daily_total_duration_min: float = 0.0

    reference_current_mA: Optional[float] = None
    reference_current_basis: str = ""

    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = {k: v for k, v in self.__dict__.items() if k != "notes"}
        data["notes"] = "；".join(self.notes)
        return data


def _trapezoid(values: Sequence[float], times: Sequence[float]) -> float:
    """纯 Python 梯形积分，避免额外依赖。"""
    total = 0.0
    for i in range(1, len(values)):
        dt = times[i] - times[i - 1]
        total += 0.5 * (values[i] + values[i - 1]) * dt
    return total


def analyze_samples(
    current_samples_mA: Sequence[float],
    sample_interval_s: Optional[float] = None,
    times_s: Optional[Sequence[float]] = None,
) -> SampleAnalysis:
    """根据实测/仿真的电流时间序列计算峰值、RMS、净电荷与绝对电荷。"""
    values = [float(v) for v in current_samples_mA]
    if len(values) < 2:
        return SampleAnalysis(sample_count=len(values), notes=["有效采样点不足，无法积分。"])

    if times_s is None:
        if sample_interval_s is None or sample_interval_s <= 0:
            return SampleAnalysis(
                sample_count=len(values),
                notes=["缺少采样间隔或时间轴，无法积分。"],
            )
        times = [i * sample_interval_s for i in range(len(values))]
    else:
        times = [float(t) for t in times_s]
        if len(times) != len(values):
            return SampleAnalysis(
                sample_count=len(values),
                notes=["时间轴与电流采样点数量不一致。"],
            )

    duration = times[-1] - times[0]
    if duration <= 0:
        return SampleAnalysis(sample_count=len(values), notes=["时间轴非单调递增，无法积分。"])

    peak = max(abs(v) for v in values)
    pp = max(values) - min(values)
    abs_values = [abs(v) for v in values]
    sq_values = [v * v for v in values]

    rms = math.sqrt(max(_trapezoid(sq_values, times) / duration, 0.0))
    mean_abs = _trapezoid(abs_values, times) / duration
    net_charge = _trapezoid(values, times)
    absolute_charge = _trapezoid(abs_values, times)

    notes: List[str] = []
    if abs(net_charge) > 1e-9 and rms > 1e-9:
        notes.append("检测到非零净电荷，提示可能存在直流偏置或电荷不平衡。")

    return SampleAnalysis(
        sample_count=len(values),
        duration_s=duration,
        peak_mA=peak,
        pp_mA=pp,
        rms_mA=rms,
        mean_abs_mA=mean_abs,
        net_charge_mC=net_charge,
        absolute_charge_mC=absolute_charge,
        notes=notes,
    )


def compute(params: StimulationParameters) -> CalculationResult:
    """计算电流密度、电荷、功率、能量与合规电压需求。"""
    res = CalculationResult()
    family = waveform_family(params.mode, params.waveform)
    res.family = family
    res.family_label = FAMILY_LABELS[family]

    area = max(params.area_cm2, 1e-12)
    duration_s = params.duration_s
    impedance = max(params.impedance_ohm, 0.0)
    res.daily_total_duration_min = params.duration_min * params.sessions_per_day

    value = params.current_value_mA
    definition = params.current_definition
    if definition not in CURRENT_DEFINITIONS:
        res.notes.append(f"未知的电流幅值定义“{definition}”，按输入值直接使用。")

    # --- 步骤 1：把各种幅值定义统一换算为峰值幅度 ------------------------
    if definition == DEF_PP:
        peak = value / 2.0
        res.notes.append("输入为峰峰值，按峰峰值的一半换算为峰值幅度。")
    elif definition == DEF_RMS:
        if family == FAMILY_SINE:
            peak = value * math.sqrt(2.0)
            res.notes.append("输入为 RMS；按理想正弦换算峰值 = RMS×√2。")
        else:
            peak = value
            res.notes.append(
                "输入为 RMS；非正弦波形无法仅由 RMS 推得峰值，此处按同值记录，须以实测波形确认。"
            )
    else:
        peak = value

    res.peak_current_mA = peak

    # --- 步骤 2：按波形族计算 rms / 峰峰值 / 电荷 ------------------------
    if family == FAMILY_DC:
        res.rms_current_mA = peak
        res.pp_current_mA = peak
        res.mean_abs_current_mA = peak
        res.net_charge_mC = peak * duration_s  # mA·s = mC
        res.absolute_charge_mC = abs(res.net_charge_mC)

    elif family == FAMILY_SINE:
        res.rms_current_mA = peak / math.sqrt(2.0)
        res.pp_current_mA = 2.0 * peak
        res.mean_abs_current_mA = peak * 2.0 / math.pi
        res.net_charge_mC = 0.0
        if params.frequency_hz > 0:
            res.absolute_charge_mC = res.mean_abs_current_mA * duration_s
            res.notes.append(
                "正弦绝对电荷按 |i| 的整周期平均 (2/π)·I_peak 估算；理想正弦净电荷接近零，"
                "但净电荷为零不代表没有刺激剂量。"
            )
        else:
            res.notes.append("频率为 0，无法按正弦积分绝对电荷，请检查频率参数。")

    elif family == FAMILY_PULSE:
        t_phase_s = params.pulse_width_us * 1e-6
        duty = min(t_phase_s * params.phases_count * params.pulses_per_second, 1.0)
        res.rms_current_mA = peak * math.sqrt(max(duty, 0.0))
        res.pp_current_mA = 2.0 * peak if params.phases_count == 2 else peak
        res.mean_abs_current_mA = peak * min(duty, 1.0)
        res.charge_per_phase_mC = peak * t_phase_s
        res.absolute_charge_mC = (
            res.charge_per_phase_mC * params.phases_count * params.pulses_per_second * duration_s
        )
        if params.phases_count == 2:
            res.net_charge_mC = 0.0
            res.notes.append(
                "双相脉冲按理想电荷平衡处理，净电荷记为 0；须实测两相面积差以确认电荷平衡与残余直流。"
            )
        else:
            res.net_charge_mC = res.absolute_charge_mC
            res.notes.append(
                "单相脉冲存在直流电荷累积，净电荷等于绝对电荷；不应直接套用低强度 tES 的电流指标。"
            )
        res.notes.append("脉冲电荷按矩形脉冲近似（幅值×脉宽×相数×脉冲数），非矩形脉冲需对实测波形积分。")

    elif family == FAMILY_NOISE:
        if definition == DEF_RMS:
            res.rms_current_mA = value
            res.notes.append("tRNS 按输入 RMS 记录；峰值、峰峰值与电荷需由实测随机波形积分得到。")
        else:
            res.notes.append(
                "tRNS 为随机噪声，无法由单一幅值推得峰值/RMS/电荷，请导入实测波形采样数据。"
            )

    else:  # FAMILY_TI / FAMILY_CUSTOM
        res.notes.append(
            "TI/tTIS 与自定义多频波形需按每个载波通道分别记录幅值/频率/相位/电极位置，"
            "并通过个体化建模与实测输出验证；本工具不计算脑内包络场。"
        )

    # --- 步骤 3：电流密度 -------------------------------------------------
    res.current_density_peak_mA_cm2 = peak / area
    res.current_density_peak_A_m2 = res.current_density_peak_mA_cm2 * 10.0
    if res.rms_current_mA is not None:
        res.current_density_rms_mA_cm2 = res.rms_current_mA / area

    # --- 步骤 4：电荷密度 -------------------------------------------------
    if res.net_charge_mC is not None:
        res.charge_density_net_mC_cm2 = res.net_charge_mC / area
    if res.absolute_charge_mC is not None:
        res.charge_density_absolute_mC_cm2 = res.absolute_charge_mC / area

    # --- 步骤 5：欧姆负载近似 --------------------------------------------
    res.peak_voltage_V = (peak / 1000.0) * impedance
    rms_for_power = res.rms_current_mA if res.rms_current_mA is not None else peak
    res.power_W = ((rms_for_power / 1000.0) ** 2) * impedance
    res.energy_J = res.power_W * duration_s
    res.notes.append("电压/功率按简化欧姆模型 I×R、I_RMS²R 估算，皮肤-电极界面实为动态非线性阻抗。")

    # --- 步骤 6：用于文献范围比较的归一化电流 ----------------------------
    if family == FAMILY_DC:
        res.reference_current_mA = peak
        res.reference_current_basis = "直流幅值 (mA)"
    elif family == FAMILY_SINE:
        res.reference_current_mA = 2.0 * peak
        res.reference_current_basis = "峰峰值 (mA, p-p)"
    else:
        res.reference_current_mA = None
        res.reference_current_basis = "不适用（需实测波形定义）"

    return res
