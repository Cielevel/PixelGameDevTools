#!/usr/bin/env python3
"""史莱姆（软体圆物）idle 待机 10 帧生成脚本 —— 生成脚本骨架范例（风格基准资产）。

演示要点：颜色先入调色板再使用、一源双产出（正式档 <类别>_slime_idle 经 layout.py
前缀映射落 mob/，基准存档 slime_idle 落 base/，两份像素完全相同）、脚本可复现
（重跑 = 资产，配合 pixcli diff 做零差异验证）。输出路径按目标工程调整。

规范：32x32、RGBA、alpha 两态、光源左上、1px 闭合内描边。
明暗/造型模型复用 tools/pixelart/style_kit.py（风格基准库）。
动画：squash & stretch 呼吸/弹性循环（压扁蓄力 → 回弹拉伸 → 顶点 → 回落 →
二次小压扁 → 回中），底边始终贴地（bbox bottom 恒为 y=31）、水平中心恒为 x=15.5，
体积守恒（压扁变宽、拉伸变窄）。首尾帧相同保证无缝循环。

可复现：python3 pixel-toolkit/examples/gen_slime_idle.py
（调色板若缺失则先落盘 assets/palettes/slime.json）
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import style_kit
from anim import build_sheet
from canvas import Canvas
from layout import sprite_dir
from palette import Palette

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAL_PATH = os.path.join(ROOT, "assets", "palettes", "slime.json")
OUT_DIR = os.path.join(ROOT, "assets", "sprites")
SIZE = 32
GROUND_Y = 31          # 底边贴地行（锚点：脚底中心 = (15.5, 31)）
CX = 15.5              # 造型左右对称轴（画布正中，偶数宽造型）

# ---------------------------------------------------------------- 调色板 ----
# 蓝色系五阶：outline / shadow / mid / light / highlight + glint + eye + mouth
PALETTE = {
    "name": "slime",
    "colors": [
        "#0b1a36",  # eye        眼睛（近黑深蓝，与描边区分）
        "#182b54",  # outline    1px 闭合外描边
        "#2a6ca8",  # shadow     暗部（右下 + 贴地接触）
        "#4aa3e0",  # mid        中间调（体色）
        "#85c9f2",  # light      亮部（左上受光带）
        "#d9f3ff",  # highlight  高光（左上高光团）
        "#ffffff",  # glint      眼神光点 / 体表亮芯
        "#6f2d52",  # mouth      张嘴内部（深莓色，仅 o 嘴用）
    ],
    "roles": {
        "outline": "#182b54",
        "shadow": "#2a6ca8",
        "mid": "#4aa3e0",
        "light": "#85c9f2",
        "highlight": "#d9f3ff",
        "glint": "#ffffff",
        "eye": "#0b1a36",
        "mouth": "#6f2d52",
    },
}

# ------------------------------------------------------------ 帧形变参数 ----
# (W, H, w_start, n_d,            剪影：宽 / 高 / 穹顶起始行宽 / 穹通行数
#  ew, eh, edy,                   眼睛：宽(2/3) 高(1=闭眼,2,3,4) 垂直偏移
#  mouth, mdy,                    嘴型：smile4/flat4/flat6/o2 与垂直偏移
#  label)
FRAMES = [
    # f0 待机中位（循环首帧 = 末帧）
    (22, 14, 4, 8,  2, 3, 0, "smile4", 0, "中位：自然呼吸，微笑"),
    # f1 蓄力开始，轻微下沉压扁
    (24, 13, 6, 7,  2, 3, 0, "smile4", 0, "蓄力：轻微压扁"),
    # f2 最大压扁（蓄力顶点）：变宽变矮，眯眼、嘴压平
    (26, 12, 8, 6,  3, 2, 1, "flat6", 0, "蓄力顶点：最大压扁，眯眼"),
    # f3 回弹拉伸：变窄变高，睁大眼、张小嘴
    (20, 16, 4, 8,  2, 4, -1, "o2", 0, "回弹：向上拉伸，睁眼张嘴"),
    # f4 拉伸顶点：最窄最高
    (18, 17, 4, 7,  2, 4, -1, "o2", 0, "顶点：最大拉伸"),
    # f5 回落：逐渐放松
    (20, 15, 4, 8,  2, 3, 0, "smile4", 0, "回落：放松复原"),
    # f6 二次触地压扁（follow-through）：闭眼压平
    (26, 12, 8, 6,  3, 1, 1, "flat6", 0, "触地：二次压扁，闭眼"),
    # f7 小回弹：眼睛重新睁开
    (20, 15, 4, 8,  2, 3, 0, "smile4", 0, "小回弹：睁眼"),
    # f8 余波微压（阻尼收尾）
    (24, 13, 6, 7,  2, 3, 0, "flat4", 0, "余波：微压收平嘴"),
    # f9 回到中位 = f0，无缝循环
    (22, 14, 4, 8,  2, 3, 0, "smile4", 0, "回中：= f0"),
]

# ---------------------------------------------------------------- 绘制 ----
def render_frame(pose, pal):
    W, H, w_start, n_d, ew, eh, edy, mouth, mdy, label = pose
    c = Canvas(SIZE, SIZE)
    rows, y_top = style_kit.body_rows(CX, W, H, w_start, n_d, GROUND_Y)
    rx = W / 2.0

    # 1+2) 体色填充 + 轮廓偏移法明暗带（光源左上）+ 贴地接触阴影
    style_kit.shade_body(c, rows, y_top, CX, pal)

    # 3) 左上高光团（小而克制，与眼睛/描边保持间隔）+ 白色亮芯
    style_kit.highlight_blob(c, CX, y_top, rx, H, pal)

    # 4) 脸（眼睛 + 嘴）
    gap = W - 2 * ew - 2 * max(4, round(W * 0.23))
    gap = max(gap, 2)
    eye_top = y_top + round(H * 0.36) + edy
    left_r = 15 - gap // 2          # 左眼最右列
    right_l = 16 + gap // 2         # 右眼最左列
    for dx in range(ew):            # 左眼列 left_r-ew+1 .. left_r；右眼镜像
        for k in (left_r - dx, right_l + dx):
            for e in range(eh):
                c.px(k, eye_top + e, pal["eye"])
    # 眼神光点：每只眼左上角 1px（与左上光源同侧；闭眼帧也保留，防循环中白点闪没）
    style_kit.eye_glints(c, left_r, right_l, eye_top, ew, pal)

    my = y_top + round(H * 0.63) + mdy
    if mouth == "smile4":
        c.px(14, my, pal["eye"]); c.px(17, my, pal["eye"])
        c.px(15, my + 1, pal["eye"]); c.px(16, my + 1, pal["eye"])
    elif mouth == "flat4":
        c.hline(14, 17, my, pal["eye"])
    elif mouth == "flat6":
        c.hline(13, 18, my, pal["eye"])
    elif mouth == "o2":
        c.rect(15, my, 2, 2, pal["mouth"])

    # 5) 1px 闭合内描边（最后画，覆盖轮廓上的所有色）
    c.outline_in(pal["outline"])
    return c, label


def main():
    os.makedirs(os.path.dirname(PAL_PATH), exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.exists(PAL_PATH):      # 颜色先入板
        Palette(PALETTE["name"],
                [tuple(int(s[i:i + 2], 16) for i in (1, 3, 5)) for s in PALETTE["colors"]],
                {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in PALETTE["roles"].items()}
                ).save(PAL_PATH)
        print("调色板 →", PAL_PATH)
    pal = Palette.load(PAL_PATH).roles

    images = []
    for i, pose in enumerate(FRAMES):
        c, label = render_frame(pose, pal)
        images.append(c.to_image())
        # 一源双产出：mob/ 正式资产（清单 §3）+ base/ 风格基准存档（同像素）
        for name in ("mob_slime_idle", "slime_idle"):
            path = os.path.join(sprite_dir(OUT_DIR, name), "{}_{:02d}.png".format(name, i))
            c.save(path)
        print("f{:02d} {:<24} W={} H={} rows={}".format(
            i, label, pose[0], pose[1], 32 - pose[1]))
    sheet = build_sheet(images, horizontal=True)
    for name in ("mob_slime_idle", "slime_idle"):
        sheet_path = os.path.join(sprite_dir(OUT_DIR, name), "{}_sheet.png".format(name))
        sheet.save(sheet_path)
    print("sheet → {} + base/slime_idle_sheet.png（{} 帧，{}x{}）".format(
        os.path.join(sprite_dir(OUT_DIR, "mob_slime_idle"), "mob_slime_idle_sheet.png"),
        len(images), *images[0].size))


if __name__ == "__main__":
    main()
