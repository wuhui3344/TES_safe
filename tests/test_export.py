"""导出引擎（Excel / HTML 报告）的集成测试；缺少可选依赖时自动跳过。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tes_core import (  # noqa: E402
    ProjectConstraints,
    StimulationParameters,
    build_calculation_record,
    build_check_records,
    build_excel_sheets,
    build_parameter_record,
    build_report_html,
    compute,
    evaluate_rules,
    sheets_to_excel_bytes,
)


class TestExport(unittest.TestCase):
    def setUp(self):
        self.params = StimulationParameters()
        self.constraints = ProjectConstraints()
        self.result = compute(self.params)
        self.checks = evaluate_rules(self.params, self.result, self.constraints)

    def test_excel_bytes(self):
        sheets = build_excel_sheets(self.params, self.constraints, self.result, self.checks)
        self.assertEqual(
            set(sheets.keys()),
            {"输入参数", "计算结果", "规则筛查", "规则依据"},
        )
        data = sheets_to_excel_bytes(sheets)
        if data is None:
            self.skipTest("openpyxl 未安装")
        # xlsx 是 zip 容器，应以 PK 开头
        self.assertTrue(data.startswith(b"PK"))
        self.assertGreater(len(data), 2000)

    def test_excel_has_all_sheets(self):
        from io import BytesIO

        from openpyxl import load_workbook

        sheets = build_excel_sheets(self.params, self.constraints, self.result, self.checks)
        data = sheets_to_excel_bytes(sheets)
        if data is None:
            self.skipTest("openpyxl 未安装")
        workbook = load_workbook(BytesIO(data))
        self.assertEqual(
            workbook.sheetnames,
            ["输入参数", "计算结果", "规则筛查", "规则依据"],
        )

    def test_report_html_self_contained(self):
        html_text = build_report_html(
            build_parameter_record(self.params, self.constraints),
            build_calculation_record(self.result),
            build_check_records(self.checks),
        )
        self.assertIn("<html", html_text)
        self.assertIn("经颅电刺激", html_text)
        self.assertIn("规则依据（可追溯性）", html_text)
        # 不得残留 reportlab 痕迹（已改用纯标准库 HTML + Qt 渲染）
        self.assertNotIn("reportlab", html_text)
        self.assertIn("</table>", html_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
