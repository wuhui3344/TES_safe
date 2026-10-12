"""经颅电刺激（tES）安全设计计算器 —— 核心计算包。

模块划分对应需求中的四个子系统：

* ``models``       —— 参数与约束数据模型（模块 1 的数据结构）；
* ``waveforms``    —— 公式计算引擎 + 波形采样分析（模块 2 / A）；
* ``safety_rules`` —— 可追溯安全规则引擎与规则数据库（模块 3 / C）；
* ``report``       —— 报告与追溯导出（模块 4 / D）。

⚠️ 本包只做物理量计算与已配置约束筛查，不输出“人体绝对安全”结论。

依赖：**仅标准库**（Excel 导出可选依赖 ``openpyxl``），因此可被任意 GUI 框架复用。
"""

from __future__ import annotations

__version__ = "1.0.0"

from .models import ProjectConstraints, SampleAnalysis, StimulationParameters
from .report import (
    build_calculation_record,
    build_check_records,
    build_excel_sheets,
    build_parameter_record,
    build_report_html,
    build_sample_record,
    build_summary,
    merge_records_for_csv,
    rows_to_csv_bytes,
    sheets_to_excel_bytes,
)
from .safety_rules import (
    STATUS_INSUFFICIENT,
    STATUS_PASS,
    STATUS_VIOLATION,
    RuleCheck,
    SafetyRule,
    evaluate_rules,
    rule_catalog,
    rule_catalog_records,
)
from .waveforms import (
    FAMILY_LABELS,
    CalculationResult,
    analyze_samples,
    compute,
    waveform_family,
)

__all__ = [
    "__version__",
    # models
    "StimulationParameters",
    "ProjectConstraints",
    "SampleAnalysis",
    # waveforms
    "CalculationResult",
    "compute",
    "analyze_samples",
    "waveform_family",
    "FAMILY_LABELS",
    # safety rules
    "SafetyRule",
    "RuleCheck",
    "evaluate_rules",
    "rule_catalog",
    "rule_catalog_records",
    "STATUS_PASS",
    "STATUS_VIOLATION",
    "STATUS_INSUFFICIENT",
    # report
    "build_parameter_record",
    "build_calculation_record",
    "build_sample_record",
    "build_check_records",
    "build_summary",
    "build_excel_sheets",
    "rows_to_csv_bytes",
    "merge_records_for_csv",
    "sheets_to_excel_bytes",
    "build_report_html",
]
