#!/usr/bin/env python3
"""视频标准化：AI 生成像素视频 → 标准像素动画帧序列。

背景（2026-09-06 实测 origin_video.mp4 定稿）：
- AI 生成的运动视频（如即梦 mp4，1280x720@24fps）是**平滑动画 + 深度压缩**，
  帧间无稳定逻辑网格（自动网格检测 conf 0.57~0.70 每帧乱跳）——**网格还原不适用**；
  正确管线是「抽帧 → 角色区裁剪 → 整数降采样 → 跨帧共享 OKLab 量化 → 描边归一」。
- 像素风角色视频本身已是像素块（块约 4.4px），缺的是稳定帧提取、尺寸归一、
  跨帧色板一致（防闪烁）与输出形态（帧序列/GIF/HTML 播放器）。

依赖：ffmpeg/ffprobe 在 PATH 中（视频解码与抽帧）。
"""
from __future__ import annotations

import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anim
import standardize as stdmod
from PIL import Image


# ------------------------------------------------------------ ffmpeg 封装 ----
def ffprobe_info(path):
    """ffprobe → (width, height, fps, duration_s, frames)。失败抛 RuntimeError。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration,codec_name",
             "-of", "default=noprint_wrappers=1", path],
            capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(
            "ffprobe 不可用（需要 ffmpeg 全家桶；macOS: brew install ffmpeg）: {}".format(e))
    info = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k.strip()] = v.strip()
    w = int(info.get("width", 0))
    h = int(info.get("height", 0))
    r = info.get("r_frame_rate", "0/1")
    num, _, den = r.partition("/")
    fps = float(num) / float(den) if den and float(den) else 0.0
    dur = float(info.get("duration", 0) or 0)
    frames = int(info.get("nb_frames", 0) or 0)
    codec = info.get("codec_name", "?")
    if not w or not h:
        raise RuntimeError("ffprobe 未解析出视频尺寸: {}".format(path))
    return {"width": w, "height": h, "fps": fps, "duration": dur,
            "frames": frames, "codec": codec}


def extract_frames(video, out_dir, fps=None, start=None, end=None):
    """视频 → PNG 帧序列（原生分辨率）。返回帧文件列表（按时间序）。

    fps=None 用视频原生帧率；fps=N 重采样（抽/并帧，如 24→12 减半）。
    """
    os.makedirs(out_dir, exist_ok=True)
    from subprocess import run
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video]
    if start is not None and end is not None:
        cmd += ["-ss", str(start), "-t", str(end - start)]
    elif start is not None:
        cmd += ["-ss", str(start)]
    if fps is not None:
        cmd += ["-r", str(fps)]
        # -r 已做帧率重采样（输出每帧间隔 1/fps），不叠加 -fps_mode（会冲突）
    else:
        cmd += ["-fps_mode", "vfr"]   # 原生帧率时按实际帧输出（ffmpeg 9 无 -vsync）
    # 输出为 f%04d.png（从 0001 起）
    pat = os.path.join(out_dir, "f%04d.png")
    cmd += [pat]
    r = run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg 抽帧失败: {}".format(r.stderr.strip()[-300:]))
    frames = sorted(f for f in os.listdir(out_dir) if f.endswith(".png"))
    if not frames:
        raise RuntimeError("ffmpeg 未抽出任何帧")
    return [os.path.join(out_dir, f) for f in frames]


# ------------------------------------------------------------ 内容分析 ----
def content_bbox(im, bg_tol=60, bg=None, step=2):
    """内容包围盒（与背景差异明显的像素）。

    bg 可指定 (r,g,b)；None 时取四角众数为背景。
    返回 (x0,y0,x1,y1) 或 None（无内容）。
    """
    im = im.convert("RGB")
    px = im.load()
    w, h = im.size
    if bg is None:
        corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
        bg = Counter(corners).most_common(1)[0][0]
    xs, ys = [], []
    for y in range(0, h, step):
        for x in range(0, w, step):
            c = px[x, y]
            if abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) > bg_tol:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def merged_content_bbox(frame_paths, bg_tol=60, step=2):
    """多帧内容 bbox 合并（全程运动范围）。取所有帧内容并集的包围盒。"""
    all_x0 = all_y0 = None
    all_x1 = all_y1 = -1
    for p in frame_paths:
        im = Image.open(p)
        b = content_bbox(im, bg_tol=bg_tol, step=step)
        if not b:
            continue
        x0, y0, x1, y1 = b
        all_x0 = x0 if all_x0 is None else min(all_x0, x0)
        all_y0 = y0 if all_y0 is None else min(all_y0, y0)
        all_x1 = max(all_x1, x1)
        all_y1 = max(all_y1, y1)
    if all_x0 is None:
        return None
    return (all_x0, all_y0, all_x1, all_y1)


# ------------------------------------------------------------ 缩放 ----
def downsample_average(im, tw, th, fit="stretch"):
    """面积平均降采样到 tw×th（无网格时的平滑像素化；防摩尔纹）。

    与 nearest（丢信息）/ 网格采样（无网格不适用）不同，平均法保留每格主色。
    输入可带 alpha（绿幕抠像后）：透明像素不参与色平均；
    输出 alpha 两态化 —— 格内不透明占比 ≥1/2 → 不透明（取不透明像素均值），否则透明。
    fit: 'stretch'（默认，直接缩放，可能拉伸失真）
         'contain'（等比适配：保持源宽高比，长边对齐目标，居中留透明边——角色不变形）
    """
    im = im.convert("RGBA")
    w, h = im.size
    if fit == "contain" and (w, h) != (tw, th):
        # 等比：缩到目标画布内最大尺寸，居中放置（透明留白，不拉伸）
        scale = min(tw / w, th / h)
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        small = downsample_average(im, nw, nh, fit="stretch")
        out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        out.paste(small, ((tw - nw) // 2, (th - nh) // 2))
        return out
    out = Image.new("RGBA", (tw, th))
    po, pi = out.load(), im.load()
    for ty in range(th):
        y0 = ty * h // th
        y1 = max(y0 + 1, (ty + 1) * h // th)
        for tx in range(tw):
            x0 = tx * w // tw
            x1 = max(x0 + 1, (tx + 1) * w // tw)
            n = 0
            r = g = b = 0
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    c = pi[xx, yy]
                    if c[3] == 0:
                        continue
                    r += c[0]
                    g += c[1]
                    b += c[2]
                    n += 1
            if n:
                po[tx, ty] = (r // n, g // n, b // n, 255)
            else:
                po[tx, ty] = (0, 0, 0, 0)
    return out


def downsample_nearest(im, tw, th):
    """nearest 整数降采样（保持硬边）；仅当原尺寸是目标的整数倍时推荐。"""
    if tw == 0 or th == 0:
        raise ValueError("目标尺寸不能为 0")
    fx, fy = im.width / tw, im.height / th
    if abs(fx - round(fx)) > 1e-6 or abs(fy - round(fy)) > 1e-6:
        # 非整数倍：用面积平均兜底（避免最近邻取点偏移产生锯齿）
        return downsample_average(im, tw, th)
    return im.convert("RGBA").resize((tw, th), Image.NEAREST)


# ------------------------------------------------------------ 绿幕抠像 ----
def is_greenish(rgb, gain=1.1):
    """色度特征：绿色通道显著高于 R/B（绿幕绿）。阈值为经验值，适配 (20,180,40) 类绿幕。"""
    r, g, b = rgb[0], rgb[1], rgb[2]
    return g > 60 and g > r * gain and g > b * gain


def detect_green_screen(im):
    """检测图像是否为绿幕背景（四角众数是否绿）。返回幕色 (r,g,b) 或 None。"""
    im = im.convert("RGB")
    px = im.load()
    w, h = im.size
    from collections import Counter
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    bg = Counter(corners).most_common(1)[0][0]
    return bg if is_greenish(bg) else None


def chroma_key(im, bg_rgb=None, green_gain=1.1, soft=0.0):
    """绿幕抠像：绿色背景像素转 alpha=0（按色度判定，与亮度无关——灰衣灰身不受影响）。

    bg_rgb：绿幕参考色（None 时自动检测四角；检测不到绿幕则原样返回）。
    green_gain：绿判定增益（G > R*增益 且 G > B*增益）。
    soft：边缘软化系数 0~1（0=两态硬边，默认；>0 使接近绿的像素渐变透明，用于防边缘绿溢）。
    返回 RGBA 图。
    """
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    if bg_rgb is None:
        bg_rgb = detect_green_screen(im)
        if bg_rgb is None:
            return im
    br, bg_, bb = bg_rgb
    # 以幕色为基准的"绿度"：G 超出 R/B 预期幅度的量
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            # 相对幕色饱和度：G 远高于 R/B（差距至少 40 且 G>R*1.15）
            if g > 60 and g > r * green_gain and g > b * green_gain \
                    and (g - r) > 40 and (g - b) > 40:
                if soft > 0:
                    # 软化：按绿距离线性插值 alpha（保留角色边缘的绿溢过渡）
                    dist = min((g - r), (g - b)) - 40
                    t = max(0.0, min(1.0, dist / (40 * soft)))
                    px[x, y] = (0, 0, 0, int(255 * (1 - t)))
                else:
                    px[x, y] = (0, 0, 0, 0)
    return im


# ------------------------------------------------------------ 背景清除 ----
def remove_bg_connected(im, bg_rgb=None, tol=24, bg_tol=None):
    """从画布边界 4-连通地清除背景色（被主体包住的同色格保留不开洞）。

    bg_rgb=None 时取四角众数为背景；tol 为 RGB 距离（单通道累计）。
    返回 RGBA 图（背景像素 alpha=0，其余 alpha=255）。
    """
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    if bg_rgb is None:
        from collections import Counter
        corners = [px[0, 0][:3], px[w - 1, 0][:3], px[0, h - 1][:3], px[w - 1, h - 1][:3]]
        bg_rgb = Counter(corners).most_common(1)[0][0]
    tol2 = (bg_tol if bg_tol is not None else tol) * 3
    # 迭代边界（去除四角 1px 边框后的内容余量）
    from collections import deque
    seen = set()
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            q.append((x, y))
    while q:
        x, y = q.popleft()
        if (x, y) in seen:
            continue
        seen.add((x, y))
        c = px[x, y]
        d = abs(c[0] - bg_rgb[0]) + abs(c[1] - bg_rgb[1]) + abs(c[2] - bg_rgb[2])
        if d > tol2:
            continue
        px[x, y] = (0, 0, 0, 0)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
                q.append((nx, ny))
    return im


# ------------------------------------------------------------ 主流程 ----
def video_standardize(video, out, *, fps=None, size=None, crop="auto",
                      box=None, bg_tol=60, colors=16, palette=None,
                      outline=None, make_gif=True, make_html=True,
                      keep_frames=True, grid=None, sampling="mode", bg="auto",
                      key="auto", fit="contain", temporal=0, stabilize=3, make_sheet=True):
    """视频标准化主流程。返回 report dict。

    size: 目标像素尺寸 (tw,th)；None=不缩放（仅量化）。
    crop: 'auto'|'none'|'fixed'；auto=全程合并 bbox 裁剪；fixed=使用 box 固定框。
    box: (x0,y0,x1,y1) 固定裁剪框。
    grid: 若指定（如 4），走 standardize.grid 采样路径（仅当视频确为网格放大时）；
          默认 None = 像素化降采样路径（AI 动态视频推荐）。
    outline: 描边色 (r,g,b) 或 None（不描边）。
    key: 'auto'|'green'|'none'；green=绿幕抠像（色度判定，原始分辨率做，灰衣不误删）；
         auto=四角检测到绿幕则抠像；none=不做。
    temporal: 时间维滤波窗口帧数（奇数；0/1=关闭，**默认 0**；运动感知中值，量化前执行）
    stabilize: 时间众数稳定窗口帧数（0/1=关闭，**默认 3**；量化后、描边前执行；只替换少数派、平局保留当前帧，
              拖影远小于中值——与 video-studio.html 的「后处理·时间稳定」同口径）——压静止区域帧间变色（闪烁）；
              插在共享色板量化之前（先滤波再映射，色数不增）。仅降采样路径生效（--grid 路径不接）。
    make_sheet: 导出 <名>_sheet.png + <名>_sheet.json（Aseprite JSON Hash，契约 §2）。
    """
    import tempfile
    rep = {"video": video}
    probe = ffprobe_info(video)
    rep.update(probe)
    tmpdir = tempfile.mkdtemp(prefix="pixcli-vidstd-")
    frames = extract_frames(video, tmpdir, fps=fps)
    rep["extracted"] = len(frames)
    rep["fps"] = fps or probe["fps"]

    # 绿幕抠像（原始分辨率、色度判定；抠像后内容 bbox 用 alpha 而非颜色差）
    keyed = False
    if key in ("auto", "green"):
        from PIL import Image as _IM
        im0 = _IM.open(frames[0])
        if detect_green_screen(im0) is not None or key == "green":
            frames = [chroma_key(_IM.open(p)) for p in frames]
            keyed = True
    if keyed:
        rep["key"] = "green"
    else:
        rep["key"] = None
    # 抠像后按 alpha 计算全程 bbox（无颜色差误判）
    alpha_bbox = None
    if keyed and crop == "auto" and box is None:
        from collections import deque
        xs, ys = [], []
        for f in frames:
            px = f.load()
            w, h = f.size
            for y in range(0, h, 2):
                for x in range(0, w, 2):
                    if px[x, y][3] > 0:
                        xs.append(x)
                        ys.append(y)
        if xs:
            alpha_bbox = (min(xs), min(ys), max(xs), max(ys))
            box = alpha_bbox
            rep["crop_from"] = "alpha"

    # 裁切（非绿幕路径的 frames 此前是文件路径：先算 bbox，再统一物化为图像）
    if crop == "auto" and box is None and not keyed:
        bb = merged_content_bbox(frames, bg_tol=bg_tol)
        if bb:
            box = bb
    if not keyed:
        frames = [Image.open(p).convert("RGBA") for p in frames]
    if box and crop in ("auto", "fixed"):
        x0, y0, x1, y1 = box
        frames = [f.crop((x0, y0, x1 + 1, y1 + 1)) for f in frames]
        rep["crop"] = box
    else:
        rep["crop"] = None

    # 缩放：网格路径 or 像素化路径
    if grid:
        cw, ch = (int(grid), int(grid)) if isinstance(grid, int) else grid
        from palette import Palette as _Pal
        _pal = _Pal.load(palette) if palette else None
        outs, srep = stdmod.standardize_frames(
            frames, grid=(cw, ch), sampling=sampling, colors=colors,
            palette=_pal, bg="keep")
        rep["grid"] = (cw, ch)
    else:
        if size:
            tw, th = size
            outs = [downsample_average(f, tw, th, fit=fit) for f in frames]
        else:
            outs = [f.convert("RGBA") for f in frames]
        # 背景透明化：绿幕已抠像（alpha 两态，跳过）；非绿幕才做连通清除（与背景色接近，容差 24）
        if not keyed:
            if bg == "auto":
                outs = [remove_bg_connected(f, bg_tol=24) for f in outs]
            elif bg and bg != "keep":
                from palette import hex_to_rgb
                outs = [remove_bg_connected(f, bg_rgb=hex_to_rgb(bg), bg_tol=24) for f in outs]
        srep = {"colors_out": [None] * len(outs)}
        # 时间维滤波（必须在共享色板量化之前：先滤波再映射，色数不增、仍受 ≤N 色约束）
        if temporal and temporal > 1:
            outs = stdmod.temporal_median_frames(outs, w=temporal)
            rep["temporal"] = temporal
        # 跨帧共享色板量化
        if palette:
            from palette import Palette
            pal = Palette.load(palette)
            outs = [stdmod.snap_to_palette(f.convert("RGBA"), pal) for f in outs]
            srep = {"colors_out": [len(set((p[0], p[1], p[2]) for p in f.getdata() if p[3] > 0))
                                   for f in outs],
                    "quantize": "palette:{}".format(pal.name)}
        elif colors and colors > 0:
            # 有描边时：主体量化保留 colors-1 色，描边色占 1 配额（工程规范 ≤16 色含描边）
            k = colors - (1 if outline else 0)
            pooled = Counter()
            for f in outs:
                pooled.update((p[0], p[1], p[2]) for p in f.getdata() if p[3] > 0)
            pal = stdmod.build_palette_k(list(pooled.items()), k)
            outs = [stdmod.map_with_palette(f, pal) for f in outs]
            srep = {"colors_out": [None] * len(outs),
                    "quantize": "k={}（跨帧合并聚类）".format(k)}
        # 时间众数稳定（量化后：众数只取已有色，不引出色板外新色；默认 3 帧）
        if stabilize and stabilize > 1:
            outs = stdmod.temporal_mode_frames(outs, w=stabilize)
            rep["stabilize"] = stabilize
        # 描边
        if outline:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "generation"))
            from canvas import Canvas
            oc = outline
            if isinstance(oc, str):
                from palette import hex_to_rgb
                oc = hex_to_rgb(oc)
            outs = [_outline(f, oc) for f in outs]
            srep["outline"] = oc
        # 最终色数（含描边后；不透明像素唯一色）
        srep["colors_out"] = [len(set((p[0], p[1], p[2]) for p in f.getdata() if p[3] > 0))
                              for f in outs]
        rep["quantize"] = srep.get("quantize")
        rep["colors_out"] = srep.get("colors_out")

    # 输出
    os.makedirs(out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(video))[0]
    if keep_frames:
        for i, f in enumerate(outs):
            f.convert("RGBA").save(os.path.join(out, "{}_{:02d}.png".format(stem, i)))
    if make_gif and outs:
        anim.export_gif([f.convert("RGBA") for f in outs],
                        os.path.join(out, stem + ".gif"),
                        fps=rep["fps"] if rep["fps"] else 10)
    if make_html and outs:
        anim.export_html([f.convert("RGBA") for f in outs],
                         os.path.join(out, stem + ".html"),
                         title=stem, fps=rep["fps"] if rep["fps"] else 10)
    if make_sheet and outs:
        import atlas
        sheet_path, json_path, _meta = atlas.export_atlas(
            [f.convert("RGBA") for f in outs],
            os.path.join(out, stem + "_sheet.png"),
            json_path=os.path.join(out, stem + "_sheet.json"),
            fps=rep["fps"] if rep["fps"] else 10, tag=stem,
            source_route="sampled")   # 视频派生 → 采样路线（契约 §2 来源路线）
        rep["sheet"] = sheet_path
        rep["atlas"] = json_path
    rep["out"] = out
    rep["frames_used"] = len(outs)
    return rep


def _outline(im, color):
    """给 RGBA 图加 1px 内描边（复用 canvas.outline_in 语义）。"""
    from canvas import Canvas
    cv = Canvas.from_image(im.convert("RGBA"))
    cv.outline_in(tuple(color) + (255,))
    return cv.to_image()
