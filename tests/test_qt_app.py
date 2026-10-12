"""Qt 界面的无头冒烟测试（offscreen 平台，不需要真实显示器）。

覆盖：窗口能构建、计算能执行、规则能填充到表格、PDF 能生成。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument
    from PySide6.QtWidgets import QApplication

    from tes_core import (
        build_calculation_record,
        build_check_records,
        build_parameter_record,
        build_report_html,
    )

    HAS_QT = True
except ImportError:  # pragma: no cover
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "PySide6 未安装")
class TestQtApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv[:1])

    def setUp(self):
        import tes_qt_app

        self.window = tes_qt_app.MainWindow()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()

    def test_window_builds_and_computes(self):
        self.assertIsNotNone(self.window._result)
        self.assertIsNotNone(self.window._params)
        self.assertTrue(self.window._checks)
        # 默认 2 mA / 20.0+ cm²，应能算出电流密度
        self.assertGreater(self.window._result.current_density_peak_mA_cm2, 0)

    def test_rules_table_populated(self):
        table = self.window.rules_table
        self.assertEqual(table.rowCount(), len(self.window._checks))
        self.assertEqual(table.columnCount(), 5)
        # 第一列应为规则编号
        self.assertTrue(table.item(0, 0).text().startswith(("LIT-", "ENG-", "PRJ-", "DEV-")))

    def test_status_thresholds_update_result(self):
        # 把电流调到 6 mA，文献范围规则应变为“超出设计约束”
        self.window.current_spin.setValue(6.0)
        self.window._recompute()
        statuses = {c.rule.rule_id: c.status for c in self.window._checks}
        self.assertEqual(statuses["LIT-CURRENT-001"], "超出设计约束")

    def test_pdf_generation_via_qt(self):
        param_record, calc_record, check_records, _ = self.window._records()
        html_text = build_report_html(param_record, calc_record, check_records)
        path = os.path.join(tempfile.mkdtemp(), "report.pdf")
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        document = QTextDocument()
        document.setHtml(html_text)
        document.print_(writer)
        document = None  # 释放，确保写盘完成
        import gc

        gc.collect()
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 1000)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(4), b"%PDF")


if __name__ == "__main__":
    unittest.main(verbosity=2)
