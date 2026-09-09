#!/usr/bin/env python3
"""bench 封装：本工程 standardize 作为对照实验参赛者。

路径口径：原为硬编码绝对路径（旧仓位置 `ProjectZCode/…`，已失效）；
2026-09-08 整理时改为相对本文件定位本仓 `pixel-toolkit/`。
"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "pixel-toolkit")))

import standardize as std
from PIL import Image


def run(in_path):
    """对标 SpriteGrid 默认：自动网格 + 众数采样，不量化。"""
    out, _ = std.standardize(Image.open(in_path), colors=0)
    return out


def run_c16(in_path):
    """默认链路：自动网格 + 众数采样 + OKLab 量化到 16 色。"""
    out, _ = std.standardize(Image.open(in_path), colors=16)
    return out
