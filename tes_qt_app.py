"""经颅电刺激（tES）安全设计计算器 —— 原生 Qt 桌面版（PySide6）。

与旧版 Streamlit 网页版的区别：
  * 不需要浏览器、不需要本地服务器，双击即用；
  * 不依赖 pandas / numpy / pyarrow / reportlab，体积小、启动快；
  * 全部计算与规则判定仍由 ``tes_core`` 完成（同一套可追溯规则库）。

运行：
    python tes_qt_app.py            正常启动图形界面
    python tes_qt_app.py --selftest 无界面自检（用于打包后验证 exe 是否可用）
"""

from __future__ import annotations

import csv
import os
import sys
from typing import Dict, List, Optional

from PySide6.QtCore import QMarginsF, QSizeF, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from tes_core import (
    STATUS_INSUFFICIENT,
    STATUS_PASS,
    STATUS_VIOLATION,
    ProjectConstraints,
    StimulationParameters,
    __version__,
    analyze_samples,
    build_calculation_record,
    build_check_records,
    build_excel_sheets,
    build_parameter_record,
    build_report_html,
    build_sample_record,
    build_summary,
    compute,
    evaluate_rules,
    merge_records_for_csv,
    rows_to_csv_bytes,
    rule_catalog_records,
    sheets_to_excel_bytes,
)
from tes_core.models import (
    CURRENT_DEFINITIONS,
    ELECTRODE_TYPES,
    PHASES_OPTIONS,
    STIM_MODES,
    WAVEFORMS,
)

APP_TITLE = "经颅电刺激（tES）安全设计计算器"

STATUS_COLORS = {
    STATUS_VIOLATION: "#c0392b",
    STATUS_INSUFFICIENT: "#b9770e",
    STATUS_PASS: "#1e8449",
}

DISCLAIMER = (
    "重要声明：本工具只计算物理量并筛查**已录入的**设计约束，不输出“人体绝对安全”结论。"
    "文献常见范围不是法规限值。未经风险分析、台架验证、必要的建模与临床/伦理审查，"
    "不得将结果用于人体刺激或作为注册合规证明。"
)

REFERENCE_TEXT = """
<h3>使用边界与依据</h3>
<ul>
<li>低强度 tES 安全指南（2025 年更新、2026 年刊出）将 <b>≤4 mA（交流波形按峰峰值定义）</b>、
单次 <b>≤60 min</b>、电极面积 <b>1–100 cm²</b> 描述为研究中<b>常见范围</b>；
指南明确说明这些<b>不是</b>固定或绝对安全阈值。</li>
<li>电极面积应指<b>电解质/导电介质与皮肤之间实际导电的界面面积</b>，不是外壳或金属片名义面积。</li>
<li>TI/tTIS、tACS、tRNS 与小面积电极需分别定义适用模型、波形指标与验证要求，
<b>不能</b>把 tDCS 的安全阈值直接套用过去。</li>
<li>标准适用性需结合预期用途与产品分类确认：IEC 60601-2-10 的范围有排除条款，
不能假定它自动覆盖所有经颅脑刺激设备。</li>
<li>参考：https://pmc.ncbi.nlm.nih.gov/articles/PMC7618810/ ｜
https://webstore.iec.ch/en/publication/81814</li>
</ul>
<h3>扫描结论只有三类</h3>
<ul>
<li><b style="color:#1e8449">满足已配置约束</b>：未超出<b>已录入</b>的约束（不代表设备对人体安全）；</li>
<li><b style="color:#c0392b">超出设计约束</b>：超出已录入的设计阈值；</li>
<li><b style="color:#b9770e">证据不足，需验证</b>：现有证据不足以判定，必须专项验证。</li>
</ul>
<h3>计算口径</h3>
<ul>
<li>电流密度 <code>J = I/A</code>（平均值）；直流累计电荷 <code>Q = I·t</code>，电荷密度 <code>σ = Q/A</code>。</li>
<li>正弦：<code>I_RMS = I_peak/√2</code>，<code>I_pp = 2·I_peak</code>，
绝对电荷按 <code>(2/π)·I_peak·t</code> 估算；净电荷接近零<b>不代表</b>没有剂量。</li>
<li>脉冲：<code>Q_phase = I_phase × t_phase</code>，总电荷按相数×脉冲数累计；
双相按理想电荷平衡处理，须实测两相面积差。</li>
<li>欧姆近似：<code>V ≈ I·R</code>、<code>P ≈ I_RMS²·R</code>、<code>E ≈ P·t</code>，
仅用于初步估算，不能替代电气安全试验。</li>
</ul>
"""


# --------------------------------------------------------------------------- #
# 小部件
# --------------------------------------------------------------------------- #
class MetricCard(QFrame):
    """一个“数值 + 名称”的指标卡片。"""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "MetricCard { background:#f6f8fa; border:1px solid #d0d7de; border-radius:6px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        self.value_label = QLabel("—")
        font = self.value_label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.value_label.setFont(font)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color:#57606a;")
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)


def _fmt(value: Optional[float], unit: str = "", digits: int = 4) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f} {unit}".strip()


# --------------------------------------------------------------------------- #
# 主窗口
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE}  v{__version__}")
        self.resize(1480, 940)

        self._sample = None  # 实测波形分析结果
        self._sample_source = ""
        self._checks = []
        self._result = None
        self._params = None
        self._constraints = None

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_input_panel())
        splitter.addWidget(self._build_result_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([520, 960])
        self.setCentralWidget(splitter)

        self._build_menu()
        self.statusBar().showMessage("就绪")

        self._connect_signals()
        self._recompute()

    # ---------------------------------------------------------------- 左侧输入
    def _build_input_panel(self) -> QWidget:
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        banner = QLabel(DISCLAIMER.replace("**", ""))
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background:#fdecea; border:1px solid #f5c6cb; color:#842029;"
            "border-radius:6px; padding:8px;"
        )
        outer.addWidget(banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        form = QVBoxLayout(content)
        form.setContentsMargins(2, 2, 2, 2)
        form.setSpacing(8)

        # --- 1 刺激模式与电极 ---------------------------------------------
        box1 = QGroupBox("1. 刺激模式与电极参数")
        f1 = QFormLayout(box1)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(STIM_MODES)
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(WAVEFORMS)
        self.electrode_combo = QComboBox()
        self.electrode_combo.addItems(ELECTRODE_TYPES)
        self.area_spin = self._dspin(0.01, 200.0, 22.9, 0.1, 2, "cm²")
        self.channels_spin = self._ispin(1, 32, 2)
        self.sessions_spin = self._ispin(1, 20, 1)
        f1.addRow("刺激类型", self.mode_combo)
        f1.addRow("输出波形/定义", self.waveform_combo)
        f1.addRow("电极形式", self.electrode_combo)
        f1.addRow("有效接触面积", self.area_spin)
        f1.addRow("通道数", self.channels_spin)
        f1.addRow("每天会话数", self.sessions_spin)
        form.addWidget(box1)

        # --- 2 电气与时间 -------------------------------------------------
        box2 = QGroupBox("2. 电气与时间参数")
        f2 = QFormLayout(box2)
        self.current_spin = self._dspin(0.0, 100.0, 2.0, 0.1, 3, "mA")
        self.definition_combo = QComboBox()
        self.definition_combo.addItems(CURRENT_DEFINITIONS)
        self.duration_spin = self._dspin(0.0, 240.0, 30.0, 1.0, 2, "min")
        self.frequency_spin = self._dspin(0.0, 100000.0, 0.0, 1.0, 1, "Hz")
        self.impedance_spin = self._dspin(0.0, 1_000_000.0, 5000.0, 100.0, 1, "Ω")
        self.compliance_spin = self._dspin(0.0, 1000.0, 30.0, 1.0, 1, "V")
        f2.addRow("电流幅值", self.current_spin)
        f2.addRow("电流幅值定义", self.definition_combo)
        f2.addRow("单次刺激时长", self.duration_spin)
        f2.addRow("频率", self.frequency_spin)
        f2.addRow("用于估算的负载阻抗", self.impedance_spin)
        f2.addRow("合规电压/输出限压", self.compliance_spin)
        form.addWidget(box2)

        # --- 3 脉冲参数 ---------------------------------------------------
        box3 = QGroupBox("3. 脉冲参数（仅脉冲模式使用）")
        f3 = QFormLayout(box3)
        self.pulse_width_spin = self._dspin(0.0, 100000.0, 200.0, 10.0, 1, "µs")
        self.pps_spin = self._dspin(0.0, 100000.0, 1.0, 1.0, 1, "pps")
        self.phases_combo = QComboBox()
        self.phases_combo.addItems(PHASES_OPTIONS)
        self.phases_combo.setCurrentText("双相")
        f3.addRow("单相脉宽", self.pulse_width_spin)
        f3.addRow("每秒脉冲数", self.pps_spin)
        f3.addRow("每个脉冲的相数", self.phases_combo)
        form.addWidget(box3)

        # --- 4 项目约束 ---------------------------------------------------
        box4 = QGroupBox("4. 项目设计约束（由项目负责人/风险管理确定）")
        f4 = QFormLayout(box4)
        self.use_current_check = QCheckBox("启用电流幅值约束")
        self.current_limit_spin = self._dspin(0.0, 100.0, 4.0, 0.1, 3, "mA")
        self.use_j_check = QCheckBox("启用电流密度约束")
        self.j_limit_spin = self._dspin(0.0, 1000.0, 0.1, 0.01, 4, "mA/cm²")
        self.use_q_check = QCheckBox("启用电荷密度约束")
        self.q_limit_spin = self._dspin(0.0, 100000.0, 200.0, 10.0, 3, "mC/cm²")
        self.use_time_check = QCheckBox("启用单次时长约束")
        self.use_time_check.setChecked(True)
        self.time_limit_spin = self._dspin(0.0, 240.0, 30.0, 5.0, 2, "min")
        f4.addRow(self.use_current_check, self.current_limit_spin)
        f4.addRow(self.use_j_check, self.j_limit_spin)
        f4.addRow(self.use_q_check, self.q_limit_spin)
        f4.addRow(self.use_time_check, self.time_limit_spin)
        form.addWidget(box4)

        # --- 5 实测波形 ---------------------------------------------------
        box5 = QGroupBox("5. 可选：实测/仿真波形采样分析")
        v5 = QVBoxLayout(box5)
        hint = QLabel(
            "用于 tACS / tRNS / 脉冲等波形：导入含“时间_s,电流_mA”两列的 CSV，"
            "按实测序列积分得到峰值、RMS、净电荷与绝对电荷。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#57606a;")
        v5.addWidget(hint)
        row5 = QHBoxLayout()
        self.load_sample_button = QPushButton("导入波形 CSV…")
        self.clear_sample_button = QPushButton("清除")
        self.interval_spin = self._dspin(0.0, 10.0, 0.0, 0.0001, 6, "s")
        self.interval_spin.setToolTip("若 CSV 只有一列电流，请填写采样间隔")
        row5.addWidget(self.load_sample_button)
        row5.addWidget(self.clear_sample_button)
        v5.addLayout(row5)
        samp_form = QFormLayout()
        samp_form.addRow("采样间隔（单列时）", self.interval_spin)
        v5.addLayout(samp_form)
        self.sample_label = QLabel("未导入实测波形")
        self.sample_label.setWordWrap(True)
        self.sample_label.setStyleSheet("color:#57606a;")
        v5.addWidget(self.sample_label)
        form.addWidget(box5)

        form.addStretch(1)

        row_reset = QHBoxLayout()
        self.reset_button = QPushButton("恢复默认参数")
        row_reset.addWidget(self.reset_button)
        row_reset.addStretch(1)
        form.addLayout(row_reset)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        return panel

    # ---------------------------------------------------------------- 右侧结果
    def _build_result_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        self.family_label = QLabel("计算结果")
        font = self.family_label.font()
        font.setBold(True)
        font.setPointSize(11)
        self.family_label.setFont(font)
        layout.addWidget(self.family_label)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.cards: Dict[str, MetricCard] = {}
        card_defs = [
            ("j_peak", "峰值电流密度"), ("j_rms", "RMS 电流密度"),
            ("j_am2", "换算 A/m²（峰值）"), ("voltage", "估算峰值电压 I×R"),
            ("power", "估算负载功率 I²R"), ("energy", "负载耗散能量"),
            ("q_abs", "绝对电荷"), ("q_net", "净电荷"),
            ("sigma_abs", "电荷密度（绝对）"), ("q_phase", "每相电荷"),
            ("duration", "单次时长"), ("daily", "每日总时长"),
        ]
        for index, (key, title) in enumerate(card_defs):
            card = MetricCard(title)
            self.cards[key] = card
            grid.addWidget(card, index // 4, index % 4)
        layout.addLayout(grid)

        self.notes_browser = QTextBrowser()
        self.notes_browser.setMaximumHeight(96)
        self.notes_browser.setStyleSheet("background:#f6f8fa; border:1px solid #d0d7de;")
        layout.addWidget(self.notes_browser)

        self.summary_label = QLabel("规则筛查")
        self.summary_label.setFont(font)
        layout.addWidget(self.summary_label)

        self.rules_table = QTableWidget(0, 5)
        self.rules_table.setHorizontalHeaderLabels(["规则编号", "类别", "状态", "说明", "来源 / 版本"])
        self.rules_table.verticalHeader().setVisible(False)
        self.rules_table.setWordWrap(True)
        self.rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rules_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.rules_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.rules_table.setColumnWidth(4, 260)
        layout.addWidget(self.rules_table, 1)

        grid_buttons = QGridLayout()
        grid_buttons.setSpacing(6)
        self.export_param_button = QPushButton("导出 参数+结果 (CSV)")
        self.export_checks_button = QPushButton("导出 规则筛查 (CSV)")
        self.export_rules_button = QPushButton("导出 规则依据 (CSV)")
        self.export_excel_button = QPushButton("导出 完整追溯报告 (Excel)")
        self.export_pdf_button = QPushButton("导出 审查报告 (PDF)")
        self.export_html_button = QPushButton("导出 审查报告 (HTML)")
        grid_buttons.addWidget(self.export_param_button, 0, 0)
        grid_buttons.addWidget(self.export_checks_button, 0, 1)
        grid_buttons.addWidget(self.export_rules_button, 0, 2)
        grid_buttons.addWidget(self.export_excel_button, 1, 0)
        grid_buttons.addWidget(self.export_pdf_button, 1, 1)
        grid_buttons.addWidget(self.export_html_button, 1, 2)
        layout.addLayout(grid_buttons)

        return panel

    # ---------------------------------------------------------------- 菜单
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件(&F)")
        act_pdf = QAction("导出审查报告 (PDF)…", self)
        act_pdf.triggered.connect(self._export_pdf)
        file_menu.addAction(act_pdf)
        act_excel = QAction("导出完整追溯报告 (Excel)…", self)
        act_excel.triggered.connect(self._export_excel)
        file_menu.addAction(act_excel)
        file_menu.addSeparator()
        act_quit = QAction("退出(&X)", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        help_menu = self.menuBar().addMenu("帮助(&H)")
        act_ref = QAction("使用边界与依据…", self)
        act_ref.triggered.connect(self._show_reference)
        help_menu.addAction(act_ref)
        act_about = QAction("关于…", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # ---------------------------------------------------------------- 控件工厂
    @staticmethod
    def _dspin(minimum: float, maximum: float, value: float, step: float,
               decimals: int, suffix: str = "") -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(decimals)
        box.setSingleStep(step)
        box.setValue(value)
        if suffix:
            box.setSuffix(" " + suffix)
        box.setKeyboardTracking(False)  # 输入过程中不逐字符重算
        box.setMinimumWidth(150)
        return box

    @staticmethod
    def _ispin(minimum: int, maximum: int, value: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        box.setKeyboardTracking(False)
        box.setMinimumWidth(150)
        return box

    def _connect_signals(self) -> None:
        for widget in (
            self.mode_combo, self.waveform_combo, self.electrode_combo,
            self.definition_combo, self.phases_combo,
        ):
            widget.currentIndexChanged.connect(self._recompute)
        for widget in (
            self.area_spin, self.channels_spin, self.sessions_spin,
            self.current_spin, self.duration_spin, self.frequency_spin,
            self.impedance_spin, self.compliance_spin,
            self.pulse_width_spin, self.pps_spin,
            self.current_limit_spin, self.j_limit_spin,
            self.q_limit_spin, self.time_limit_spin,
        ):
            widget.valueChanged.connect(self._recompute)
        for widget in (
            self.use_current_check, self.use_j_check,
            self.use_q_check, self.use_time_check,
        ):
            widget.toggled.connect(self._recompute)

        self.load_sample_button.clicked.connect(self._load_sample)
        self.clear_sample_button.clicked.connect(self._clear_sample)
        self.reset_button.clicked.connect(self._reset)

        self.export_param_button.clicked.connect(self._export_param_csv)
        self.export_checks_button.clicked.connect(self._export_checks_csv)
        self.export_rules_button.clicked.connect(self._export_rules_csv)
        self.export_excel_button.clicked.connect(self._export_excel)
        self.export_pdf_button.clicked.connect(self._export_pdf)
        self.export_html_button.clicked.connect(self._export_html)

    # ---------------------------------------------------------------- 读取输入
    def _read_params(self) -> StimulationParameters:
        return StimulationParameters(
            mode=self.mode_combo.currentText(),
            waveform=self.waveform_combo.currentText(),
            current_definition=self.definition_combo.currentText(),
            current_value_mA=self.current_spin.value(),
            frequency_hz=self.frequency_spin.value(),
            pulse_width_us=self.pulse_width_spin.value(),
            pulses_per_second=self.pps_spin.value(),
            phases=self.phases_combo.currentText(),
            electrode_type=self.electrode_combo.currentText(),
            area_cm2=self.area_spin.value(),
            channels=self.channels_spin.value(),
            duration_min=self.duration_spin.value(),
            sessions_per_day=self.sessions_spin.value(),
            impedance_ohm=self.impedance_spin.value(),
            compliance_voltage_V=self.compliance_spin.value(),
        )

    def _read_constraints(self) -> ProjectConstraints:
        return ProjectConstraints(
            use_current_amplitude=self.use_current_check.isChecked(),
            current_amplitude_limit_mA=self.current_limit_spin.value(),
            use_current_density=self.use_j_check.isChecked(),
            current_density_limit_mA_cm2=self.j_limit_spin.value(),
            use_charge_density=self.use_q_check.isChecked(),
            charge_density_limit_mC_cm2=self.q_limit_spin.value(),
            use_duration=self.use_time_check.isChecked(),
            duration_limit_min=self.time_limit_spin.value(),
        )

    # ---------------------------------------------------------------- 计算
    def _recompute(self, *_args) -> None:
        params = self._read_params()
        constraints = self._read_constraints()
        result = compute(params)
        checks = evaluate_rules(params, result, constraints)

        self._params, self._constraints, self._result, self._checks = params, constraints, result, checks

        self.family_label.setText(f"计算结果（波形族：{result.family_label}）")
        self.cards["j_peak"].set_value(_fmt(result.current_density_peak_mA_cm2, "mA/cm²"))
        self.cards["j_rms"].set_value(_fmt(result.current_density_rms_mA_cm2, "mA/cm²"))
        self.cards["j_am2"].set_value(_fmt(result.current_density_peak_A_m2, "A/m²", 3))
        self.cards["voltage"].set_value(_fmt(result.peak_voltage_V, "V", 2))
        self.cards["power"].set_value(_fmt(result.power_W, "W"))
        self.cards["energy"].set_value(_fmt(result.energy_J, "J", 2))
        self.cards["q_abs"].set_value(_fmt(result.absolute_charge_mC, "mC", 3))
        self.cards["q_net"].set_value(_fmt(result.net_charge_mC, "mC", 3))
        self.cards["sigma_abs"].set_value(_fmt(result.charge_density_absolute_mC_cm2, "mC/cm²", 3))
        self.cards["q_phase"].set_value(_fmt(result.charge_per_phase_mC, "mC", 4))
        self.cards["duration"].set_value(_fmt(params.duration_min, "min", 1))
        self.cards["daily"].set_value(_fmt(result.daily_total_duration_min, "min", 1))

        notes = list(result.notes)
        if self._sample is not None:
            notes.append(
                f"已导入实测波形（{self._sample_source or 'CSV'}）：峰值 {self._sample.peak_mA:.4f} mA、"
                f"峰峰值 {self._sample.pp_mA:.4f} mA、RMS {self._sample.rms_mA:.4f} mA、"
                f"净电荷 {self._sample.net_charge_mC:.4f} mC、绝对电荷 {self._sample.absolute_charge_mC:.4f} mC。"
                "实测值应优先于简化公式结果。"
            )
            notes.extend(self._sample.notes)
        self.notes_browser.setHtml(
            "<ul style='margin-left:-20px;'>"
            + "".join(f"<li>{n}</li>" for n in notes)
            + "</ul>"
        )

        summary = build_summary(checks)
        self.summary_label.setText(
            f"规则筛查：满足已配置约束 {summary.get(STATUS_PASS, 0)} ｜ "
            f"超出设计约束 {summary.get(STATUS_VIOLATION, 0)} ｜ "
            f"证据不足，需验证 {summary.get(STATUS_INSUFFICIENT, 0)} ｜ "
            f"合计 {summary.get('合计', 0)}"
        )
        self._fill_rules_table(checks)
        self.statusBar().showMessage("已重新计算")

    def _fill_rules_table(self, checks) -> None:
        table = self.rules_table
        table.setRowCount(len(checks))
        for row, check in enumerate(checks):
            values = [
                check.rule.rule_id,
                check.rule.category,
                check.status,
                check.message,
                f"{check.rule.source}（{check.rule.source_version}）",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(str(text))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 2:
                    item.setForeground(QBrush(QColor(STATUS_COLORS.get(check.status, "#000000"))))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if col == 4:
                    item.setToolTip(
                        f"证据等级：{check.rule.evidence_level}\n验证状态：{check.rule.validation_status}\n"
                        f"适用模式：{'、'.join(check.rule.applies_modes)}"
                    )
                table.setItem(row, col, item)
        table.resizeRowsToContents()

    # ---------------------------------------------------------------- 波形导入
    def _load_sample(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择波形采样 CSV", "", "CSV 文件 (*.csv);;所有文件 (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as handle:
                rows = [r for r in csv.reader(handle) if r and any(str(x).strip() for x in r)]
        except OSError as exc:
            QMessageBox.critical(self, "读取失败", f"无法读取文件：\n{exc}")
            return

        if not rows:
            QMessageBox.warning(self, "空文件", "CSV 中没有可用数据。")
            return

        first = [str(x).strip().lower() for x in rows[0]]
        looks_header = any(
            h in ("time_s", "time", "t", "时间_s", "时间", "current_ma", "current", "i", "电流_ma", "电流")
            for h in first
        )
        data_rows = rows[1:] if looks_header else rows

        times: List[float] = []
        currents: List[float] = []
        for row in data_rows:
            try:
                if len(row) >= 2:
                    times.append(float(row[0]))
                    currents.append(float(row[1]))
                else:
                    currents.append(float(row[0]))
            except ValueError:
                continue

        if len(currents) < 2:
            QMessageBox.warning(self, "数据不足", "有效采样点少于 2 个，无法积分。")
            return

        interval = self.interval_spin.value()
        sample = analyze_samples(
            currents,
            sample_interval_s=interval if interval > 0 else None,
            times_s=times if len(times) == len(currents) else None,
        )
        if sample.sample_count == 0 or sample.duration_s <= 0:
            QMessageBox.warning(self, "无法解析", "；".join(sample.notes) or "采样数据无法解析。")
            return

        self._sample = sample
        self._sample_source = os.path.basename(path)
        self.sample_label.setText(
            f"已导入：{os.path.basename(path)}\n"
            f"采样点 {sample.sample_count} ｜ 时长 {sample.duration_s:.4f} s ｜ "
            f"峰值 {sample.peak_mA:.4f} mA ｜ RMS {sample.rms_mA:.4f} mA ｜ "
            f"绝对电荷 {sample.absolute_charge_mC:.4f} mC"
        )
        self._recompute()

    def _clear_sample(self) -> None:
        self._sample = None
        self._sample_source = ""
        self.sample_label.setText("未导入实测波形")
        self._recompute()

    def _reset(self) -> None:
        defaults = StimulationParameters()
        self.mode_combo.setCurrentText(defaults.mode)
        self.waveform_combo.setCurrentText(defaults.waveform)
        self.electrode_combo.setCurrentText(defaults.electrode_type)
        self.definition_combo.setCurrentText(defaults.current_definition)
        self.phases_combo.setCurrentText(defaults.phases)
        self.area_spin.setValue(defaults.area_cm2)
        self.channels_spin.setValue(defaults.channels)
        self.sessions_spin.setValue(defaults.sessions_per_day)
        self.current_spin.setValue(defaults.current_value_mA)
        self.duration_spin.setValue(defaults.duration_min)
        self.frequency_spin.setValue(defaults.frequency_hz)
        self.impedance_spin.setValue(defaults.impedance_ohm)
        self.compliance_spin.setValue(defaults.compliance_voltage_V)
        self.pulse_width_spin.setValue(defaults.pulse_width_us)
        self.pps_spin.setValue(defaults.pulses_per_second)
        for check, spin, value in (
            (self.use_current_check, self.current_limit_spin, 4.0),
            (self.use_j_check, self.j_limit_spin, 0.1),
            (self.use_q_check, self.q_limit_spin, 200.0),
            (self.use_time_check, self.time_limit_spin, 30.0),
        ):
            spin.setValue(value)
        self.use_current_check.setChecked(False)
        self.use_j_check.setChecked(False)
        self.use_q_check.setChecked(False)
        self.use_time_check.setChecked(True)
        self._clear_sample()
        self.statusBar().showMessage("已恢复默认参数")

    # ---------------------------------------------------------------- 导出
    def _records(self):
        params, constraints, result, checks = self._params, self._constraints, self._result, self._checks
        return (
            build_parameter_record(params, constraints),
            build_calculation_record(result),
            build_check_records(checks),
            build_sample_record(self._sample),
        )

    def _save(self, data: bytes, default_name: str, file_filter: str) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "保存文件", default_name, file_filter)
        if not path:
            return False
        try:
            with open(path, "wb") as handle:
                handle.write(data)
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", f"无法写入文件：\n{exc}")
            return False
        self.statusBar().showMessage(f"已保存：{path}")
        QMessageBox.information(self, "导出完成", f"已保存到：\n{path}")
        return True

    def _export_param_csv(self) -> None:
        param_record, calc_record, _, sample_record = self._records()
        sections = {"输入参数": param_record, "计算结果": calc_record}
        if self._sample is not None:
            sections["实测波形"] = sample_record
        data = rows_to_csv_bytes(merge_records_for_csv(sections))
        self._save(data, "tes_input_and_calc.csv", "CSV 文件 (*.csv)")

    def _export_checks_csv(self) -> None:
        _, _, check_records, _ = self._records()
        self._save(rows_to_csv_bytes(check_records), "tes_rule_checks.csv", "CSV 文件 (*.csv)")

    def _export_rules_csv(self) -> None:
        self._save(rows_to_csv_bytes(rule_catalog_records()), "tes_rule_catalog.csv", "CSV 文件 (*.csv)")

    def _export_excel(self) -> None:
        params, constraints, result, checks = self._params, self._constraints, self._result, self._checks
        data = sheets_to_excel_bytes(build_excel_sheets(params, constraints, result, checks, self._sample))
        if not data:
            QMessageBox.warning(
                self, "Excel 导出不可用",
                "未安装 openpyxl，无法生成 Excel。\n\n请在命令行执行：\n"
                "python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple openpyxl",
            )
            return
        self._save(data, "tes_safety_report.xlsx", "Excel 工作簿 (*.xlsx)")

    def _export_html(self) -> None:
        param_record, calc_record, check_records, sample_record = self._records()
        html_text = build_report_html(
            param_record, calc_record, check_records,
            sample_record if self._sample is not None else None,
        )
        self._save(html_text.encode("utf-8"), "tes_safety_report.html", "HTML 文件 (*.html)")

    def _export_pdf(self) -> None:
        param_record, calc_record, check_records, sample_record = self._records()
        html_text = build_report_html(
            param_record, calc_record, check_records,
            sample_record if self._sample is not None else None,
        )
        path, _ = QFileDialog.getSaveFileName(self, "保存 PDF 报告", "tes_safety_report.pdf", "PDF 文件 (*.pdf)")
        if not path:
            return
        try:
            writer = QPdfWriter(path)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
            writer.setResolution(96)
            document = QTextDocument()
            document.setHtml(html_text)
            rect = writer.pageLayout().paintRectPixels(writer.resolution())
            document.setPageSize(QSizeF(rect.size()))
            document.print_(writer)
        except Exception as exc:  # pragma: no cover - 面向用户兜底
            QMessageBox.critical(self, "PDF 导出失败", str(exc))
            return
        self.statusBar().showMessage(f"已保存：{path}")
        QMessageBox.information(self, "导出完成", f"已保存到：\n{path}")

    # ---------------------------------------------------------------- 帮助
    def _show_reference(self) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("使用边界与依据")
        dialog.setTextFormat(Qt.TextFormat.RichText)
        dialog.setText(REFERENCE_TEXT)
        dialog.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于",
            f"<b>{APP_TITLE}</b><br>版本 {__version__}<br><br>"
            "工程计算与设计审查辅助工具（原生 Qt 桌面版）。<br>"
            "计算与规则引擎位于 <code>tes_core</code>，与界面完全解耦。<br><br>"
            "<b>本工具不输出“人体绝对安全”结论，不能替代标准全文、风险管理文件、"
            "独立安全试验与临床/伦理审查。</b>",
        )


# --------------------------------------------------------------------------- #
# 自检（供打包后的 exe 无界面验证）
# --------------------------------------------------------------------------- #
def run_selftest() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = MainWindow()
    window._recompute()

    problems = []
    if window._result is None or window._params is None:
        problems.append("计算未执行")
    if not window._checks:
        problems.append("规则筛查为空")

    # 试导出 PDF，验证 Qt 打印链路可用
    import tempfile

    param_record, calc_record, check_records, sample_record = window._records()
    html_text = build_report_html(param_record, calc_record, check_records)
    pdf_path = os.path.join(tempfile.mkdtemp(), "selftest.pdf")
    writer = QPdfWriter(pdf_path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    document = QTextDocument()
    document.setHtml(html_text)
    document.print_(writer)
    if not (os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0):
        problems.append("PDF 生成失败")

    excel_ok = "skipped"
    sheets = build_excel_sheets(window._params, window._constraints, window._result, window._checks)
    data = sheets_to_excel_bytes(sheets)
    excel_ok = "ok" if data else "unavailable(openpyxl 缺失)"

    if problems:
        print("[SELFTEST FAILED] " + "；".join(problems))
        return 1
    print(f"[SELFTEST OK] 规则检查 {len(window._checks)} 项；Excel={excel_ok}；PDF=ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return run_selftest()

    app = QApplication(sys.argv)
    for family in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"):
        font = QFont(family, 10)
        if font.exactMatch():
            app.setFont(font)
            break

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
