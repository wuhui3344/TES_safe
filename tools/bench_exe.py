"""测量打包后 exe 的启动耗时（用 --selftest 作为“完整启动 + 计算 + 导出”的代理指标）。

用法:
    python tools/bench_exe.py                     # 自动找 dist-onefile / dist-onedir
    python tools/bench_exe.py <exe路径> [次数]
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CANDIDATES = [
    ("单文件 --onefile", os.path.join(ROOT, "dist-onefile", "TES-Safety-Calculator.exe")),
    ("目录版 --onedir", os.path.join(ROOT, "dist-onedir", "TES-Safety-Calculator", "TES-Safety-Calculator.exe")),
]


def measure(exe: str, rounds: int = 3) -> None:
    if not os.path.exists(exe):
        print(f"  [跳过] 未找到：{exe}")
        return
    for index in range(1, rounds + 1):
        start = time.perf_counter()
        completed = subprocess.run([exe, "--selftest"], capture_output=True, timeout=300)
        elapsed = time.perf_counter() - start
        print(f"  第{index}次: {elapsed:6.2f} s  exit={completed.returncode}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        targets = [("指定", sys.argv[1])]
        rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    else:
        targets = CANDIDATES
        rounds = 3

    for label, exe in targets:
        print(f"[{label}] {exe}")
        measure(exe, rounds)
