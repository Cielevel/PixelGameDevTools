#!/usr/bin/env python3
"""前端口径对拍：两个单文件 HTML 的 JS 实现 ↔ pixel-toolkit 的 Python 实现。

**为什么存在**：`video-studio.html` / `asset-inspector.html` 为保「双击即用」各自内联实现算法
（OKLab、网格检测、降采样、色度抠像、稳定性判据…），口径只能靠人工同步。本脚本把「同步」变成可执行检查：
改任一侧后跑一遍，不一致就红。

对拍项（JS 函数真身从 HTML 里抽取后 eval，测的就是页面里跑的那份代码）：
  1) 稳定性判据   video-studio.html `computeStability`   ↔ `stability.analyze_rgba`
  2) 时间维滤波   video-studio.html `temporalMedianFrames` ↔ `standardize.temporal_median_frames`（逐字节）
  3) 结构检查     asset-inspector.html `structureOf/bboxOf` ↔ `check.analyze`（bbox/连通域/孤立像素）
  4) 归板         asset-inspector.html `mapToPaletteImageData` ↔ `palette.quantize`（先 alpha 两态化）
  5) sheet 元数据 video-studio.html `sheetMeta`          ↔ `atlas.build_meta`
  6) sheet 元数据 asset-inspector.html `sheetMetaAI`      ↔ `atlas.build_meta`（duration/sourceRoute）
  7) 缩格         asset-inspector.html `downscaleImageData` ↔ `standardize.sample_cells`（含 alpha）
  8) 时间众数稳定 video-studio.html `temporalStabilize`   ↔ `standardize.temporal_mode_frames`（逐字节）

需 Node（可选开发依赖，不进 pixcli 部署）。全部通过 exit 0；无 node 则打印 SKIP 并 exit 0。
"""
from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # pixel-toolkit/
REPO = os.path.dirname(ROOT)
sys.path.insert(0, ROOT)

import atlas as atlasmod
import check as checkmod
import palette as palmod
import stability as stabmod
import standardize as stdmod
from PIL import Image


# ------------------------------------------------------------ 合成数据 ----
def make_stab_frames(w=12, h=10, n=7):
    """确定性帧序列：中部 6×6 纯静态块 + 变色/透明/闪烁格（覆盖静态格与核心静态格判定）。"""
    rnd = random.Random(12345)
    frames = [[(0, 0, 0, 0)] * (w * h) for _ in range(n)]
    for c in range(w * h):
        cx, cy = c % w, c // w
        core = 3 <= cx <= 8 and 2 <= cy <= 7
        kind = 1 if core else c % 5
        for i in range(n):
            r, g, b, a = 100, 100, 100, 255
            if kind == 0:
                r, g, b = 10 + i, 20, 30
            elif kind == 2:
                a = 0 if i % 2 else 255
            elif kind == 3:
                r, g, b = (i * 37) % 256, (i * 11) % 256, (i * 5) % 256
            elif kind == 4:
                a = 0
            if kind in (0, 3) and rnd.random() < 0.15:
                a = 0
            frames[i][c] = (r, g, b, a)
    return [b"".join(bytes(p) for p in f) for f in frames], w, h


def make_struct_images():
    """三张结构用例图：单连通块 / 三岛 / 块+孤立像素。"""
    rnd = random.Random(7)
    out = {}

    def blank():
        return Image.new("RGBA", (32, 24), (0, 0, 0, 0))

    def rnd_px():
        return (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), 255)

    im = blank()
    for y in range(2, 22):
        for x in range(2, 30):
            im.putpixel((x, y), rnd_px())
    out["block"] = im

    im = blank()
    for ox in (1, 12, 24):
        for y in range(3, 8):
            for x in range(ox, ox + 4):
                im.putpixel((x, y), rnd_px())
    out["islands"] = im

    im = blank()
    for y in range(3, 9):
        for x in range(3, 9):
            im.putpixel((x, y), rnd_px())
    im.putpixel((20, 5), rnd_px())          # 孤立像素
    out["stray"] = im

    im = blank()                            # 缩格对拍用：含透明区 + 噪色（16×16）
    for y in range(16):
        for x in range(16):
            if 4 <= x <= 11 and 4 <= y <= 11:
                continue                    # 中心 8×8 透明
            im.putpixel((x, y), rnd_px())
    out["grid"] = im
    return out


def deep_equal(a, b):
    """结构相等（数值按 1e-9 容差比较；JSON 里 16 与 16.0 视为相同）。"""
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(deep_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(deep_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-9
    return a == b


def main():
    node = shutil.which("node")
    if not node:
        print("[parity] SKIP：未找到 node（前端口径对拍需要 Node，可选开发依赖）")
        return 0
    work = tempfile.mkdtemp(prefix="pixcli-parity-")
    frames, w, h = make_stab_frames()
    n = len(frames)
    structs = make_struct_images()

    pal_colors = ["#%02x%02x%02x" % structs["block"].getpixel((2, 2))[:3],
                  "#%02x%02x%02x" % structs["block"].getpixel((10, 10))[:3],
                  "#000000", "#ffffff", "#e5484d", "#0a7d3c", "#123456"]

    with open(os.path.join(work, "stab_frames.bin"), "wb") as f:
        f.write(b"".join(frames))
    struct_meta = []
    for name, im in structs.items():
        im.save(os.path.join(work, "struct_%s.png" % name))
        with open(os.path.join(work, "struct_%s.raw" % name), "wb") as f:
            f.write(im.convert("RGBA").tobytes())
        struct_meta.append({"name": name, "w": im.size[0], "h": im.size[1]})
    with open(os.path.join(work, "input.json"), "w") as f:
        json.dump({"stab": {"w": w, "h": h, "n": n}, "temporalW": 5,
                   "palette": {"name": "parity-pal", "colors": pal_colors},
                   "struct": struct_meta}, f)

    r = subprocess.run([node, os.path.join(HERE, "parity_frontend.js"), REPO, work],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("[parity] JS 侧执行失败：\n" + (r.stderr or r.stdout).strip()[-2000:])
        return 1
    js = json.load(open(os.path.join(work, "js_out.json")))

    fails = []

    def check(name, ok, detail=""):
        print("  {} {}{}".format("PASS" if ok else "FAIL", name, ("  " + detail) if detail else ""))
        if not ok:
            fails.append(name)

    # 1) 稳定性判据
    py = stabmod.analyze_rgba(frames, w, h)
    keys = ["frames", "cells", "pairs", "staticCells", "coreCells", "flipAll", "flipCore", "avgColors"]
    bad = [k for k in keys if abs(float(py[k]) - float(js["stability"][k])) > 0]
    check("稳定性判据 computeStability ↔ analyze_rgba", not bad, str(bad) if bad else
          "flipCore {:.2f}% avgColors {:.2f}".format(py["flipCore"], py["avgColors"]))

    # 2) 时间维滤波（逐字节）
    imgs = [Image.frombytes("RGBA", (w, h), f) for f in frames]
    py_out = b"".join(o.tobytes() for o in stdmod.temporal_median_frames(imgs, 5))
    js_out = open(os.path.join(work, "temporal_js.bin"), "rb").read()
    check("时间维滤波 temporalMedianFrames ↔ temporal_median_frames", py_out == js_out,
          "" if py_out == js_out else "字节不一致（py {} vs js {}）".format(len(py_out), len(js_out)))

    # 3) 结构检查（vs check.analyze）
    struct_ok = True
    detail = []
    for item in struct_meta:
        nm = item["name"]
        info, issues = checkmod.analyze(os.path.join(work, "struct_%s.png" % nm))
        strays = []
        for _sev, msg in issues:
            if "孤立像素" in msg:
                import re
                m = re.search(r"\[.*\]", msg)
                strays = [list(t) for t in eval(m.group(0))] if m else []
        j = js["struct"][nm]
        same = (list(info["bbox"]) if info["bbox"] else None) == j["bbox"] \
            and info["components"] == j["compSizes"] \
            and strays == [list(s) for s in j["strays"]]
        struct_ok = struct_ok and same
        if not same:
            detail.append(nm)
    check("结构检查 structureOf ↔ check.analyze", struct_ok, ",".join(detail))

    # 4) 归板（先 alpha 两态化，对齐 inspector 链路）
    pal = palmod.Palette(name="parity-pal", colors=[palmod.hex_to_rgb(c) for c in pal_colors])
    pal_ok = True
    detail = []
    for item in struct_meta:
        nm = item["name"]
        img = Image.open(os.path.join(work, "struct_%s.png" % nm)).convert("RGBA")
        py_map = palmod.quantize(palmod.enforce_alpha(img, 128), pal).tobytes()
        js_map = open(os.path.join(work, "pal_%s_js.bin" % nm), "rb").read()
        if py_map != js_map:
            pal_ok = False
            detail.append(nm)
    check("归板 mapToPaletteImageData ↔ palette.quantize", pal_ok, ",".join(detail))

    # 5) sheet 元数据（vs atlas.build_meta）：video-studio 与 asset-inspector 各一份
    sheet_imgs = [structs[i["name"]].convert("RGBA") for i in struct_meta]
    py_meta, py_cols, py_rows = atlasmod.build_meta(sheet_imgs, "track1_sheet.png", fps=12,
                                                    tag="track1", source_route="sampled")
    jm = js["sheetMeta"]
    same = (py_cols == len(sheet_imgs) and py_rows == 1 and deep_equal(py_meta, jm))
    check("sheet 元数据 video-studio sheetMeta ↔ atlas.build_meta", same,
          "" if same else "meta 不一致（帧数 {} vs {}）".format(len(py_meta["frames"]), len(jm["frames"])))

    py_meta2, _c2, _r2 = atlasmod.build_meta(sheet_imgs, "ai_sheet.png", fps=10,
                                             tag="anim", source_route="authored")
    jm2 = js["sheetMetaAI"]
    same2 = deep_equal(py_meta2, jm2)
    check("sheet 元数据 asset-inspector sheetMeta ↔ atlas.build_meta", same2,
          "" if same2 else "meta 不一致（duration/sourceRoute 检查）")

    # 6) 缩格（含 alpha 语义）↔ standardize.sample_cells
    gimg = structs["grid"].convert("RGBA")
    py_ds = stdmod.sample_cells(gimg, 4, 4, method="mode", bg=None, ox=0, oy=0)
    js_ds = open(os.path.join(work, "down_js.bin"), "rb").read()
    ds_ok = py_ds.tobytes() == js_ds and js["downscale"]["w"] == py_ds.size[0] \
        and js["downscale"]["h"] == py_ds.size[1]
    check("缩格（含 alpha）downscaleImageData ↔ standardize.sample_cells", ds_ok,
          "" if ds_ok else "尺寸 {}×{} vs {}×{}".format(js["downscale"]["w"], js["downscale"]["h"],
                                                        *py_ds.size))

    # 7) 时间众数稳定（量化后）↔ standardize.temporal_mode_frames
    py_stab = b"".join(o.tobytes() for o in stdmod.temporal_mode_frames(imgs, 3))
    js_stab = open(os.path.join(work, "stabmode_js.bin"), "rb").read()
    check("时间众数稳定 temporalStabilize ↔ temporal_mode_frames", py_stab == js_stab,
          "" if py_stab == js_stab else "字节不一致（py {} vs js {}）".format(len(py_stab), len(js_stab)))

    shutil.rmtree(work, ignore_errors=True)
    total = 8
    if fails:
        print("[parity] {}/{} 项不一致：{}".format(len(fails), total, "、".join(fails)))
        return 1
    print("[parity] 全部一致（{}/{}）".format(total, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
