#!/usr/bin/env python3
"""像素动画时间稳定性判据（口径 = knowledge/像素视频-工具改进方案.md §1）。

指标定义
--------
- **静态格**：片段全程 `alpha > 0` 的格（各帧不透明格的交集）。
- **核心静态格**：静态格中 8 邻域也属于静态格的子集（排除轮廓边缘与描边抖动；
  越界邻域不算静态格，故 1px 画布边框不参与核心统计）。
- **帧间变色率**：相邻帧对中颜色发生变化的格数 /（格数 × 相邻帧对数）；
  分别对静态格（`flipAll`）、核心静态格（`flipCore`）统计，单位 **%**。
- **单格平均色数**：每个静态格在片段中出现过的不同颜色数，取平均（`avgColors`）。

为什么只统计静止格：运动本身必然改变颜色，把闪烁从运动里分离出来才能定位「闪」。
`pixcli anim` 的「相邻 diff 率」是全局像素差，跑步时天然很高，被运动淹没，**不能用来定位闪烁**；
本指标可以。全屏运动片段（静态格 < `STATIC_MIN`）报「样本不足」，不判通过。

同一口径的浏览器侧实现是 `video-studio.html` 的 `computeStability()`——两处数值必须一致
（验收见方案 §5.2），改这里务必同步改那里。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

STATIC_MIN = 50        # 静态格少于此数 → 样本不足（不判通过）
MAX_FLIP_CORE = 5.0    # 核心静态格变色率门禁（%），暂定值
MAX_AVG_COLORS = 3.0   # 单格平均色数门禁，暂定值
ALPHA_MIN = 128        # 不透明判定（与 alpha 两态化同口径）

# 阈值档位（2026-09-08 加入）：同一读数按用途取不同尺子。
#   strict   = 方案 §1 的暂定门禁（手绘级目标；采样路线通常过不了）
#   standard = 方案 §5 的验收档（AI 视频样片 w=5 实测 10.4% / 13.7%，刚好卡在门口）
#   quick    = 回归探测档（只拦明显退化，不判「好不好」；2026-09-08 由 15% 提到 30%：
#              低拖影配置（时间众数稳定）的读数天然在 25% 上下——该读数奖励时间冻结，必须与拖影一起看）
PRESETS = {
    "strict": (5.0, 3.0),
    "standard": (10.0, 3.5),
    "quick": (30.0, 4.0),
}


def preset(name):
    """档位名 → (max_flip, max_colors)；未知档位抛 KeyError。"""
    return PRESETS[name]


def analyze_rgba(frames, width, height, alpha_min=ALPHA_MIN):
    """帧序列（每帧 RGBA 字节串，长度 = width*height*4）→ §1 指标 dict。

    返回：frames / cells / pairs / staticCells / coreCells / flipAll / flipCore / avgColors。
    帧为空返回 None。各帧尺寸由调用方保证一致（本函数只看字节长度隐含的 width×height）。
    """
    n = len(frames)
    if n == 0:
        return None
    cells = width * height
    opaque = bytearray(b"\x01") * cells        # 静态格标记：1=全程不透明
    colors = [set() for _ in range(cells)]     # 每格的色集合（仅静态格有意义）
    for f in frames:
        for c in range(cells):
            o = c * 4
            if f[o + 3] < alpha_min:
                opaque[c] = 0
            elif opaque[c]:
                colors[c].add((f[o], f[o + 1], f[o + 2]))
    # 核心静态格：8 邻域全部静态
    core = bytearray(cells)
    for y in range(height):
        for x in range(width):
            c = y * width + x
            if not opaque[c]:
                continue
            ok = True
            for dy in (-1, 0, 1):
                ny = y + dy
                if ny < 0 or ny >= height:
                    ok = False
                    break
                for dx in (-1, 0, 1):
                    nx = x + dx
                    if nx < 0 or nx >= width or not opaque[ny * width + nx]:
                        ok = False
                        break
                if not ok:
                    break
            core[c] = 1 if ok else 0
    static_n = sum(opaque)
    core_n = sum(core)
    pairs = max(0, n - 1)
    flip_all = flip_core = 0
    for i in range(pairs):
        a, b = frames[i], frames[i + 1]
        for c in range(cells):
            if not opaque[c]:
                continue
            o = c * 4
            if a[o] != b[o] or a[o + 1] != b[o + 1] or a[o + 2] != b[o + 2]:
                flip_all += 1
                if core[c]:
                    flip_core += 1

    def pct(count, cells_n):
        return 100.0 * count / (pairs * cells_n) if pairs and cells_n else 0.0

    avg_colors = (sum(len(colors[c]) for c in range(cells) if opaque[c]) / static_n
                  if static_n else 0.0)
    return {"frames": n, "cells": cells, "pairs": pairs,
            "staticCells": static_n, "coreCells": core_n,
            "flipAll": pct(flip_all, static_n), "flipCore": pct(flip_core, core_n),
            "avgColors": avg_colors}


def analyze_paths(paths, alpha_min=ALPHA_MIN):
    """PNG 文件/目录路径列表 → §1 指标 dict（尺寸不一致抛 ValueError）。"""
    imgs = [Image.open(p).convert("RGBA") for p in paths]
    if not imgs:
        return None
    w, h = imgs[0].size
    for p, im in zip(paths, imgs):
        if im.size != (w, h):
            raise ValueError("帧尺寸不一致：{} 为 {}x{}，首帧为 {}x{}".format(
                os.path.basename(p), im.size[0], im.size[1], w, h))
    return analyze_rgba([im.tobytes() for im in imgs], w, h, alpha_min=alpha_min)


def verdict(stats, max_flip=MAX_FLIP_CORE, max_colors=MAX_AVG_COLORS,
            min_static=STATIC_MIN):
    """门禁判定 → (ok, issues)。样本不足（静态格 < min_static）不判通过。"""
    if not stats:
        return False, ["无帧可判"]
    issues = []
    if stats["staticCells"] < min_static:
        issues.append("样本不足：静态格 {} < {}（全屏运动片段不适用该指标）".format(
            stats["staticCells"], min_static))
        return False, issues
    if stats["flipCore"] > max_flip:
        issues.append("核心静态格变色率 {:.1f}% > {:.1f}%".format(stats["flipCore"], max_flip))
    if stats["avgColors"] > max_colors:
        issues.append("单格平均色数 {:.2f} > {:.2f}".format(stats["avgColors"], max_colors))
    return (not issues), issues


def format_stats(stats):
    """一行读数（与 video-studio 指示器同口径：核心变色率 + 单格平均色数）。"""
    if not stats:
        return "-"
    return "稳定 {:.1f}% | 色 {:.2f}（静态格 {}/核心 {}，{} 帧）".format(
        stats["flipCore"], stats["avgColors"], stats["staticCells"],
        stats["coreCells"], stats["frames"])
