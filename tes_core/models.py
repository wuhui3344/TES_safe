"""数据模型与常量定义。

本文件只负责“描述参数”，不做任何安全判定。
所有安全相关结论由 :mod:`tes_core.safety_rules` 依据带来源的规则给出。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

# --- 刺激模式 -------------------------------------------------------------
MODE_TDCS = "tDCS（直流）"
MODE_TACS = "tACS（正弦交流）"
MODE_TRNS = "tRNS（随机噪声）"
MODE_PULSE = "脉冲/双相波形"
MODE_TI = "TI/tTIS（时间干涉）"
MODE_CUSTOM = "多模式/自定义"

STIM_MODES = (MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_PULSE, MODE_TI, MODE_CUSTOM)

# --- 波形定义 -------------------------------------------------------------
WF_DC = "恒定直流"
WF_SINE = "正弦波"
WF_NOISE = "随机/噪声波"
WF_MONO = "单相脉冲"
WF_BI = "电荷平衡双相脉冲"
WF_MULTI = "多通道多频"

WAVEFORMS = (WF_DC, WF_SINE, WF_NOISE, WF_MONO, WF_BI, WF_MULTI)

# --- 电流幅值定义 ---------------------------------------------------------
DEF_DC = "直流恒定值"
DEF_PEAK = "峰值/基线至峰值"
DEF_PP = "峰峰值 (peak-to-peak)"
DEF_RMS = "RMS有效值"
DEF_PHASE_AMP = "每相脉冲幅值"

CURRENT_DEFINITIONS = (DEF_DC, DEF_PEAK, DEF_PP, DEF_RMS, DEF_PHASE_AMP)

# --- 电极形式 -------------------------------------------------------------
ELECTRODE_SPONGE = "盐水海绵/导电介质垫"
ELECTRODE_RUBBER = "导电橡胶+水凝胶"
ELECTRODE_HD = "HD小面积电极"
ELECTRODE_SILICONE = "导电硅胶"
ELECTRODE_CUSTOM = "其他/自定义"

ELECTRODE_TYPES = (
    ELECTRODE_SPONGE,
    ELECTRODE_RUBBER,
    ELECTRODE_HD,
    ELECTRODE_SILICONE,
    ELECTRODE_CUSTOM,
)

PHASES_OPTIONS = ("单相", "双相")


@dataclass
class StimulationParameters:
    """单次刺激设计的输入参数（需求模块 1）。"""

    mode: str = MODE_TDCS
    waveform: str = WF_DC
    current_definition: str = DEF_DC
    current_value_mA: float = 2.0
    frequency_hz: float = 0.0
    pulse_width_us: float = 200.0
    pulses_per_second: float = 1.0
    phases: str = "双相"
    electrode_type: str = ELECTRODE_SPONGE
    area_cm2: float = 22.9
    channels: int = 2
    duration_min: float = 30.0
    sessions_per_day: int = 1
    impedance_ohm: float = 5000.0
    compliance_voltage_V: float = 30.0

    @property
    def duration_s(self) -> float:
        return self.duration_min * 60.0

    @property
    def phases_count(self) -> int:
        return 2 if self.phases == "双相" else 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectConstraints:
    """项目级筛查阈值（由项目负责人 / 风险管理确定，非通用医学限值）。"""

    use_current_amplitude: bool = False
    current_amplitude_limit_mA: float = 4.0

    use_current_density: bool = False
    current_density_limit_mA_cm2: float = 0.1

    use_charge_density: bool = False
    charge_density_limit_mC_cm2: float = 200.0

    use_duration: bool = True
    duration_limit_min: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SampleAnalysis:
    """由实测波形采样数据得到的指标（需求 A：按波形采样计算）。"""

    sample_count: int = 0
    duration_s: float = 0.0
    peak_mA: float = 0.0
    pp_mA: float = 0.0
    rms_mA: float = 0.0
    mean_abs_mA: float = 0.0
    net_charge_mC: float = 0.0
    absolute_charge_mC: float = 0.0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["notes"] = "；".join(self.notes)
        return data
