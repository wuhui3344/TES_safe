"""核心计算与规则引擎的单元测试（不依赖 streamlit）。

运行：
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tes_core import (  # noqa: E402
    STATUS_INSUFFICIENT,
    STATUS_PASS,
    STATUS_VIOLATION,
    ProjectConstraints,
    StimulationParameters,
    analyze_samples,
    compute,
    evaluate_rules,
    rows_to_csv_bytes,
)
from tes_core.models import DEF_PP, DEF_RMS, MODE_PULSE, MODE_TACS, MODE_TDCS, MODE_TI  # noqa: E402


class TestDC(unittest.TestCase):
    def test_charge_and_density(self):
        p = StimulationParameters(mode=MODE_TDCS, current_value_mA=2.0, area_cm2=20.0, duration_min=10.0)
        r = compute(p)
        # Q = I * t = 2 mA * 600 s = 1200 mC
        self.assertAlmostEqual(r.net_charge_mC, 1200.0, places=6)
        self.assertAlmostEqual(r.absolute_charge_mC, 1200.0, places=6)
        # J = I / A = 2 / 20 = 0.1 mA/cm²
        self.assertAlmostEqual(r.current_density_peak_mA_cm2, 0.1, places=6)
        # σ = Q / A = 60 mC/cm²
        self.assertAlmostEqual(r.charge_density_absolute_mC_cm2, 60.0, places=6)
        # V = I * R = 0.002 A * 5000 Ω = 10 V
        self.assertAlmostEqual(r.peak_voltage_V, 10.0, places=6)
        # P = I²R = 0.002² * 5000 = 0.02 W
        self.assertAlmostEqual(r.power_W, 0.02, places=9)

    def test_reference_current_is_amplitude(self):
        p = StimulationParameters(mode=MODE_TDCS, current_value_mA=3.0)
        r = compute(p)
        self.assertAlmostEqual(r.reference_current_mA, 3.0, places=6)


class TestSine(unittest.TestCase):
    def test_pp_input_conversion_and_absolute_charge(self):
        p = StimulationParameters(
            mode=MODE_TACS, waveform="正弦波", current_definition=DEF_PP,
            current_value_mA=4.0, frequency_hz=1000.0, duration_min=1.0, area_cm2=10.0,
        )
        r = compute(p)
        # 峰峰值 4 mA → 峰值 2 mA → RMS = 2/√2
        self.assertAlmostEqual(r.peak_current_mA, 2.0, places=6)
        self.assertAlmostEqual(r.rms_current_mA, 2.0 / math.sqrt(2.0), places=6)
        self.assertAlmostEqual(r.pp_current_mA, 4.0, places=6)
        # 绝对电荷 = (2/π)·I_peak·t = 2/π·2·60
        self.assertAlmostEqual(r.absolute_charge_mC, (2.0 / math.pi) * 2.0 * 60.0, places=6)
        self.assertAlmostEqual(r.net_charge_mC, 0.0, places=9)
        # 文献比较基准为峰峰值
        self.assertAlmostEqual(r.reference_current_mA, 4.0, places=6)

    def test_rms_input_conversion(self):
        p = StimulationParameters(
            mode=MODE_TACS, waveform="正弦波", current_definition=DEF_RMS,
            current_value_mA=1.0, frequency_hz=1000.0,
        )
        r = compute(p)
        self.assertAlmostEqual(r.peak_current_mA, math.sqrt(2.0), places=6)


class TestPulse(unittest.TestCase):
    def test_monophasic_charge(self):
        p = StimulationParameters(
            mode=MODE_PULSE, waveform="单相脉冲", phases="单相",
            current_value_mA=1.0, pulse_width_us=100.0, pulses_per_second=100.0,
            duration_min=1.0, area_cm2=10.0,
        )
        r = compute(p)
        # 每相电荷 = 1 mA * 100e-6 s = 1e-4 mC
        self.assertAlmostEqual(r.charge_per_phase_mC, 1e-4, places=9)
        # 绝对电荷 = 1e-4 * 1 相 * 100 pps * 60 s = 0.6 mC
        self.assertAlmostEqual(r.absolute_charge_mC, 0.6, places=9)
        # 单相净电荷等于绝对电荷
        self.assertAlmostEqual(r.net_charge_mC, r.absolute_charge_mC, places=9)

    def test_biphasic_net_zero(self):
        p = StimulationParameters(
            mode=MODE_PULSE, waveform="电荷平衡双相脉冲", phases="双相",
            current_value_mA=1.0, pulse_width_us=100.0, pulses_per_second=100.0, duration_min=1.0,
        )
        r = compute(p)
        self.assertAlmostEqual(r.net_charge_mC, 0.0, places=9)
        self.assertGreater(r.absolute_charge_mC, 0.0)


class TestSamples(unittest.TestCase):
    def test_sine_sampling_matches_analytic(self):
        # 1 kHz 正弦，峰值 2 mA，采样 1 个周期（40 点）
        n = 4000
        freq = 1000.0
        peak = 2.0
        dt = (1.0 / freq) / 400
        currents = [peak * math.sin(2 * math.pi * freq * i * dt) for i in range(n)]
        s = analyze_samples(currents, sample_interval_s=dt)
        self.assertAlmostEqual(s.peak_mA, peak, places=2)
        self.assertAlmostEqual(s.rms_mA, peak / math.sqrt(2.0), places=2)
        self.assertAlmostEqual(s.mean_abs_mA, peak * 2.0 / math.pi, places=2)
        self.assertAlmostEqual(s.net_charge_mC, 0.0, places=2)

    def test_insufficient_points(self):
        s = analyze_samples([1.0])
        self.assertEqual(s.sample_count, 1)
        self.assertTrue(s.notes)


class TestRules(unittest.TestCase):
    def test_within_literature_range_passes(self):
        p = StimulationParameters(mode=MODE_TDCS, current_value_mA=2.0, duration_min=20.0, area_cm2=20.0)
        r = compute(p)
        checks = evaluate_rules(p, r, ProjectConstraints(use_duration=False))
        statuses = {c.rule.rule_id: c.status for c in checks}
        self.assertEqual(statuses["LIT-CURRENT-001"], STATUS_PASS)
        self.assertEqual(statuses["LIT-DURATION-001"], STATUS_PASS)
        self.assertEqual(statuses["LIT-AREA-001"], STATUS_PASS)

    def test_exceeds_literature_range_flags_violation(self):
        p = StimulationParameters(mode=MODE_TDCS, current_value_mA=6.0, duration_min=90.0, area_cm2=0.5)
        r = compute(p)
        checks = evaluate_rules(p, r, ProjectConstraints(use_duration=False))
        statuses = {c.rule.rule_id: c.status for c in checks}
        self.assertEqual(statuses["LIT-CURRENT-001"], STATUS_VIOLATION)
        self.assertEqual(statuses["LIT-DURATION-001"], STATUS_VIOLATION)
        self.assertEqual(statuses["LIT-AREA-001"], STATUS_VIOLATION)

    def test_ti_requires_special_verification(self):
        p = StimulationParameters(mode=MODE_TI, waveform="多通道多频")
        r = compute(p)
        checks = evaluate_rules(p, r, ProjectConstraints(use_duration=False))
        statuses = {c.rule.rule_id: c.status for c in checks}
        self.assertEqual(statuses["ENG-TI-001"], STATUS_INSUFFICIENT)
        self.assertEqual(statuses["DEV-LEVEL-001"], STATUS_INSUFFICIENT)
        self.assertIsNone(r.charge_density_absolute_mC_cm2)

    def test_project_constraint_violation(self):
        p = StimulationParameters(mode=MODE_TDCS, current_value_mA=2.0, area_cm2=10.0)
        r = compute(p)  # J = 0.2 mA/cm²
        constraints = ProjectConstraints(use_current_density=True,
                                         current_density_limit_mA_cm2=0.1,
                                         use_duration=False)
        checks = evaluate_rules(p, r, constraints)
        statuses = {c.rule.rule_id: c.status for c in checks}
        self.assertEqual(statuses["PRJ-J-001"], STATUS_VIOLATION)

    def test_pulse_current_marked_insufficient(self):
        p = StimulationParameters(mode=MODE_PULSE, waveform="单相脉冲")
        r = compute(p)
        checks = evaluate_rules(p, r, ProjectConstraints(use_duration=False))
        statuses = {c.rule.rule_id: c.status for c in checks}
        self.assertEqual(statuses["LIT-CURRENT-001"], STATUS_INSUFFICIENT)


class TestReport(unittest.TestCase):
    def test_csv_bytes_have_bom_and_rows(self):
        p = StimulationParameters()
        r = compute(p)
        checks = evaluate_rules(p, r, ProjectConstraints())
        row = {"a": 1, "b": "中文"}
        data = rows_to_csv_bytes([row])
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        self.assertIn("中文".encode("utf-8"), data)

    def test_csv_supports_heterogeneous_rows(self):
        # 回归：两行字段不同时不应抛 ValueError
        from tes_core import build_calculation_record, build_parameter_record, merge_records_for_csv

        p = StimulationParameters()
        r = compute(p)
        rows = [build_parameter_record(p, ProjectConstraints()), build_calculation_record(r)]
        data = rows_to_csv_bytes(rows)
        self.assertGreater(len(data), 0)
        text = data.decode("utf-8-sig")
        self.assertIn("刺激类型", text)
        self.assertIn("峰值电流密度_mA_cm2", text)

        flat = merge_records_for_csv({"输入参数": build_parameter_record(p, ProjectConstraints())})
        self.assertTrue(all(set(row) == {"分类", "项目", "数值"} for row in flat))


if __name__ == "__main__":
    unittest.main(verbosity=2)
