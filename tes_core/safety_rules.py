"""安全规则引擎（需求模块 3 + C 安全规则数据库）。

每条规则都带可追溯元数据：适用模式、来源、版本、证据等级、验证状态。
状态输出严格限定为三类（与需求一致）：

* ``满足已配置约束``  —— 未超出当前已录入的约束；
* ``超出设计约束``    —— 超出已录入的设计阈值；
* ``证据不足，需验证`` —— 现有证据不足以判定，必须专项验证。

注意：即使输出“满足已配置约束”，也**不等于**设备对人体安全。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .models import (
    MODE_CUSTOM,
    MODE_PULSE,
    MODE_TACS,
    MODE_TDCS,
    MODE_TI,
    MODE_TRNS,
    ELECTRODE_HD,
    ProjectConstraints,
    StimulationParameters,
)
from .waveforms import (
    FAMILY_CUSTOM,
    FAMILY_NOISE,
    FAMILY_PULSE,
    FAMILY_SINE,
    FAMILY_TI,
    CalculationResult,
    waveform_family,
)

STATUS_PASS = "满足已配置约束"
STATUS_VIOLATION = "超出设计约束"
STATUS_INSUFFICIENT = "证据不足，需验证"

# 证据等级
EV_LITERATURE = "文献共识（非法规限值）"
EV_STANDARD = "强制性/引用标准（适用范围需确认）"
EV_PROJECT = "项目风险管理文件"
EV_ENGINEERING = "工程判据（待验证）"


@dataclass(frozen=True)
class SafetyRule:
    """一条可追溯的安全规则。"""

    rule_id: str
    category: str
    applies_modes: Tuple[str, ...]
    source: str
    source_version: str
    evidence_level: str
    validation_status: str
    description: str


@dataclass
class RuleCheck:
    rule: SafetyRule
    status: str
    measured: Optional[float]
    limit: Optional[float]
    unit: str
    message: str

    def to_dict(self) -> dict:
        return {
            "规则编号": self.rule.rule_id,
            "类别": self.rule.category,
            "状态": self.status,
            "实测值": "" if self.measured is None else self.measured,
            "限值": "" if self.limit is None else self.limit,
            "单位": self.unit,
            "说明": self.message,
            "来源": self.rule.source,
            "来源版本": self.rule.source_version,
            "证据等级": self.rule.evidence_level,
            "验证状态": self.rule.validation_status,
        }


# --- 规则库（需求 C：每项限制保存适用模式/定义/来源/版本/证据等级/验证状态）---
_LIT_SOURCE = "低强度 tES 安全指南（2025 年更新、2026 年刊出）"
_LIT_VERSION = "2025-更新 / 2026-刊出"

RULE_LIT_CURRENT = SafetyRule(
    rule_id="LIT-CURRENT-001",
    category="文献低强度范围｜电流",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_TI, MODE_CUSTOM),
    source=_LIT_SOURCE,
    source_version=_LIT_VERSION,
    evidence_level=EV_LITERATURE,
    validation_status="参考性阈值，须由项目确认是否适用",
    description="研究常见低强度 tES 电流 ≤4 mA（交流波形按峰峰值定义），非固定/绝对安全阈值。",
)

RULE_LIT_DURATION = SafetyRule(
    rule_id="LIT-DURATION-001",
    category="文献低强度范围｜时长",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_TI, MODE_CUSTOM, MODE_PULSE),
    source=_LIT_SOURCE,
    source_version=_LIT_VERSION,
    evidence_level=EV_LITERATURE,
    validation_status="参考性阈值，须由项目确认是否适用",
    description="研究常见单次刺激时长 ≤60 min，非绝对安全上限。",
)

RULE_LIT_AREA = SafetyRule(
    rule_id="LIT-AREA-001",
    category="文献低强度范围｜电极面积",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_TI, MODE_CUSTOM),
    source=_LIT_SOURCE,
    source_version=_LIT_VERSION,
    evidence_level=EV_LITERATURE,
    validation_status="参考性阈值，须由项目确认是否适用",
    description="研究常见有效接触面积 1–100 cm²；面积为电解质与皮肤间实际导电界面面积。",
)

RULE_VOLTAGE = SafetyRule(
    rule_id="ENG-VOLT-001",
    category="电压能力｜工程计算",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_PULSE, MODE_TI, MODE_CUSTOM),
    source="项目设计输入（合规电压 / 输出限压设定）",
    source_version="用户输入",
    evidence_level=EV_ENGINEERING,
    validation_status="待用真实负载与动态阻抗验证",
    description="比较简化欧姆模型估算的峰值电压与输入的合规电压/限压设定。",
)

RULE_PROJECT_CURRENT = SafetyRule(
    rule_id="PRJ-CURRENT-001",
    category="项目约束｜电流幅值",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_PULSE, MODE_TI, MODE_CUSTOM),
    source="项目风险管理文件（用户输入）",
    source_version="用户输入",
    evidence_level=EV_PROJECT,
    validation_status="由项目负责人批准",
    description="用户自定义的电流幅值上限筛查。",
)

RULE_PROJECT_J = SafetyRule(
    rule_id="PRJ-J-001",
    category="项目约束｜电流密度",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_PULSE, MODE_TI, MODE_CUSTOM),
    source="项目风险管理文件（用户输入）",
    source_version="用户输入",
    evidence_level=EV_PROJECT,
    validation_status="由项目负责人批准",
    description="用户自定义的平均电流密度上限筛查。",
)

RULE_PROJECT_Q = SafetyRule(
    rule_id="PRJ-Q-001",
    category="项目约束｜电荷密度",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_PULSE, MODE_TI, MODE_CUSTOM),
    source="项目风险管理文件（用户输入）",
    source_version="用户输入",
    evidence_level=EV_PROJECT,
    validation_status="由项目负责人批准",
    description="用户自定义的电荷密度上限筛查（脉冲/直流可算时）。",
)

RULE_PROJECT_TIME = SafetyRule(
    rule_id="PRJ-TIME-001",
    category="项目约束｜单次时长",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_PULSE, MODE_TI, MODE_CUSTOM),
    source="项目风险管理文件（用户输入）",
    source_version="用户输入",
    evidence_level=EV_PROJECT,
    validation_status="由项目负责人批准",
    description="用户自定义的单次刺激时长上限筛查。",
)

RULE_HD_ELECTRODE = SafetyRule(
    rule_id="ENG-ELEC-001",
    category="小面积/HD 电极",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_PULSE, MODE_TI, MODE_CUSTOM),
    source="工程判据",
    source_version="v1",
    evidence_level=EV_ENGINEERING,
    validation_status="必须专项验证",
    description="小面积/HD 电极局部电流密度更高，须验证局部电流分布、界面材料、接触压力、温升与皮肤耐受性。",
)

RULE_WAVEFORM_REVIEW = SafetyRule(
    rule_id="ENG-WAVE-001",
    category="波形审查",
    applies_modes=(MODE_TACS, MODE_TRNS, MODE_TI, MODE_CUSTOM),
    source="工程判据",
    source_version="v1",
    evidence_level=EV_ENGINEERING,
    validation_status="必须专项验证",
    description="须记录峰值、峰峰值、RMS、频谱、直流偏置、启停瞬态与输出误差；不同波形的剂量指标不可互换。",
)

RULE_TI_SPECIAL = SafetyRule(
    rule_id="ENG-TI-001",
    category="TI/tTIS 专项",
    applies_modes=(MODE_TI,),
    source="工程判据",
    source_version="v1",
    evidence_level=EV_ENGINEERING,
    validation_status="必须专项验证",
    description="须逐通道记录幅值/频率/相位/电极位置，并进行个体化电场建模与实测输出验证；本工具不判定 TI 人体安全性。",
)

RULE_MULTICHANNEL = SafetyRule(
    rule_id="ENG-CHAN-001",
    category="多通道电流分配",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_PULSE, MODE_TI, MODE_CUSTOM),
    source="工程判据",
    source_version="v1",
    evidence_level=EV_ENGINEERING,
    validation_status="必须专项验证",
    description="通道数较多时须验证各通道实际电流分配、串扰、单通道故障与总电流上限。",
)

RULE_DEVICE_LEVEL = SafetyRule(
    rule_id="DEV-LEVEL-001",
    category="设备级安全",
    applies_modes=(MODE_TDCS, MODE_TACS, MODE_TRNS, MODE_PULSE, MODE_TI, MODE_CUSTOM),
    source="IEC 60601-2-10 / 预期用途评估（适用范围需确认）",
    source_version="官方标准页面（版本以采购/引用为准）",
    evidence_level=EV_STANDARD,
    validation_status="待完成标准适用性分析与型式试验",
    description="须完成适用标准评估、风险管理、基本安全/基本性能、电气隔离、漏电流、单故障、软件异常与可用性验证。",
)


def rule_catalog() -> List[SafetyRule]:
    """返回全部规则的元数据，用于报告中的规则依据表。"""
    return [
        RULE_LIT_CURRENT,
        RULE_LIT_DURATION,
        RULE_LIT_AREA,
        RULE_VOLTAGE,
        RULE_PROJECT_CURRENT,
        RULE_PROJECT_J,
        RULE_PROJECT_Q,
        RULE_PROJECT_TIME,
        RULE_HD_ELECTRODE,
        RULE_WAVEFORM_REVIEW,
        RULE_TI_SPECIAL,
        RULE_MULTICHANNEL,
        RULE_DEVICE_LEVEL,
    ]


def rule_catalog_records() -> List[dict]:
    return [
        {
            "规则编号": r.rule_id,
            "类别": r.category,
            "适用模式": "、".join(r.applies_modes),
            "来源": r.source,
            "来源版本": r.source_version,
            "证据等级": r.evidence_level,
            "验证状态": r.validation_status,
            "规则描述": r.description,
        }
        for r in rule_catalog()
    ]


def _check_upper(
    rule: SafetyRule,
    value: Optional[float],
    limit: float,
    unit: str,
    label: str,
    over_message: str,
    ok_message: str,
    no_value_message: str,
) -> RuleCheck:
    if value is None:
        return RuleCheck(rule, STATUS_INSUFFICIENT, None, limit, unit,
                         f"{label}：{no_value_message}")
    if value > limit:
        return RuleCheck(rule, STATUS_VIOLATION, value, limit, unit, over_message)
    return RuleCheck(rule, STATUS_PASS, value, limit, unit, ok_message)


def evaluate_rules(
    params: StimulationParameters,
    result: CalculationResult,
    constraints: ProjectConstraints,
) -> List[RuleCheck]:
    """依据输入参数与计算结果执行规则筛查。"""
    checks: List[RuleCheck] = []
    family = waveform_family(params.mode, params.waveform)

    # 1) 文献范围｜电流
    if family == FAMILY_PULSE:
        checks.append(RuleCheck(
            RULE_LIT_CURRENT, STATUS_INSUFFICIENT, None, 4.0, "mA",
            "脉冲波形不应直接套用低强度 tES 的统一电流指标，需按实测波形与专门证据评估。"))
    elif result.reference_current_mA is None:
        checks.append(RuleCheck(
            RULE_LIT_CURRENT, STATUS_INSUFFICIENT, None, 4.0, "mA(p-p)",
            "该波形的电流指标无法直接归一化到 ≤4 mA 的文献范围，需提供实测波形与专项依据。"))
    else:
        ref = result.reference_current_mA
        checks.append(RuleCheck(
            RULE_LIT_CURRENT,
            STATUS_VIOLATION if ref > 4.0 else STATUS_PASS,
            ref, 4.0, "mA",
            f"归一化电流 {ref:.3f} mA（{result.reference_current_basis}）"
            + ("超出" if ref > 4.0 else "未超出")
            + "文献所述常见低强度 tES 范围（≤4 mA，交流按峰峰值）；该范围不是法规限值。"))

    # 2) 文献范围｜时长
    checks.append(RuleCheck(
        RULE_LIT_DURATION,
        STATUS_VIOLATION if params.duration_min > 60.0 else STATUS_PASS,
        params.duration_min, 60.0, "min",
        ("超出" if params.duration_min > 60.0 else "未超出")
        + "文献所述常见单次时长 ≤60 min 的研究范围；该值不是绝对安全上限。"))

    # 3) 文献范围｜电极面积
    if params.area_cm2 < 1.0 or params.area_cm2 > 100.0:
        checks.append(RuleCheck(
            RULE_LIT_AREA, STATUS_VIOLATION, params.area_cm2, 100.0, "cm²",
            "有效接触面积不在文献所述常见研究范围 1–100 cm² 内，需提供独立依据与验证。"))
    else:
        checks.append(RuleCheck(
            RULE_LIT_AREA, STATUS_PASS, params.area_cm2, 100.0, "cm²",
            "面积位于常见研究范围描述内；仍需验证电极材料、边缘效应与皮肤界面。"))

    # 4) 电压能力（工程计算）
    est_voltage = result.peak_voltage_V
    if est_voltage is not None and params.compliance_voltage_V > 0:
        checks.append(RuleCheck(
            RULE_VOLTAGE,
            STATUS_VIOLATION if est_voltage > params.compliance_voltage_V else STATUS_PASS,
            est_voltage, params.compliance_voltage_V, "V",
            ("估算峰值电压高于" if est_voltage > params.compliance_voltage_V else "估算峰值电压未超过")
            + "输入的合规电压/限压设定；实际负载非纯电阻，须用真实负载与动态阻抗测试。"))
    else:
        checks.append(RuleCheck(
            RULE_VOLTAGE, STATUS_INSUFFICIENT, est_voltage, params.compliance_voltage_V, "V",
            "缺少估算电压或合规电压设定，无法比较。"))

    # 5) 项目约束｜电流幅值
    if constraints.use_current_amplitude:
        checks.append(_check_upper(
            RULE_PROJECT_CURRENT, result.peak_current_mA, constraints.current_amplitude_limit_mA,
            "mA", "项目电流幅值",
            f"{result.peak_current_mA:.3f} mA > 项目设定上限 {constraints.current_amplitude_limit_mA:.3f} mA。",
            f"{result.peak_current_mA:.3f} mA ≤ 项目设定上限 {constraints.current_amplitude_limit_mA:.3f} mA。",
            "无可用电流幅值。"))

    # 6) 项目约束｜电流密度
    if constraints.use_current_density:
        checks.append(_check_upper(
            RULE_PROJECT_J, result.current_density_peak_mA_cm2,
            constraints.current_density_limit_mA_cm2, "mA/cm²", "项目电流密度",
            f"{result.current_density_peak_mA_cm2:.4f} mA/cm² > 项目设定上限 {constraints.current_density_limit_mA_cm2:.4f} mA/cm²。",
            f"{result.current_density_peak_mA_cm2:.4f} mA/cm² ≤ 项目设定上限 {constraints.current_density_limit_mA_cm2:.4f} mA/cm²。",
            "无可用电流密度。"))

    # 7) 项目约束｜电荷密度
    if constraints.use_charge_density:
        checks.append(_check_upper(
            RULE_PROJECT_Q, result.charge_density_absolute_mC_cm2,
            constraints.charge_density_limit_mC_cm2, "mC/cm²", "项目电荷密度",
            f"{result.charge_density_absolute_mC_cm2:.3f} mC/cm² > 项目设定上限 {constraints.charge_density_limit_mC_cm2:.3f} mC/cm²。",
            f"{result.charge_density_absolute_mC_cm2:.3f} mC/cm² ≤ 项目设定上限 {constraints.charge_density_limit_mC_cm2:.3f} mC/cm²。",
            "当前波形无可用的电荷密度估算值，需导入实测波形后计算。"))

    # 8) 项目约束｜单次时长
    if constraints.use_duration:
        checks.append(_check_upper(
            RULE_PROJECT_TIME, params.duration_min, constraints.duration_limit_min,
            "min", "项目单次时长",
            f"{params.duration_min:.1f} min > 项目设定上限 {constraints.duration_limit_min:.1f} min。",
            f"{params.duration_min:.1f} min ≤ 项目设定上限 {constraints.duration_limit_min:.1f} min。",
            "无可用时长。"))

    # 9) 小面积 / HD 电极
    if params.electrode_type == ELECTRODE_HD or params.area_cm2 < 5.0:
        checks.append(RuleCheck(
            RULE_HD_ELECTRODE, STATUS_INSUFFICIENT, params.area_cm2, 5.0, "cm²",
            "使用小面积/HD 电极或面积 <5 cm²，平均电流密度较高，须专项验证局部电流分布、界面材料、"
            "接触压力、温升与皮肤耐受性。"))

    # 10) 波形审查
    if family in (FAMILY_SINE, FAMILY_NOISE, FAMILY_TI, FAMILY_CUSTOM) or params.mode in (
        MODE_TACS, MODE_TRNS, MODE_TI, MODE_CUSTOM
    ):
        checks.append(RuleCheck(
            RULE_WAVEFORM_REVIEW, STATUS_INSUFFICIENT, None, None, "",
            "记录峰值、峰峰值、RMS、频谱、直流偏置、启停瞬态与输出误差；不同波形的剂量指标不可直接互换。"))

    # 11) TI 专项
    if params.mode == MODE_TI:
        checks.append(RuleCheck(
            RULE_TI_SPECIAL, STATUS_INSUFFICIENT, None, None, "",
            "需逐通道记录幅值/频率/相位/电极位置，并完成个体化电场建模与实测输出验证；"
            "本工具不计算脑内包络场，也不判定 TI 的人体安全性。"))

    # 12) 多通道
    if params.channels > 2:
        checks.append(RuleCheck(
            RULE_MULTICHANNEL, STATUS_INSUFFICIENT, float(params.channels), 2.0, "通道",
            f"通道数为 {params.channels}，须验证各通道实际电流分配、串扰、单通道故障与总电流上限。"))

    # 13) 设备级
    checks.append(RuleCheck(
        RULE_DEVICE_LEVEL, STATUS_INSUFFICIENT, None, None, "",
        "需完成适用标准评估、风险管理、基本安全/基本性能、电气隔离、漏电流、单故障、软件异常与可用性验证。"))

    return checks
