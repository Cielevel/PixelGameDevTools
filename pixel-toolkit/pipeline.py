#!/usr/bin/env python3
"""管线配方（pipeline JSON）：一份 JSON 描述处理链，`pixcli run` 执行（节点系统 Phase 0）。

定位（2026-09-09「像素工具形态迁移」定案）：
- 图 = **线性 stage 列表**；schema 预留 DAG 演进（stage 的 id/from 字段已定义、暂不实现分支）
- **一核两宿主**：本模块是权威执行器（CPython：CLI / CI / Agent）；
  浏览器节点工作台（Phase 1，Pyodide 加载同一核心）只是编辑器，产物与本模块逐字节一致
- 端口以 bundle 状态槽承载：frames（**帧序列整体对象**——时间维节点需要全部帧，
  绝不逐帧连线）/ palette / report（门禁）
- **门禁是一等节点**：gate.check / gate.stability 在管线内拦截，任一不通过 exit 1
- **确定性**：同输入同参数 → 逐字节一致产物（无时间戳，与 manifest 同口径，可进 CI diff）
- 阶段语义与 video.py / standardize.py 同源分解——本模块**只做编排不重写算法**；
  既有子命令（video-std / standardize）行为不受影响

配方结构（version 1）::

    {
      "version": 1,
      "name": "ai-video → 64x64 四件套",        # 可选，仅展示用
      "input":  {"op": "source.video", "params": {"path": "in.mp4", "fps": 12}},
      "stages": [
        {"op": "chroma-key",   "params": {"mode": "auto"}},
        {"op": "crop",         "params": {"mode": "auto"}},
        {"op": "resize",       "params": {"size": [64, 64]}},
        {"op": "quantize",     "params": {"colors": 16}},
        {"op": "temporal-mode", "params": {"window": 3}},
        {"op": "outline",      "params": {"color": "#182b54"}},
        {"op": "export-frames"}, {"op": "export-gif"}, {"op": "export-sheet"}
      ],
      "output": {"dir": "out/"}                    # 任一 export-* 节点存在时必需
    }

示例见 examples/*.pipeline.json；可用节点 `pixcli ops` 自省（--json 供工具/Agent 读）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anim
import atlas as atlasmod
import check as checkmod
import palette as palmod
import stability as stabmod
import standardize as stdmod
import video as vidmod
from PIL import Image

SCHEMA_VERSION = 1


class PipelineError(Exception):
    """配方校验或执行错误（错误信息可直接展示给用户/Agent）。"""


# ------------------------------------------------------------ 数据流 ----
class Bundle:
    """沿管线流动的状态槽（线性 stage 依次改写；未来 DAG 时每个节点各持一份副本）。

    frames 是帧序列整体对象：图像（单帧）与视频共用同一槽——单图 = 1 帧序列。
    """

    def __init__(self):
        self.frames = []          # list[PIL.Image RGBA]
        self.fps = None           # float | None（GIF/HTML/sheet 帧率）
        self.name = "out"         # 导出文件名主干
        self.meta = {}            # 各阶段报告（key/crop/grid/quantize/...）
        self.exported_frames = [] # export-frames 写出的路径（gate.check 消费）
        self.exports = []         # 全部导出产物路径
        self.gates = []           # [(op, ok, issues)]


# ------------------------------------------------------------ 参数 ----
def _param(key, ptype, default=None, help="", required=False):
    return {"key": key, "type": ptype, "default": default,
            "help": help, "required": required}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _coerce(decl, value, op_name):
    """按声明把 JSON 值转成 Python 值；非法值抛 PipelineError。"""
    k, t = decl["key"], decl["type"]
    if t == "str":
        if not isinstance(value, str):
            raise PipelineError("{}.{} 应为字符串".format(op_name, k))
        return value
    if t == "int":
        if not _is_int(value):
            raise PipelineError("{}.{} 应为整数".format(op_name, k))
        return value
    if t == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PipelineError("{}.{} 应为数值".format(op_name, k))
        return float(value)
    if t == "bool":
        if not isinstance(value, bool):
            raise PipelineError("{}.{} 应为布尔".format(op_name, k))
        return value
    if t == "size":  # [w,h] 或 "WxH" → (w,h)
        if isinstance(value, str) and "x" in value.lower():
            value = [v for v in value.lower().split("x") if v != ""]
            try:
                value = [int(v) for v in value]
            except ValueError:
                raise PipelineError("{}.{} 应为 [宽,高] 或 \"宽x高\"".format(op_name, k))
        if not (isinstance(value, (list, tuple)) and len(value) == 2
                and all(_is_int(v) and v > 0 for v in value)):
            raise PipelineError("{}.{} 应为 [宽,高]（正整数）".format(op_name, k))
        return (value[0], value[1])
    if t == "box":  # [x0,y0,x1,y1]
        if not (isinstance(value, (list, tuple)) and len(value) == 4
                and all(_is_int(v) for v in value)):
            raise PipelineError("{}.{} 应为 [x0,y0,x1,y1]".format(op_name, k))
        return tuple(value)
    if t == "color":  # "#rrggbb" → (r,g,b)
        if not isinstance(value, str):
            raise PipelineError("{}.{} 应为 #rrggbb 字符串".format(op_name, k))
        try:
            return palmod.hex_to_rgb(value)
        except Exception:
            raise PipelineError("{}.{} 无法解析为颜色: {!r}".format(op_name, k, value))
    if t == "grid":  # "auto" | N | [w,h]
        if value == "auto":
            return "auto"
        if _is_int(value):
            return (value, value)
        if isinstance(value, (list, tuple)) and len(value) == 2 \
                and all(_is_int(v) and v > 0 for v in value):
            return (value[0], value[1])
        raise PipelineError('{}.{} 应为 "auto" / N / [w,h]'.format(op_name, k))
    if t.startswith("choice:"):
        opts = t.split(":", 1)[1].split("|")
        if value not in opts:
            raise PipelineError("{}.{} 应为 {} 之一，收到 {!r}".format(
                op_name, k, "/".join(opts), value))
        return value
    if t == "strlist":
        if isinstance(value, str):
            return [value]
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            return list(value)
        raise PipelineError("{}.{} 应为字符串或字符串列表".format(op_name, k))
    raise PipelineError("内部错误：未知参数类型 {}".format(t))


def _resolve_params(op_name, given):
    """声明 ∪ 给定 → 完整参数 dict；未知参数 / 缺必填 → PipelineError。"""
    decls = {d["key"]: d for d in OPS[op_name]["params"]}
    for k in given or {}:
        if k not in decls:
            raise PipelineError("{}.{} 不是有效参数（可用: {}）".format(
                op_name, k, ", ".join(sorted(decls)) or "无"))
    out = {}
    for k, d in decls.items():
        if given and k in given:
            out[k] = _coerce(d, given[k], op_name)
        elif d["required"]:
            raise PipelineError("{}.{} 必填".format(op_name, k))
        else:
            out[k] = d["default"]
    return out


# ------------------------------------------------------------ 注册表 ----
OPS = {}


def op(name, category, title, inputs="frames", outputs="frames", params=()):
    """登记一个节点。category: source / transform / export / gate。"""
    def deco(fn):
        OPS[name] = {"name": name, "category": category, "title": title,
                     "io": [inputs, outputs], "params": list(params), "fn": fn}
        return fn
    return deco


def _collect_images(paths):
    """路径列表（文件或目录，目录递归收 PNG/JPG/JPEG/WEBP）→ 排序后的文件列表。"""
    exts = (".png", ".jpg", ".jpeg", ".webp")
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs.sort()
                files += [os.path.join(root, n) for n in sorted(names)
                          if n.lower().endswith(exts)]
        elif os.path.isfile(p):
            files.append(p)
        else:
            raise PipelineError("输入路径不存在: {}".format(p))
    if not files:
        raise PipelineError("未收集到任何图像输入: {}".format(", ".join(paths)))
    return files


def _common_stem(paths):
    """首文件主干去掉尾部 _NN 帧号（mob_idle_00 → mob_idle）作为导出命名主干。"""
    import re
    stem = os.path.splitext(os.path.basename(paths[0]))[0]
    return re.sub(r"_\d+$", "", stem) or stem


# ---------- 源 ----------
@op("source.video", "source", "视频抽帧（需要 ffmpeg）", inputs="-", params=[
    _param("path", "str", required=True, help="输入视频路径（mp4/webm/mov）"),
    _param("fps", "float", help="重采样帧率（默认视频原生）"),
    _param("start", "float", help="起始秒"),
    _param("end", "float", help="结束秒"),
    _param("name", "str", help="导出命名主干（默认视频文件名主干）"),
])
def _src_video(b, p, ctx):
    probe = vidmod.ffprobe_info(p["path"])
    import tempfile
    tmp = tempfile.mkdtemp(prefix="pixcli-pipeline-vid-")
    paths = vidmod.extract_frames(p["path"], tmp, fps=p["fps"],
                                  start=p["start"], end=p["end"])
    b.frames = [Image.open(f).convert("RGBA") for f in paths]
    b.fps = p["fps"] if p["fps"] else probe["fps"]
    b.name = p["name"] or os.path.splitext(os.path.basename(p["path"]))[0]
    b.meta["source"] = {"video": os.path.basename(p["path"]), **probe,
                        "extracted": len(paths)}
    return "{} 帧（{}x{} @{}fps {}）".format(
        len(paths), probe["width"], probe["height"],
        round(b.fps, 2) if b.fps else "?", probe["codec"])


@op("source.images", "source", "图像/帧目录载入（多图即帧序列）", inputs="-", params=[
    _param("paths", "strlist", required=True, help="图像或目录列表（目录递归收集，按文件名排序）"),
    _param("fps", "float", 10.0, help="帧率（GIF/HTML/sheet 用）"),
    _param("name", "str", help="导出命名主干（默认首文件主干去 _NN 帧号）"),
])
def _src_images(b, p, ctx):
    files = _collect_images(p["paths"])
    b.frames = [Image.open(f).convert("RGBA") for f in files]
    b.fps = p["fps"]
    b.name = p["name"] or _common_stem(files)
    b.meta["source"] = {"images": len(files)}
    return "{} 帧（{}x{}）".format(len(files), *b.frames[0].size)


# ---------- 变换（语义与 video.py / standardize.py 同源） ----------
@op("chroma-key", "transform", "绿幕抠像（色度判定，原始分辨率做）", params=[
    _param("mode", "choice:auto|green|none", "auto",
           help="auto=四角检测到绿幕才抠 | green=强制 | none=跳过"),
    _param("gain", "float", 1.1, help="绿判定增益（G > R*gain 且 G > B*gain）"),
    _param("soft", "float", 0.0, help="边缘软化 0~1（0=两态硬边，默认）"),
])
def _chroma_key(b, p, ctx):
    if p["mode"] == "none":
        b.meta["key"] = None
        return "跳过（mode=none）"
    if p["mode"] == "auto" and vidmod.detect_green_screen(b.frames[0]) is None:
        b.meta["key"] = None
        return "未检测到绿幕，不抠像"
    bg = vidmod.detect_green_screen(b.frames[0])
    b.frames = [vidmod.chroma_key(f, bg_rgb=bg, green_gain=p["gain"], soft=p["soft"])
                for f in b.frames]
    b.meta["key"] = "green"
    return "绿幕抠像（幕色 {}）".format(bg)


@op("crop", "transform", "内容裁剪（绿幕路径按 alpha，否则按背景色差）", params=[
    _param("mode", "choice:auto|none|fixed", "auto",
           help="auto=全程合并内容 bbox | none=不裁 | fixed=用 box"),
    _param("box", "box", help="固定裁剪框 [x0,y0,x1,y1]（mode=fixed 必填；auto 时给出则优先生效）"),
    _param("bg-tol", "int", 60, help="非绿幕路径的背景判定亮度差阈值"),
])
def _crop(b, p, ctx):
    if p["mode"] == "none":
        b.meta["crop"] = None
        return "不裁剪"
    if p["box"] is not None:
        box = p["box"]
        src = "fixed"
    elif b.meta.get("key"):
        box = _merged_alpha_bbox(b.frames)
        src = "alpha"
    else:
        box = _merged_content_bbox_frames(b.frames, p["bg-tol"])
        src = "content"
    if box is None:
        b.meta["crop"] = None
        return "无内容，不裁剪"
    x0, y0, x1, y1 = box
    b.frames = [f.crop((x0, y0, x1 + 1, y1 + 1)) for f in b.frames]
    b.meta["crop"] = box
    return "{}（{}）→ {}x{}".format(box, src, b.frames[0].size[0], b.frames[0].size[1])


def _merged_alpha_bbox(frames):
    """抠像后的全程 alpha 并集 bbox（与 video_standardize 同口径，步长 2）。"""
    xs, ys = [], []
    for f in frames:
        px = f.load()
        w, h = f.size
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                if px[x, y][3] > 0:
                    xs.append(x)
                    ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _merged_content_bbox_frames(frames, bg_tol):
    """多帧内容 bbox 并集（video.merged_content_bbox 的 Image 对象版，同口径）。"""
    best = None
    for f in frames:
        b = vidmod.content_bbox(f, bg_tol=bg_tol)
        if not b:
            continue
        best = b if best is None else (min(best[0], b[0]), min(best[1], b[1]),
                                       max(best[2], b[2]), max(best[3], b[3]))
    return best


@op("resize", "transform", "面积平均降采样（防摩尔纹；透明像素不参与色平均）", params=[
    _param("size", "size", required=True, help="目标尺寸 [w,h]"),
    _param("fit", "choice:contain|stretch", "contain",
           help="contain=等比适配居中留透明边（默认）| stretch=直接拉伸"),
])
def _resize(b, p, ctx):
    tw, th = p["size"]
    b.frames = [vidmod.downsample_average(f, tw, th, fit=p["fit"]) for f in b.frames]
    return "{} 帧 → {}x{}（{}）".format(len(b.frames), tw, th, p["fit"])


@op("grid-sample", "transform", "网格还原 + 逐格鲁棒采样（JPEG/放大源；多帧共享网格）", params=[
    _param("grid", "grid", "auto", help='"auto"=自相关检测 | N | [w,h]'),
    _param("sampling", "choice:mode|median", "mode",
           help="格内众数（默认，JPEG 噪声吸收）| 逐通道中位数"),
    _param("bg", "choice:auto|keep", "auto", help="auto=四角一致色判为背景→透明 | keep=保留"),
    _param("bg-tol", "int", 16, help="背景判定 RGB 距离容差"),
])
def _grid_sample(b, p, ctx):
    outs, rep = stdmod.standardize_frames(
        b.frames, grid=p["grid"], sampling=p["sampling"], colors=0,
        palette=None, bg=p["bg"], bg_tol=p["bg-tol"])
    b.frames = outs
    b.meta["grid"] = rep["grid_cell"]
    b.meta["grid_bg"] = rep["bg"]
    return "网格 {} → {}x{}".format(rep["grid_cell"], *b.frames[0].size)


@op("remove-bg", "transform", "边界 4-连通背景清除（非绿幕路径；绿幕已抠像时跳过）", params=[
    _param("mode", "choice:auto|keep", "auto", help="auto=四角众数为背景 | keep=保留背景"),
    _param("tol", "int", 24, help="背景判定 RGB 距离（单通道累计口径 24→容差 72）"),
])
def _remove_bg(b, p, ctx):
    if b.meta.get("key"):
        return "跳过（绿幕已抠像，alpha 两态）"
    if p["mode"] == "keep":
        return "保留背景"
    b.frames = [vidmod.remove_bg_connected(f, bg_tol=p["tol"]) for f in b.frames]
    return "背景透明化（连通清除，容差 {}）".format(p["tol"])


@op("temporal-median", "transform", "时间维中值滤波（量化前；运动感知，压闪烁但拖影较大）", params=[
    _param("window", "int", 3, help="窗口帧数（奇数；≤1 = 跳过）"),
])
def _temporal_median(b, p, ctx):
    if p["window"] <= 1:
        return "跳过（window≤1）"
    b.frames = stdmod.temporal_median_frames(b.frames, w=p["window"])
    b.meta["temporal"] = p["window"]
    return "窗口 {} 帧（量化前中值）".format(p["window"])


@op("quantize", "transform", "跨帧共享量化（工程调色板优先；否则 OKLab k-means 合并聚类）", params=[
    _param("colors", "int", 16, help="目标色数（无 palette 时生效；0=不量化）"),
    _param("palette", "str", help="工程调色板 JSON 路径（优先于 colors）"),
])
def _quantize(b, p, ctx):
    if p["palette"]:
        pal = palmod.Palette.load(p["palette"])
        b.frames = [stdmod.snap_to_palette(f.convert("RGBA"), pal) for f in b.frames]
        b.meta["quantize"] = "palette:{}".format(pal.name)
        return "归板 {}（{}）".format(len(pal.colors), pal.name)
    if not p["colors"] or p["colors"] <= 0:
        b.meta["quantize"] = None
        return "不量化"
    k = p["colors"]
    # 与 video_standardize 同口径：后续有描边则主体量化保留 k-1 色（描边占 1 配额，含 ≤16 色规范）
    if "outline" in ctx["later"]:
        k -= 1
        b.meta["outline_reserved"] = True
    from collections import Counter
    pooled = Counter()
    for f in b.frames:
        pooled.update((px[0], px[1], px[2]) for px in f.getdata() if px[3] > 0)
    pal = stdmod.build_palette_k(list(pooled.items()), k)
    b.frames = [stdmod.map_with_palette(f, pal) for f in b.frames]
    b.meta["quantize"] = "k={}".format(k)
    return "k={}（跨帧合并聚类{}）".format(k, "，描边预留 1 色" if k != p["colors"] else "")


@op("temporal-mode", "transform", "时间众数稳定（量化后；只替换少数派，低拖影压闪烁）", params=[
    _param("window", "int", 3, help="窗口帧数（≤1 = 跳过；默认 3，与 video-std 同口径）"),
])
def _temporal_mode(b, p, ctx):
    if p["window"] <= 1:
        return "跳过（window≤1）"
    b.frames = stdmod.temporal_mode_frames(b.frames, w=p["window"])
    b.meta["stabilize"] = p["window"]
    return "窗口 {} 帧（量化后众数）".format(p["window"])


@op("outline", "transform", "1px 内描边（复用 generation/canvas.outline_in 语义）", params=[
    _param("color", "color", required=True, help="描边色 #rrggbb"),
])
def _outline(b, p, ctx):
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "generation"))
    b.frames = [vidmod._outline(f, p["color"]) for f in b.frames]
    b.meta["outline"] = tuple(p["color"])
    return "描边 rgb{}".format(tuple(p["color"]))


# ---------- 导出 ----------
@op("export-frames", "export", "帧序列 PNG（<name>_NN.png）", outputs="-", params=[])
def _export_frames(b, p, ctx):
    for i, f in enumerate(b.frames):
        path = os.path.join(ctx["out_dir"], "{}_{:02d}.png".format(b.name, i))
        f.convert("RGBA").save(path)
        b.exported_frames.append(path)
    return "{} 帧 → {}".format(len(b.frames), ctx["out_dir"])


@op("export-gif", "export", "循环 GIF", outputs="-", params=[
    _param("fps", "int", help="帧率（默认源帧率或 10）"),
    _param("pingpong", "bool", False, help="往复播放"),
])
def _export_gif(b, p, ctx):
    fps = p["fps"] or (int(b.fps) if b.fps else 10)
    path = os.path.join(ctx["out_dir"], b.name + ".gif")
    anim.export_gif([f.convert("RGBA") for f in b.frames], path,
                    fps=fps, pingpong=p["pingpong"])
    b.exports.append(path)
    return "{}（{} fps{}）".format(path, fps, "，往复" if p["pingpong"] else "")


@op("export-html", "export", "自包含 HTML 播放器", outputs="-", params=[
    _param("fps", "int", help="帧率（默认源帧率或 10）"),
    _param("zoom", "int", 6, help="预览放大倍数"),
])
def _export_html(b, p, ctx):
    fps = p["fps"] or (int(b.fps) if b.fps else 10)
    path = os.path.join(ctx["out_dir"], b.name + ".html")
    anim.export_html([f.convert("RGBA") for f in b.frames], path,
                     title=b.name, fps=fps, zoom=p["zoom"])
    b.exports.append(path)
    return path


@op("export-sheet", "export", "sprite sheet + Aseprite JSON（契约四件套；可选附 TexturePacker Hash）",
    outputs="-", params=[
    _param("fps", "int", help="帧率（默认源帧率或 10）"),
    _param("tag", "str", help="动画标签（默认 name）"),
    _param("source-route", "choice:sampled|authored", "sampled",
           help="来源路线（写入 meta.sourceRoute；管线产物默认 sampled）"),
    _param("format", "choice:aseprite|hash", "aseprite",
           help="aseprite=JSON Hash（默认）| hash=额外写 TexturePacker JSON Hash（契约 §3 Web 适配）"),
])
def _export_sheet(b, p, ctx):
    fps = p["fps"] or (int(b.fps) if b.fps else 10)
    sheet_path = os.path.join(ctx["out_dir"], b.name + "_sheet.png")
    json_path = os.path.join(ctx["out_dir"], b.name + "_sheet.json")
    sheet_path, json_path, _meta = atlasmod.export_atlas(
        [f.convert("RGBA") for f in b.frames], sheet_path,
        json_path=json_path, fps=fps, tag=p["tag"] or b.name,
        source_route=p["source-route"])
    b.exports += [sheet_path, json_path]
    msg = "{} / {}".format(sheet_path, json_path)
    if p["format"] == "hash":
        hash_path = os.path.join(ctx["out_dir"], b.name + "_hash.json")
        with open(json_path, encoding="utf-8") as fp:
            meta = json.load(fp)
        with open(hash_path, "w", encoding="utf-8") as fp:
            json.dump(atlasmod.to_hash(meta), fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        b.exports.append(hash_path)
        msg += " / {}".format(hash_path)
    return msg


# ---------- 门禁 ----------
@op("gate-check", "gate", "程序化门禁（pixcli check 同口径；需先 export-frames）",
    outputs="report", params=[
    _param("size", "size", help="期望帧尺寸 [w,h]"),
    _param("max-colors", "int", 16, help="单帧色数上限"),
    _param("palette", "str", help="工程调色板 JSON（校验归板）"),
    _param("components-max", "int", help="连通域上限（>N 报 P1）"),
    _param("no-frames", "bool", False, help="关闭帧组对齐检查"),
    _param("no-anim", "bool", False, help="关闭动画一致性检查"),
])
def _gate_check(b, p, ctx):
    results = checkmod.run(
        b.exported_frames, expected_size=p["size"], max_colors=p["max-colors"],
        palette=palmod.Palette.load(p["palette"]) if p["palette"] else None,
        frames=not p["no-frames"], anim=not p["no-anim"],
        components_max=p["components-max"])
    n = {"P0": 0, "P1": 0, "P2": 0}
    for kind, ref, issues in results:
        for sev, msg in issues:
            n[sev] += 1
    ok = not (n["P0"] or n["P1"])
    b.gates.append(("gate-check", ok, n))
    return "{} 帧，P0×{} P1×{} P2×{} → {}".format(
        len(b.exported_frames), n["P0"], n["P1"], n["P2"], "通过" if ok else "不通过")


@op("gate-stability", "gate", "时间稳定性门禁（pixcli stability 同口径，内存帧直判）",
    outputs="report", params=[
    _param("preset", "choice:strict|standard|quick", "strict",
           help="strict=5%/3.0 | standard=10%/3.5 | quick=30%/4.0"),
    _param("max-flip", "float", help="核心静态格变色率上限 %（覆盖档位）"),
    _param("max-colors", "float", help="单格平均色数上限（覆盖档位）"),
    _param("min-static", "int", stabmod.STATIC_MIN, help="静态格下限（低于报样本不足）"),
])
def _gate_stability(b, p, ctx):
    if len(b.frames) < 2:
        ok, issues = False, ["少于 2 帧，无稳定性可判"]
        b.gates.append(("gate-stability", ok, issues))
        return "不通过（帧数不足）"
    w, h = b.frames[0].size
    stats = stabmod.analyze_rgba([f.tobytes() for f in b.frames], w, h)
    max_flip, max_colors = stabmod.preset(p["preset"])
    if p["max-flip"] is not None:
        max_flip = p["max-flip"]
    if p["max-colors"] is not None:
        max_colors = p["max-colors"]
    ok, issues = stabmod.verdict(stats, max_flip, max_colors, p["min-static"])
    b.gates.append(("gate-stability", ok, issues))
    return "{}（flipCore {:.1f}% / 色 {:.2f}）→ {}".format(
        p["preset"], stats["flipCore"], stats["avgColors"], "通过" if ok else "不通过")


# ------------------------------------------------------------ 装载与校验 ----
def load_graph(path):
    """读配方 JSON 并做结构校验。返回 (graph, sha256 前 12 位)；错误抛 PipelineError。"""
    try:
        with open(path, encoding="utf-8") as fp:
            graph = json.load(fp)
    except OSError as e:
        raise PipelineError("配方无法读取: {}".format(e))
    except json.JSONDecodeError as e:
        raise PipelineError("配方不是合法 JSON: {}".format(e))
    if not isinstance(graph, dict):
        raise PipelineError("配方应为 JSON 对象")
    sha = hashlib.sha256(json.dumps(graph, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()[:12]
    return graph, sha


def validate(graph):
    """静态校验（op 存在 / 参数合法 / 顺序约束）。返回错误列表（空 = 通过）。"""
    errors = []
    if graph.get("version") != SCHEMA_VERSION:
        errors.append("version 应为 {}（收到 {!r}）".format(SCHEMA_VERSION, graph.get("version")))
    inp = graph.get("input")
    if not isinstance(inp, dict) or "op" not in inp:
        errors.append("input.op 必填（源节点，如 source.video / source.images）")
    else:
        if inp["op"] not in OPS:
            errors.append("input.op 未知节点: {}".format(inp["op"]))
        elif OPS[inp["op"]]["category"] != "source":
            errors.append("input.op 必须是源节点: {}".format(inp["op"]))
        else:
            try:
                _resolve_params(inp["op"], inp.get("params"))
            except PipelineError as e:
                errors.append("input: {}".format(e))
    stages = graph.get("stages")
    if not isinstance(stages, list) or not stages:
        errors.append("stages 应为非空列表")
        stages = stages or []
    seen_ops = []
    for i, st in enumerate(stages):
        if not isinstance(st, dict) or "op" not in st:
            errors.append("stages[{}] 缺 op".format(i))
            continue
        name = st["op"]
        if "from" in st or "id" in st:
            errors.append("stages[{}]（{}）: id/from 为 DAG 预留字段，version 1 暂不支持分支".format(i, name))
        if name not in OPS:
            errors.append("stages[{}] 未知节点: {}".format(i, name))
            continue
        if OPS[name]["category"] == "source":
            errors.append("stages[{}]（{}）: 源节点只能出现在 input".format(i, name))
        try:
            _resolve_params(name, st.get("params"))
        except PipelineError as e:
            errors.append("stages[{}] {}".format(i, e))
        seen_ops.append(name)
    # gate.check 消费 export-frames 写出的帧文件
    if "gate-check" in seen_ops and "export-frames" not in seen_ops:
        errors.append("gate-check 需要先有 export-frames（门禁读导出的帧文件）")
    has_export = any(OPS[o]["category"] == "export" for o in seen_ops if o in OPS)
    out_dir = (graph.get("output") or {}).get("dir")
    if has_export and not out_dir:
        errors.append("存在 export-* 节点但缺 output.dir")
    return errors


# ------------------------------------------------------------ 执行 ----
def run(graph, dry_run=False, log=None):
    """执行配方。返回 report dict：{ok, exits, exports, gates, stages}。

    dry_run=True 只打印执行计划（已含完整校验），不读源、不写文件。
    源节点/阶段失败抛 PipelineError；门禁不通过记入 gates，最终 ok=False。
    """
    if log is None:
        log = lambda msg: None
    errors = validate(graph)
    if errors:
        raise PipelineError("配方校验未通过：\n  - " + "\n  - ".join(errors))
    stages = graph.get("stages") or []
    out_dir = (graph.get("output") or {}).get("dir")

    log("[管线] {}（version {}，{} 个阶段）".format(
        graph.get("name") or "(未命名)", graph.get("version"), 1 + len(stages)))
    if dry_run:
        log("  input: {}".format(graph["input"]["op"]))
        for i, st in enumerate(stages):
            p = _resolve_params(st["op"], st.get("params"))
            shown = " ".join("{}={}".format(k, v) for k, v in p.items() if v is not None)
            log("  [{:>2}] {:<16} {}".format(i + 1, st["op"], shown))
        log("  导出目录: {}".format(out_dir or "（无导出节点）"))
        log("  → 校验通过，dry-run 结束")
        return {"ok": True, "exports": [], "gates": [], "dry_run": True}

    b = Bundle()
    ctx = {"out_dir": None, "later": set()}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        ctx["out_dir"] = out_dir

    def _exec(name, params, index, total):
        p = _resolve_params(name, params)
        try:
            status = OPS[name]["fn"](b, p, ctx)
        except PipelineError:
            raise
        except Exception as e:
            raise PipelineError("stages[{}]（{}）执行失败: {}".format(index, name, e))
        log("  [{:>2}/{}] {:<16} {}".format(index + 1, total, name, status or ""))

    total = 1 + len(stages)
    _exec(graph["input"]["op"], graph["input"].get("params"), 0, total)
    for i, st in enumerate(stages):
        ctx["later"] = {s["op"] for s in stages[i + 1:]}
        _exec(st["op"], st.get("params"), i + 1, total)

    ok = all(g[1] for g in b.gates)
    if b.gates:
        log("[门禁] {} 项 → {}".format(len(b.gates), "全部通过" if ok else "存在不通过"))
        for name, gok, info in b.gates:
            if not gok:
                log("  ✗ {} {}".format(name, info))
    if b.exports or b.exported_frames:
        n_all = len(set(b.exports) | set(b.exported_frames))
        log("[产物] {} 个文件 → {}".format(n_all, out_dir))
    log("[汇总] {} 帧，门禁 {}/{} 通过 → {}".format(
        len(b.frames), sum(1 for g in b.gates if g[1]), len(b.gates),
        "通过" if ok else "不通过"))
    return {"ok": ok, "frames": len(b.frames), "exports": b.exports + b.exported_frames,
            "gates": b.gates, "name": b.name, "meta": b.meta}
