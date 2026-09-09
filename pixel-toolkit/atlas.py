#!/usr/bin/env python3
"""sprite sheet ↔ 元数据 JSON：生成与一致性门禁。

规格 = `agent-pipeline/shared/跨引擎交付契约.md` §1/§2/§4.2：

- **横向 sheet**（帧宽 = 原生画布宽；超单边上限时自动换行成网格，JSON 矩形同步换行）；
- **Aseprite JSON（Hash 变体）**：`trimmed=false`、`spriteSourceSize == frame == sourceSize`、
  逐帧 `duration`(ms)、`frameTags` 表达循环语义；
- **pivot 唯一且显式**：脚底水平中心 `(w/2, h-1)`，写在 `meta.pivot`（契约 §2 规则 2）。

`check()` 是 `pixcli atlas` 的实现：帧数/矩形越界/矩形重叠/pivot 一致/tags 连续无重叠
+（给源帧时）逐帧逐像素比对 + 采样保真提示（`check_fidelity`，契约 §4.2 判据 4）；
`to_hash()` 是 Web 端 TexturePacker JSON Hash 适配层（契约 §3）；`export_atlas(palette_path=…)`
随资产落调色板 `.gpl`/`.json`（契约 §4.2 判据 5）。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageChops

import palette as palmod

MAX_SIDE = 32767          # 跨浏览器画布单边上限（与 video-studio 导出端一致）
MAX_PIXELS = 178956970    # Pillow DecompressionBomb 硬上限（2 × MAX_IMAGE_PIXELS）


def layout(n, w, h):
    """n 帧 w×h 的网格排布 → (cols, rows)；超单边/总像素上限抛 RuntimeError。"""
    if n <= 0:
        raise ValueError("无帧可排布")
    cols = max(1, MAX_SIDE // max(1, w))
    cols = min(cols, n)
    rows = (n + cols - 1) // cols
    if rows * h > MAX_SIDE:
        raise RuntimeError(
            "帧数过多（{} 帧 {}×{}）：单张 sheet 会超过 {}px 单边上限，"
            "请改用帧序列/ZIP，或缩小画布".format(n, w, h, MAX_SIDE))
    if w * cols * h * rows > MAX_PIXELS:
        raise RuntimeError("sheet 总像素 {} 超过 Pillow 上限，请缩小画布或改用帧序列".format(
            w * cols * h * rows))
    return cols, rows


def build_meta(frames, image_name, fps=12, tag="anim", direction="forward",
               source_route="authored"):
    """帧列表 → (Aseprite JSON Hash dict, cols, rows)。帧尺寸不一致抛 ValueError。

    source_route: `"authored"`（手绘/重绘）| `"sampled"`（采样像素风格，工具从图片/视频生成）
    ——写入 `meta.sourceRoute`，口径见 `agent-pipeline/shared/像素资产约定.md`「资产来源路线」。
    """
    if not frames:
        raise ValueError("无帧可导出")
    w, h = frames[0].size
    for i, f in enumerate(frames):
        if f.size != (w, h):
            raise ValueError("帧尺寸不一致：第 {} 帧为 {}x{}，首帧为 {}x{}（契约 §2 规则 3："
                             "画布组内恒定）".format(i, f.size[0], f.size[1], w, h))
    n = len(frames)
    cols, rows = layout(n, w, h)
    dur = max(1, int(round(1000.0 / fps))) if fps and fps > 0 else 83
    pad = max(2, len(str(n - 1)))
    fr = {}
    for i in range(n):
        key = "{}_{:0{}d}".format(tag, i, pad)
        fr[key] = {
            "frame": {"x": (i % cols) * w, "y": (i // cols) * h, "w": w, "h": h},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h},
            "sourceSize": {"w": w, "h": h},
            "duration": dur,
        }
    return {"frames": fr, "meta": {
        "image": image_name, "format": "RGBA8888",
        "size": {"w": w * cols, "h": h * rows}, "scale": "1",
        "pivot": {"x": w / 2.0, "y": float(h - 1)},
        "sourceRoute": source_route,
        "frameTags": [{"name": tag, "from": 0, "to": n - 1, "direction": direction}],
    }}, cols, rows


def export_atlas(frames, sheet_path, json_path=None, fps=12, tag=None, direction="forward",
                 source_route="authored", palette_path=None):
    """帧序列 → sheet PNG +（可选）Aseprite JSON +（可选）调色板文件。

    palette_path：`.gpl`（GIMP）或其他扩展名（本仓 JSON）——契约 §4.2 判据 5，
    色集取全组不透明像素并集、按 RGB 排序（确定性）。
    返回 (sheet_path, json_path, meta)。
    """
    frames = [f.convert("RGBA") for f in frames]
    tag = tag or os.path.splitext(os.path.basename(sheet_path))[0]
    meta, cols, rows = build_meta(frames, os.path.basename(sheet_path),
                                  fps=fps, tag=tag, direction=direction,
                                  source_route=source_route)
    w, h = frames[0].size
    sheet = Image.new("RGBA", (w * cols, h * rows), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, ((i % cols) * w, (i // cols) * h))
    sheet.save(sheet_path)
    if json_path:
        with open(json_path, "w", encoding="utf-8") as fp:
            json.dump(meta, fp, ensure_ascii=False, indent=2)
    if palette_path:
        colors = set()
        for f in frames:
            colors.update(c for c, _ in palmod.count_colors(f))
        palmod.export_palette(colors, palette_path, name=tag)
    return sheet_path, json_path, meta


def to_hash(meta):
    """Aseprite JSON Hash → TexturePacker JSON Hash（契约 §3 的 Web 适配层，只写一次）。

    帧条目字段同形（`frame/rotated/trimmed/spriteSourceSize/sourceSize/duration`）；
    `meta` 去掉 Aseprite 专属的 `pivot`/`sourceRoute`/`frameTags`，补 `app`/`version`。
    """
    out = {"frames": {}, "meta": {}}
    for k, e in (meta.get("frames") or {}).items():
        entry = {
            "frame": dict(e.get("frame") or {}),
            "rotated": bool(e.get("rotated", False)),
            "trimmed": bool(e.get("trimmed", False)),
            "spriteSourceSize": dict(e.get("spriteSourceSize") or {}),
            "sourceSize": dict(e.get("sourceSize") or {}),
        }
        if isinstance(e.get("duration"), int):
            entry["duration"] = e["duration"]
        out["frames"][k] = entry
    m = meta.get("meta") or {}
    out["meta"] = {
        "app": "pixcli",
        "version": "1.0",
        "image": m.get("image", ""),
        "format": m.get("format", "RGBA8888"),
        "size": dict(m.get("size") or {}),
        "scale": m.get("scale", "1"),
    }
    return out


# ------------------------------------------------------------ 门禁 ----
def _rects(meta):
    """JSON frames → [(key, rect, entry)]，按 sheet 上的位置（y,x）排序 = 帧序。"""
    out = []
    for k, e in (meta.get("frames") or {}).items():
        r = e.get("frame") or {}
        out.append((k, r, e))
    out.sort(key=lambda t: (t[1].get("y", 0), t[1].get("x", 0)))
    return out


def check_fidelity(sheet, max_block=16, min_logical=8):
    """采样保真（契约 §4.2 判据 4）：检测整数倍放大稿 → P2 提示（需显式开启）。

    判据（契约字面口径「以 NEAREST 整数倍放大后仍为纯色块」）：存在 k ∈ 2..max_block 整除画布，
    且每个 k×k 块内颜色（含 alpha）完全一致——即该 sheet 恰为某小图的 k× 最近邻放大。
    取最大的 k；逻辑图任一边 < min_logical 不提示（避免平凡命中）。

    **局限（不可判定）**：特征恰好落在 k 格点上的原生稿，与 k× 放大稿在像素上完全等价，
    无法区分——故本项只作提示、不作门禁，需人工确认（AI 直出放大稿是主要命中来源）。
    """
    px = sheet.load()
    w, h = sheet.size
    best = None
    for k in range(2, max_block + 1):
        if w % k or h % k:
            continue
        uniform = True
        for y in range(0, h, k):
            for x in range(0, w, k):
                c = px[x, y]
                for yy in range(y, y + k):
                    for xx in range(x, x + k):
                        if px[xx, yy] != c:
                            uniform = False
                            break
                    if not uniform:
                        break
                if not uniform:
                    break
            if not uniform:
                break
        if uniform:
            best = k
    if best is None:
        return []
    lw, lh = w // best, h // best
    if lw < min_logical or lh < min_logical:
        return []
    return [("P2", "疑似 {}× 整数倍放大稿（逻辑图 {}×{}；原生尺寸应为 1:1。对齐特征的原生稿"
                   "与之不可分，人工确认）".format(best, lw, lh))]


def check(sheet_path, json_path, frames=None, fidelity=False):
    """sheet ↔ JSON 一致性 → [(sev, msg)]；sev ∈ P0/P1/P2（P0/P1 = 不通过）。

    fidelity=True 时附带判据 4「采样保真」提示（只出 P2，默认关——见 check_fidelity 的不可判定说明）。
    """
    issues = []
    if not os.path.isfile(sheet_path):
        return [("P0", "sheet 不存在: " + sheet_path)]
    sheet = Image.open(sheet_path).convert("RGBA")
    try:
        with open(json_path, encoding="utf-8") as fp:
            meta = json.load(fp)
    except Exception as e:  # noqa: BLE001 —— 门禁要报清原因，不吞异常类型
        return [("P0", "JSON 解析失败: {}".format(e))]
    rects = _rects(meta)
    if not rects:
        return [("P0", "JSON 无 frames 条目")]

    m = meta.get("meta") or {}
    if os.path.basename(m.get("image", "")) != os.path.basename(sheet_path):
        issues.append(("P1", "meta.image（{}）与实际 sheet 文件名（{}）不一致".format(
            m.get("image"), os.path.basename(sheet_path))))
    size = m.get("size") or {}
    if (size.get("w"), size.get("h")) != sheet.size:
        issues.append(("P1", "meta.size {}×{} 与 sheet 实际 {}×{} 不一致".format(
            size.get("w"), size.get("h"), sheet.size[0], sheet.size[1])))
    route = m.get("sourceRoute")
    if route is None:
        issues.append(("P2", "meta.sourceRoute 未标注（按 authored 处理；工具链产物应写 "
                             "authored|sampled，见 像素资产约定.md「资产来源路线」）"))
    elif route not in ("authored", "sampled"):
        issues.append(("P1", "meta.sourceRoute={!r} 非法（只允许 authored | sampled）".format(route)))

    # 矩形：越界 / trim / sourceSize / duration
    sw, sh = sheet.size
    for key, r, e in rects:
        x, y = r.get("x"), r.get("y")
        w, h = r.get("w"), r.get("h")
        if None in (x, y, w, h) or w <= 0 or h <= 0:
            issues.append(("P0", "{}: 矩形字段缺失或非法 {}".format(key, r)))
            continue
        if x < 0 or y < 0 or x + w > sw or y + h > sh:
            issues.append(("P0", "{}: 矩形 {} 越界（sheet {}×{}）".format(key, r, sw, sh)))
        if e.get("trimmed") is not False:
            issues.append(("P0", "{}: trimmed 必须为 false（契约 §2 规则 1）".format(key)))
        ss, src = e.get("spriteSourceSize") or {}, e.get("sourceSize") or {}
        if (ss.get("x"), ss.get("y"), ss.get("w"), ss.get("h")) != (0, 0, w, h):
            issues.append(("P0", "{}: spriteSourceSize {} 必须等于 frame {}".format(key, ss, r)))
        if (src.get("w"), src.get("h")) != (w, h):
            issues.append(("P0", "{}: sourceSize {} 必须等于画布 {}×{}".format(key, src, w, h)))
        if not isinstance(e.get("duration"), int) or e["duration"] <= 0:
            issues.append(("P0", "{}: duration 必须为正整数毫秒，收到 {!r}".format(
                key, e.get("duration"))))

    # 矩形两两不重叠（区间相交判定，O(n²)；n 为帧数）
    for i in range(len(rects)):
        a = rects[i][1]
        for j in range(i + 1, len(rects)):
            b = rects[j][1]
            if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                    and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                issues.append(("P0", "{} 与 {} 矩形重叠".format(rects[i][0], rects[j][0])))

    # pivot：唯一且显式 = 脚底水平中心
    piv = m.get("pivot")
    if not piv:
        issues.append(("P1", "meta.pivot 缺失（契约 §2 规则 2：pivot 必须唯一且显式）"))
    else:
        w0, h0 = rects[0][1].get("w"), rects[0][1].get("h")
        want = (w0 / 2.0, float(h0 - 1))
        got = (piv.get("x"), piv.get("y"))
        if abs((got[0] or 0) - want[0]) > 1e-6 or abs((got[1] or 0) - want[1]) > 1e-6:
            issues.append(("P1", "meta.pivot {} != 脚底水平中心 {}".format(got, want)))

    # tags：越界 / 连续 / 不重叠
    tags = m.get("frameTags") or []
    if not tags:
        issues.append(("P1", "meta.frameTags 缺失（循环语义无处表达）"))
    cover = []
    for t in tags:
        f0, f1 = t.get("from"), t.get("to")
        if not isinstance(f0, int) or not isinstance(f1, int) or f0 > f1:
            issues.append(("P0", "tag {}: from/to 非法 {}/{}".format(t.get("name"), f0, f1)))
            continue
        if f0 < 0 or f1 >= len(rects):
            issues.append(("P0", "tag {}: 帧号 {}~{} 越界（共 {} 帧）".format(
                t.get("name"), f0, f1, len(rects))))
            continue
        cover.extend(range(f0, f1 + 1))
    if cover:
        if sorted(cover) != list(range(len(rects))):
            issues.append(("P1", "frameTags 未连续覆盖 0~{}（有重叠或空洞）".format(len(rects) - 1)))

    # 采样保真（判据 4）：疑似整数倍放大 → P2 提示（不拦交付，默认关）
    if fidelity:
        issues.extend(check_fidelity(sheet))

    # 与源帧逐像素比对（可选）
    if frames:
        srcs = [f.convert("RGBA") for f in frames]
        if len(srcs) != len(rects):
            issues.append(("P0", "帧数不一致：源 {} 帧 vs JSON {} 条".format(len(srcs), len(rects))))
        else:
            for i, (key, r, _e) in enumerate(rects):
                box = (r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])
                if sheet.crop(box).size != srcs[i].size:
                    issues.append(("P0", "{}: 裁出尺寸与源帧不一致".format(key)))
                    continue
                if ImageChops.difference(sheet.crop(box), srcs[i]).getbbox() is not None:
                    issues.append(("P0", "{}: sheet 裁出图与源帧逐像素不一致".format(key)))
    return issues
