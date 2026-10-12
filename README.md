# 经颅电刺激仪安全设计计算器（tES Safety Design Calculator）

面向 **医疗器械研发与设计审查** 的工程计算与约束筛查工具，**原生 Windows 桌面程序（Python + Qt）**。

输入刺激类型、波形、电极形式与面积、电流、时长等参数后，自动计算电流密度、电荷、
功率、能量与合规电压需求，依据**带来源的规则库**输出筛查结论，并导出可追溯审查记录。

> ⚠️ **本工具只计算物理量并筛查“已录入的”设计约束，不输出“人体绝对安全”结论。**
> 文献常见范围不是法规限值；未经风险分析、台架验证、必要的建模与临床/伦理审查，
> 不得将结果用于人体刺激或作为注册合规证明。

---

## 一、为什么用 Qt 而不是网页版

早期版本用 Streamlit（浏览器 + 本地服务）。改成原生 Qt 后：

| 对比项 | Streamlit 网页版 | 原生 Qt 版（当前） |
| --- | --- | --- |
| 运行形态 | 需启动本地服务 + 打开浏览器 | 双击 exe 直接出窗口 |
| 运行时依赖 | streamlit / pandas / numpy / pyarrow / reportlab | 仅 PySide6 + openpyxl |
| 打包体积 | exe ≈ 322 MB（onedir） | **54.8 MB（单文件）** |
| 启动耗时 | 服务 ~1 s + 浏览器加载前端 1.94 MB JS + WebSocket 握手 | **≈ 3.0 s（单文件）/ ≈ 1.0 s（目录版）** |
| 离线/内网 | 需空闲端口 | 无网络、无端口要求 |

---

## 二、目录结构

```
TES safe/
├── tes_qt_app.py            # Qt 桌面程序入口（PySide6）
├── tes_core/                # 核心库（与界面完全解耦，仅标准库）
│   ├── __init__.py          # 对外 API
│   ├── models.py            # 数据模型与常量（需求模块 1 的数据结构）
│   ├── waveforms.py         # 公式计算引擎 + 波形采样积分（模块 2 / A）
│   ├── safety_rules.py      # 可追溯安全规则引擎与规则库（模块 3 / C）
│   └── report.py            # 报告导出 CSV / Excel / HTML(PDF)（模块 4 / D）
├── tests/                   # 单元测试（核心逻辑 + 导出 + Qt 界面）
│   ├── test_core.py
│   ├── test_export.py
│   └── test_qt_app.py
├── tools/screenshot_qt.py   # 无显示器环境下把界面渲染成 PNG
├── build_exe.ps1            # 一键打包脚本
├── requirements.txt
└── 需求.md
```

---

## 三、运行与打包

### 1. 直接运行（开发/调试）

```powershell
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
python tes_qt_app.py
```

### 2. 打包成 exe

```powershell
# 单文件版（推荐分发给用户，双击即用）→ dist-onefile\TES-Safety-Calculator.exe
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1

# 目录版（启动最快）→ dist-onedir\TES-Safety-Calculator\TES-Safety-Calculator.exe
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -Mode onedir

# 需要看报错时加 -Console（保留控制台窗口）
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -Mode onedir -Console
```

### 3. 免显示器自检（验证打包结果）

```powershell
.\dist-onefile\TES-Safety-Calculator.exe --selftest
# 退出码 0 = 窗口构建 + 计算 + 规则筛查 + PDF 导出全部正常
```

### 4. 运行测试

```powershell
$env:QT_QPA_PLATFORM="offscreen"   # 无显示器时
python -m unittest discover -s tests -v
```

---

## 四、启动速度实测数据（本机）

| 形态 | 第 1 次 | 第 2 次 | 第 3 次 | 体积 |
| --- | --- | --- | --- | --- |
| 单文件 `--onefile` | 5.11 s | 3.03 s | 3.05 s | 54.8 MB（单文件） |
| 目录版 `--onedir` | 1.03 s | 1.01 s | 1.01 s | 3.2 MB exe + 130 MB 目录 |

**结论：单文件版每次启动都要把约 55 MB 内容解压到 `%TEMP%`，这是它比目录版慢约 3 倍的全部原因。**
对启动速度敏感就分发目录版（可把整个目录压缩后分发，或做快捷方式）。

---

## 五、四个子系统与需求对应关系

| 需求 | 实现位置 | 说明 |
| --- | --- | --- |
| 模块 1 刺激参数输入 | `tes_qt_app.py` + `models.py` | 刺激类型、恒流/恒压、峰值/RMS、频率、脉宽、相位、面积、时长、阻抗、每日次数 |
| 模块 2 公式计算引擎 | `waveforms.py` | 电流密度、电荷量、电荷密度、输出功率、能量、合规电压需求；**按波形族分别计算** |
| 模块 3 安全规则引擎 | `safety_rules.py` | 输出 **满足已配置约束 / 超出设计约束 / 证据不足，需验证** 三类状态 |
| 模块 4 报告与追溯 | `report.py` | 导出 CSV / Excel / HTML / PDF，含输入、公式口径、规则来源、标准版本、风险项与待验证项 |

补充子系统：

- **A. 刺激剂量计算引擎**：`analyze_samples()` 对实测/仿真采样波形做梯形积分，得到峰值、
  峰峰值、RMS、平均绝对电流、净电荷与绝对电荷，避免把不同波形套同一个公式。
- **B. 电极与组织建模**：记录电极形式与有效接触面积，对 ≤5 cm² 或 HD 电极强制专项验证；
  与 ROAST / SimNIBS 的电场仿真衔接属于后续扩展。
- **C. 安全规则数据库**：`rule_catalog()` 中每条规则都带**适用模式、来源、版本、证据等级、验证状态**。
- **D. 风险与验证报告**：设备级安全、波形审查、多通道分配等以“必须专项验证”形式进入报告。

---

## 六、当前计算能力与边界

| 刺激类型 | 当前支持 | 需后续扩展 |
| --- | --- | --- |
| tDCS 直流 | 电流密度、累计电荷、电荷密度、负载估算 | 电极界面模型、完整安全验证 |
| tACS 交流 | 峰值/峰峰值/RMS 换算、绝对电荷积分、负载估算 | 实测波形积分、频率相关评价 |
| tRNS 随机噪声 | 基础参数记录与约束筛查 | 真实随机波形的峰值/RMS/电荷分析 |
| 脉冲及双相 | 矩形脉冲电荷近似、单相/双相净电荷区分 | 实测波形积分、电荷平衡与残余直流检测 |
| TI/tTIS | 多模式参数记录、专项审查提示 | 多通道载波建模、脑内包络场、个体化仿真 |

---

## 七、关键设计约束

- 状态输出**严格限定为三类**，不使用“安全 / 不安全”这类绝对结论。
- 文献范围（≤4 mA、≤60 min、1–100 cm²）作为**参考性提示**，与项目自定义阈值分开管理。
- 项目阈值属于**用户输入**，其证据、批准与验证状态由项目负责人负责。
- IEC 60601-2-10 的适用范围需结合预期用途确认，不能假定自动覆盖所有经颅脑刺激设备。
- 核心库 `tes_core` **不依赖任何 GUI 框架**，可被 Qt / 命令行 / 未来的其他界面复用。

---

## 八、依据

- 低强度 tES 安全指南（2025 年更新、2026 年刊出）：https://pmc.ncbi.nlm.nih.gov/articles/PMC7618810/
- IEC 60601-2-10 官方标准页面：https://webstore.iec.ch/en/publication/81814
- 原文存档：[`docs/EMS212626.pdf`](docs/EMS212626.pdf) —— 上述指南正文，
  是 `tes_core/safety_rules.py` 中各条规则（`LIT-CURRENT-001`、`LIT-DURATION-001`、
  `LIT-AREA-001`）的证据来源，便于审查时逐条回溯。
