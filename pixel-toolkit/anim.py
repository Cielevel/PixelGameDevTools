"""序列帧 I/O、sprite sheet 拼合/切分、GIF 与自包含 HTML 播放器、放大检查图。"""
from __future__ import annotations

import base64
import io
import json
import math
import os

from PIL import Image, ImageDraw


def expand_input(path):
    """目录 → 目录下按文件名排序的 PNG 列表（排除 `*_sheet.png`）；文件 → [文件]。"""
    if os.path.isdir(path):
        return [
            os.path.join(path, f)
            for f in sorted(os.listdir(path))
            if f.lower().endswith(".png") and not f.lower().endswith("_sheet.png")
        ]
    return [path]


def load_frames(paths):
    """按给定顺序加载 PNG（RGBA）。"""
    return [Image.open(p).convert("RGBA") for p in paths]


# ---------- sprite sheet ----------
def build_sheet(frames, horizontal=True):
    sizes = {f.size for f in frames}
    if len(sizes) != 1:
        raise ValueError(f"帧尺寸不一致: {sorted(sizes)}")
    w, h = frames[0].size
    n = len(frames)
    if horizontal:
        sheet = Image.new("RGBA", (w * n, h), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            sheet.paste(f, (i * w, 0))
    else:
        sheet = Image.new("RGBA", (w, h * n), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            sheet.paste(f, (0, i * h))
    return sheet


def slice_sheet(sheet, fw, fh, horizontal=True):
    sheet = sheet.convert("RGBA")
    w, h = sheet.size
    frames = []
    if horizontal:
        if w % fw or h != fh:
            raise ValueError(f"sheet {w}x{h} 不能按帧宽 {fw}x{fh} 切分")
        for i in range(w // fw):
            frames.append(sheet.crop((i * fw, 0, (i + 1) * fw, fh)))
    else:
        if h % fh or w != fw:
            raise ValueError(f"sheet {w}x{h} 不能按帧高 {fh} 切分")
        for i in range(h // fh):
            frames.append(sheet.crop((0, i * fh, fw, (i + 1) * fh)))
    return frames


# ---------- 缩放 ----------
def scale_nearest(img, factor):
    """nearest 整数倍放大（仅用于预览/检查，不用于正式资产）。"""
    if factor != int(factor) or factor < 1:
        raise ValueError("factor 必须为正整数")
    factor = int(factor)
    w, h = img.size
    return img.resize((w * factor, h * factor), Image.NEAREST)


# ---------- GIF ----------
def _to_p_frame(img, colors, transparent_index=255):
    lut = {c: i for i, c in enumerate(colors)}
    pal_flat = []
    for c in colors:
        pal_flat += list(c)
    while len(pal_flat) < 768:
        pal_flat.append(0)
    p = Image.new("P", img.size)
    p.putpalette(pal_flat)
    p.putdata([transparent_index if a == 0 else lut[(r, g, b)]
               for (r, g, b, a) in img.convert("RGBA").getdata()])
    return p


def export_gif(frames, path, fps=10, pingpong=False):
    """帧序列 → 循环 GIF（全局精确调色板，disposal=2 保持透明背景）。"""
    if not frames:
        raise ValueError("无帧可导出")
    seq = list(frames)
    if pingpong and len(seq) > 1:
        seq = seq + seq[-2:0:-1]
    colors = []
    for f in seq:
        for r, g, b, a in f.convert("RGBA").getdata():
            if a and (r, g, b) not in colors:
                colors.append((r, g, b))
    if len(colors) > 255:
        raise ValueError(f"GIF 全局调色板超限：{len(colors)} 色 > 255")
    ti = 255
    p_frames = [_to_p_frame(f, colors, ti) for f in seq]
    duration = max(20, int(round(1000 / fps)))
    p_frames[0].save(
        path, save_all=True, append_images=p_frames[1:],
        duration=duration, loop=0, disposal=2, transparency=ti, optimize=False,
    )


# ---------- HTML 播放器 ----------
_HTML_TEMPLATE = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; padding: 24px; background: #14161a; color: #d8dde6;
         font: 14px/1.6 -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
  h1 { font-size: 16px; margin: 0 0 16px; font-weight: 600; }
  .stage { display: inline-block; padding: 16px; background: #1b1e24; border-radius: 10px; }
  canvas { image-rendering: pixelated; display: block; }
  canvas.checker { background: repeating-conic-gradient(#34383f 0 25%, #282b31 0 50%) 0 0 / 16px 16px; }
  .bar { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-top: 14px; }
  .bar label { display: flex; gap: 6px; align-items: center; }
  input[type=range] { width: 140px; }
  select, button { background: #262b33; color: inherit; border: 1px solid #3a4048;
                   border-radius: 6px; padding: 3px 10px; }
  button { cursor: pointer; min-width: 56px; }
  .frameinfo { color: #8b93a1; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>
<h1>__TITLE__</h1>
<div class="stage"><canvas id="cv" class="checker"></canvas></div>
<div class="bar">
  <button id="play">暂停</button>
  <label>FPS <input id="fps" type="range" min="1" max="24" value="__FPS__"><span id="fpsv">__FPS__</span></label>
  <label>缩放 <select id="zoom">__ZOOMS__</select></label>
  <label><input id="ping" type="checkbox">往复</label>
  <label><input id="onion" type="checkbox">洋葱皮</label>
  <label><input id="ckb" type="checkbox" checked>棋盘格</label>
  <span class="frameinfo" id="fi"></span>
</div>
<div class="bar"><label>逐帧 <input id="seek" type="range" min="0" max="__MAXI__" value="0" style="width: 320px"></label></div>
<script>
"use strict";
const FRAMES = __FRAMES__;
const N = FRAMES.length, W = __W__, H = __H__;
const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
const seek = document.getElementById("seek"), playBtn = document.getElementById("play");
const imgs = [];
let loaded = 0, playing = true, fps = __FPS__, frame = 0, acc = 0, last = 0;
let pingpong = false, onion = false, zoom = __ZOOM__;

FRAMES.forEach((u) => {
  const im = new Image();
  im.onload = () => { if (++loaded === N) requestAnimationFrame(tick); };
  im.src = u;
  imgs.push(im);
});

function setZoom(z) {
  zoom = z;
  cv.width = W * z; cv.height = H * z;
  ctx.imageSmoothingEnabled = false;
}
function seqIndex() {
  if (!pingpong || N < 3) return frame % N;
  const m = 2 * N - 2, k = frame % m;
  return k < N ? k : m - k;
}
function draw() {
  const i = seqIndex();
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (onion) {
    ctx.globalAlpha = 0.35;
    ctx.drawImage(imgs[(i - 1 + N) % N], 0, 0, cv.width, cv.height);
    ctx.globalAlpha = 1;
  }
  ctx.drawImage(imgs[i], 0, 0, cv.width, cv.height);
  document.getElementById("fi").textContent = "帧 " + (i + 1) + " / " + N;
  if (playing) seek.value = i;
}
function tick(t) {
  if (!last) last = t;
  acc += t - last; last = t;
  if (playing) {
    const step = 1000 / fps;
    while (acc >= step) { acc -= step; frame++; }
  } else { acc = 0; }
  draw();
  requestAnimationFrame(tick);
}
playBtn.onclick = () => { playing = !playing; playBtn.textContent = playing ? "暂停" : "播放"; };
document.getElementById("fps").oninput = (e) => {
  fps = +e.target.value;
  document.getElementById("fpsv").textContent = fps;
};
document.getElementById("zoom").onchange = (e) => setZoom(+e.target.value);
document.getElementById("ping").onchange = (e) => { pingpong = e.target.checked; };
document.getElementById("onion").onchange = (e) => { onion = e.target.checked; };
document.getElementById("ckb").onchange = (e) => { cv.classList.toggle("checker", e.target.checked); };
seek.oninput = (e) => {
  playing = false; playBtn.textContent = "播放";
  frame = +e.target.value;
  draw();
};
setZoom(__ZOOM__);
</script>
</body>
</html>
"""


def _data_url(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def export_html(frames, path, title="Pixel Animation", fps=10, zoom=6):
    """自包含 HTML 播放器（帧以 base64 内嵌）：FPS/缩放/逐帧/往复/洋葱皮/棋盘格。"""
    if not frames:
        raise ValueError("无帧可导出")
    w, h = frames[0].size
    zooms = "".join(
        '<option value="{0}"{1}>{0}x</option>'.format(z, " selected" if z == zoom else "")
        for z in range(1, 9)
    )
    html = (_HTML_TEMPLATE
            .replace("__TITLE__", title)
            .replace("__MAXI__", str(len(frames) - 1))
            .replace("__W__", str(w))
            .replace("__H__", str(h))
            .replace("__FPS__", str(fps))
            .replace("__ZOOMS__", zooms)
            .replace("__ZOOM__", str(zoom))
            .replace("__FRAMES__", json.dumps([_data_url(f) for f in frames])))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ---------- 放大逐帧检查图 ----------
def _draw_checker(d, x, y, cw, ch, cell):
    for cy in range(0, ch, cell):
        for cx in range(0, cw, cell):
            col = (44, 48, 55, 255) if ((cx // cell + cy // cell) % 2 == 0) else (34, 37, 43, 255)
            d.rectangle([x + cx, y + cy, min(x + cx + cell - 1, x + cw - 1),
                         min(y + cy + cell - 1, y + ch - 1)], fill=col)


GRID_MINOR = (96, 102, 114, 70)
GRID_MAJOR = (168, 174, 186, 120)
GRID_LABEL = (196, 202, 212, 170)


def _draw_grid(d, x, y, w, h, scale):
    """放大格上叠像素网格：每源像素 1 条细线，每 8px 一条亮线；scale≥4 时标坐标刻度。"""
    for gx in range(w + 1):
        col = GRID_MAJOR if gx % 8 == 0 else GRID_MINOR
        d.line([(x + gx * scale, y), (x + gx * scale, y + h * scale)], fill=col)
    for gy in range(h + 1):
        col = GRID_MAJOR if gy % 8 == 0 else GRID_MINOR
        d.line([(x, y + gy * scale), (x + w * scale, y + gy * scale)], fill=col)
    if scale >= 4:
        for gx in range(0, w, 8):
            d.text((x + gx * scale + 2, y + 1), str(gx), fill=GRID_LABEL)
        for gy in range(0, h, 8):
            d.text((x + 2, y + gy * scale + 1), str(gy), fill=GRID_LABEL)


def contact_sheet(frames, path, scale=6, cols=None, pad=8, label_h=16, grid=False):
    """逐帧 nearest 放大排成网格（带棋盘格底与帧号），供目视检查；grid=True 叠像素网格与坐标刻度。"""
    if not frames:
        raise ValueError("无帧")
    w, h = frames[0].size
    for f in frames:
        if f.size != (w, h):
            raise ValueError(f"帧尺寸不一致: {f.size} != {(w, h)}")
    n = len(frames)
    cols = cols or min(n, 10)
    rows = math.ceil(n / cols)
    cw, ch = w * scale, h * scale
    W = cols * cw + pad * (cols + 1)
    H = rows * (ch + label_h + pad) + pad
    img = Image.new("RGBA", (W, H), (24, 26, 30, 255))
    d = ImageDraw.Draw(img)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0)) if grid else None
    od = ImageDraw.Draw(overlay) if grid else None
    cell = max(4, scale)
    for i, f in enumerate(frames):
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad)
        y = pad + r * (ch + label_h + pad)
        _draw_checker(d, x, y, cw, ch, cell)
        big = scale_nearest(f, scale)
        img.alpha_composite(big, (x, y))
        if grid:
            _draw_grid(od, x, y, w, h, scale)
        d.text((x + 2, y + ch + 2), "#{:02d}".format(i), fill=(200, 206, 216, 255))
    if grid:
        img = Image.alpha_composite(img, overlay)
    img.save(path)


# ---------- 洋葱皮静态检查图 ----------
ONION_PREV = (255, 82, 82)    # 上一帧幽灵：红
ONION_NEXT = (86, 156, 255)   # 下一帧幽灵：蓝


def _ghost(frame, color, alpha):
    """帧的不透明区域 → 单色半透明幽灵图（仅预览用，不受资产 alpha 两态约束）。"""
    g = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    gp, fp = g.load(), frame.load()
    w, h = frame.size
    for y in range(h):
        for x in range(w):
            if fp[x, y][3]:
                gp[x, y] = (color[0], color[1], color[2], alpha)
    return g


def onion_sheet(frames, path, scale=6, cols=None, pad=8, label_h=16,
                prev_alpha=115, next_alpha=95):
    """洋葱皮静态检查图：每格 = 上一帧（红幽灵）+ 下一帧（蓝幽灵）+ 当前帧。

    首尾回绕（第 0 帧的上一帧取最后一帧），用于查运动弧线、循环衔接与锚点抖动；
    是 aseprite-mcp「onion-skin」的静态图等价物，供审查 Read。
    """
    if not frames:
        raise ValueError("无帧可导出")
    w, h = frames[0].size
    for f in frames:
        if f.size != (w, h):
            raise ValueError(f"帧尺寸不一致: {f.size} != {(w, h)}")
    n = len(frames)
    cols = cols or min(n, 10)
    rows = math.ceil(n / cols)
    cw, ch = w * scale, h * scale
    top = 18 if n > 1 else 0
    W = cols * cw + pad * (cols + 1)
    H = rows * (ch + label_h + pad) + pad + top
    img = Image.new("RGBA", (W, H), (24, 26, 30, 255))
    d = ImageDraw.Draw(img)
    if n > 1:
        d.text((pad, 4), "ONION  red=prev  blue=next  full=cur  (loop wrap)",
               fill=(150, 156, 166, 255))
    ghosts = {i: {"prev": _ghost(f, ONION_PREV, prev_alpha),
                  "next": _ghost(f, ONION_NEXT, next_alpha)}
              for i, f in enumerate(frames)}
    cell = max(4, scale)
    for i, f in enumerate(frames):
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad)
        y = top + pad + r * (ch + label_h + pad)
        _draw_checker(d, x, y, cw, ch, cell)
        g = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        if n > 1:
            g.alpha_composite(scale_nearest(ghosts[(i - 1) % n]["prev"], scale))
            g.alpha_composite(scale_nearest(ghosts[(i + 1) % n]["next"], scale))
        g.alpha_composite(scale_nearest(f, scale))
        img.alpha_composite(g, (x, y))
        d.text((x + 2, y + ch + 2), "#{:02d}".format(i), fill=(200, 206, 216, 255))
    img.save(path)
