"""pytest 公共设置：把 pixel-toolkit 目录加进 sys.path（import pipeline / pixcli 等）。

运行（仓库根）：python3 -m pytest pixel-toolkit/tests/ -q
依赖：Pillow（工具本体）；ffmpeg（仅视频 parity 用例，缺失自动跳过）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
