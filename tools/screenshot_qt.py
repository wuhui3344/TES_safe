"""把 Qt 主窗口渲染为 PNG，用于无显示器环境下检查界面外观。

用法: python tools/screenshot_qt.py [输出路径]
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication  # noqa: E402

import tes_qt_app  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "shot.png")

app = QApplication(sys.argv[:1])
window = tes_qt_app.MainWindow()
window.resize(1480, 940)
window.show()
app.processEvents()
window._recompute()
app.processEvents()

ok = window.grab().save(out)
print(f"saved={ok} path={out}")
