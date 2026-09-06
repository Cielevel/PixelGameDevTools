#!/usr/bin/env python3
"""制作标准化对照实验的测试样本。

> **失效声明（2026-09-06）**：本脚本依赖的 `gen_slime_idle.py`（史莱姆 demo 遗留生成脚本）
> 已从仓库删除；脚本不再可运行，仅保留作为交接包 bench 实验的**历史存档**（实验方法可参考，
> 真值生成需另备源）。真值：复用仓库自带真实像素资产（32x32 干净 RGBA 帧、≤16 色）即可。
> 模拟 Google Flow 输出：NEAREST 放大 32 倍 → 1024x1024 → 白底合成 → JPEG（有损）。

样本：
  sampleA_f0.jpg        单帧，NEAREST 放大 + JPEG q85（纯 JPEG 噪声，良性）
  sampleB_f2_hard.jpg   单帧，NEAREST 放大 + 轻微高斯模糊(0.6) + JPEG q85（模拟 AA/mixels，困难）
  anim/f{0,2,3,6}.jpg   动画 4 帧，各 NEAREST 放大 + JPEG q85（跨帧共享网格/色板测试）
  gt/f*.png             32x32 干净真值（对齐/命中率基准）
"""
import os
import sys

REPO = "/Users/cielevel/ProjectAI/ProjectZCode/PixelGameDevTools"
sys.path.insert(0, os.path.join(REPO, "pixel-toolkit"))
sys.path.insert(0, os.path.join(REPO, "pixel-toolkit", "generation"))

import gen_slime_idle as gen
from PIL import Image, ImageFilter

LAB = "/tmp/pas-lab"
S = os.path.join(LAB, "samples")
GT = os.path.join(S, "gt")
ANIM = os.path.join(S, "anim")
UP = 32          # 32x32 -> 1024x1024
Q = 85           # JPEG 质量（Flow ~2MB/2K 的量级）
SCALE = 6        # 报告中放大倍数

os.makedirs(GT, exist_ok=True)
os.makedirs(ANIM, exist_ok=True)

pal = gen.Palette(gen.PALETTE["name"],
                  [tuple(int(s[i:i + 2], 16) for i in (1, 3, 5)) for s in gen.PALETTE["colors"]],
                  {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in gen.PALETTE["roles"].items()})
roles = pal.roles

def gt_frame(idx):
    c, _ = gen.render_frame(gen.FRAMES[idx], roles)
    return c.to_image()          # 32x32 RGBA 干净帧

def to_jpeg(img32, path, blur=0.0):
    big = img32.resize((img32.width * UP, img32.height * UP), Image.NEAREST)
    bg = Image.new("RGBA", big.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(bg, big).convert("RGB")
    if blur:
        flat = flat.filter(ImageFilter.GaussianBlur(blur))
    flat.save(path, "JPEG", quality=Q)
    return flat

frames = {}
for i in (0, 2, 3, 6):
    im = gt_frame(i)
    im.save(os.path.join(GT, "f{}.png".format(i)))
    frames[i] = im
    print("gt f{}: {} 唯一色".format(i, len(im.convert("RGBA").getcolors(maxcolors=1 << 24))))

to_jpeg(frames[0], os.path.join(S, "sampleA_f0.jpg"))
to_jpeg(frames[2], os.path.join(S, "sampleB_f2_hard.jpg"), blur=0.6)
for i in (0, 2, 3, 6):
    to_jpeg(frames[i], os.path.join(ANIM, "f{}.jpg".format(i)))

print("样本完成 →", S)
