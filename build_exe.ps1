# Build the Windows executable for the tES Safety Design Calculator (Qt / PySide6).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\build_exe.ps1                 # onefile (single .exe)
#   powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -Mode onedir    # folder output (fastest start)
#   powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -Mode onedir -Console
#
# Notes:
#   * Uses the Tsinghua PyPI mirror (domestic).
#   * Deliberately does NOT use --collect-all PySide6: that would bundle
#     QtWebEngine (~130 MB) and Qt3D, which this app does not use.
param(
    [ValidateSet("onefile", "onedir")]
    [string]$Mode = "onefile",
    [switch]$Console
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

$py = "C:/Users/Administrator/AppData/Local/Python/bin/python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$mirror = "https://pypi.tuna.tsinghua.edu.cn/simple"

Write-Host "==> Ensuring PyInstaller is installed (mirror: $mirror)"
& $py -m pip install --quiet --upgrade -i $mirror pyinstaller

$outDir = if ($Mode -eq "onefile") { "dist-onefile" } else { "dist-onedir" }

$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm", "--clean",
    "--name", "TES-Safety-Calculator",
    "--distpath", $outDir,
    "--exclude-module", "PySide6.QtWebEngineCore",
    "--exclude-module", "PySide6.QtWebEngineWidgets",
    "--exclude-module", "PySide6.QtWebEngineQuick",
    "--exclude-module", "PySide6.QtQuick",
    "--exclude-module", "PySide6.QtQml",
    "--exclude-module", "PySide6.Qt3DCore",
    "--exclude-module", "PySide6.QtMultimedia",
    "--exclude-module", "PySide6.QtCharts",
    "--exclude-module", "PySide6.QtDataVisualization",
    "--exclude-module", "streamlit",
    "--exclude-module", "pandas",
    "--exclude-module", "numpy",
    "--exclude-module", "reportlab",
    "--exclude-module", "matplotlib",
    "--exclude-module", "scipy",
    "--exclude-module", "tkinter",
    "--windowed",
    "tes_qt_app.py"
)

if ($Console) {
    $arguments = @($arguments | Where-Object { $_ -ne "--windowed" })
}

if ($Mode -eq "onefile") { $arguments += "--onefile" }

Write-Host "==> Building ($Mode, console=$Console)"
& $py @arguments
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed (exit $LASTEXITCODE)" }

$exe = if ($Mode -eq "onefile") {
    Join-Path $outDir "TES-Safety-Calculator.exe"
} else {
    Join-Path $outDir "TES-Safety-Calculator\TES-Safety-Calculator.exe"
}
Write-Host "==> Output: $exe"
if (Test-Path $exe) { Write-Host ("    Size: {0:N1} MB" -f ((Get-Item $exe).Length / 1MB)) }
