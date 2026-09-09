#!/usr/bin/env python3
"""资产清单与审计：扫描资产目录 → manifest.json / manifest.md / 单 HTML 看板 + 全量门禁汇总。

- **清单（manifest）**：只读盘点，不设门禁——每个资产的名称 / 目录 / 类型 / 尺寸 / 帧数 /
  色数 / 来源路线 / sheet+JSON 齐备性，产出 JSON + Markdown（`--html` 另出看板）。
- **审计（audit）**：清单之上跑现有门禁，按 P0/P1/P2 汇总，存在 P0/P1 时 exit 1——
  交付前 / CI 的「全工程一眼看全」入口。

口径复用（不另立判据）：
- 帧组划分与逐帧/帧组判据 = `check`（`group_stem` / `run`：尺寸/alpha/色数/调色板/对齐/动画/孤立像素/连通域）
- sheet ↔ JSON 一致性 = `atlas.check`
- 色数 = 不透明唯一 RGB（alpha=0 不计），与 `palette.count_colors` 同口径
- 来源路线 = sheet JSON 的 `meta.sourceRoute`（authored | sampled，见 像素资产约定.md）

清单输出**不含时间戳**：重跑逐字节一致，可直接进 CI diff。
"""
from __future__ import annotations

import html
import json
import os
import re
from collections import OrderedDict

from PIL import Image

import atlas as atlasmod
import check as checkmod
import palette as palmod

SHEET_STEM_SUFFIX = "_sheet"
# 帧命名约定：<名称>_<两位起帧号>.png（00 起，见 pixel-toolkit/README「约定」）
FRAME_NAME = re.compile(r"^(?P<group>.+)_(?P<no>\d{2,})$")

KIND_LABEL = {"frames": "帧序列", "single": "单图", "sheet": "sheet"}


# ---------- 路径与扫描 ----------
def _rel(path, base):
    """相对 base 的 POSIX 风格路径（Windows 跨盘符时原样返回）。"""
    try:
        rel = os.path.relpath(path, base)
    except ValueError:
        return path.replace(os.sep, "/")
    return rel.replace(os.sep, "/")


def _walk(paths):
    """输入（PNG 文件 / 目录，目录递归）→ (PNG 列表, `*_sheet.json` 列表)，均按路径排序。"""
    pngs, jsons = [], []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs.sort()
                for f in sorted(files):
                    fp = os.path.join(root, f)
                    if f.lower().endswith(".png"):
                        pngs.append(fp)
                    elif f.lower().endswith("_sheet.json"):
                        jsons.append(fp)
        elif p.lower().endswith(".png"):
            pngs.append(p)
        elif p.lower().endswith("_sheet.json"):
            jsons.append(p)
    return pngs, jsons


def _src_for(path_abs, out_dir):
    """看板缩略图地址：优先相对 out_dir，跨盘符（Windows）退回 file:// URI。"""
    try:
        return os.path.relpath(path_abs, out_dir).replace(os.sep, "/")
    except ValueError:
        from pathlib import Path
        return Path(path_abs).as_uri()


def _read_stats(path):
    """单帧统计 → (size, 不透明唯一色集合)。"""
    with Image.open(path) as im:
        im = im.convert("RGBA")
        return im.size, {c for c, _ in palmod.count_colors(im)}


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except Exception:  # noqa: BLE001 —— 元数据只作清单信息，坏 JSON 交给 audit/atlas 报
        return None


def _json_frame_size(path):
    meta = _load_json(path) or {}
    for entry in (meta.get("frames") or {}).values():
        r = entry.get("frame") or {}
        if r.get("w") and r.get("h"):
            return (r["w"], r["h"])
    return None


def _json_route(path):
    meta = _load_json(path) or {}
    return (meta.get("meta") or {}).get("sourceRoute")


def _public(asset):
    """去掉内部字段（下划线开头）后的清单条目。"""
    return {k: v for k, v in asset.items() if not k.startswith("_")}


# ---------- 扫描 → 清单 ----------
def scan(paths, base=None):
    """扫描输入 → 资产记录列表（按目录、名称排序）。

    分组口径与 `check` 一致（帧文件按文件名前缀聚合，`<名称>_sheet.png` / `.json` 挂同组），
    但**分组键含目录**：不同子目录的同名资产各自成条（递归扫描整个 sprites 根时不会并成一条）。
    """
    base = os.path.abspath(base or os.getcwd())
    pngs, jsons = _walk(paths)
    groups = OrderedDict()
    for p in pngs:
        stem = os.path.splitext(os.path.basename(p))[0]
        if stem.endswith(SHEET_STEM_SUFFIX):
            name, is_sheet = stem[:-len(SHEET_STEM_SUFFIX)], True
        else:
            name, is_sheet = checkmod.group_stem(p), False
        key = (os.path.dirname(p), name)
        rec = groups.get(key)
        if rec is None:
            rec = {"name": name, "dir": _rel(os.path.dirname(p), base) or ".", "_frames": [],
                   "_sheet": None, "_json": None}
            groups[key] = rec
        if is_sheet:
            rec["_sheet"] = p
        else:
            rec["_frames"].append(p)
    for j in jsons:
        name = os.path.splitext(os.path.basename(j))[0][:-len(SHEET_STEM_SUFFIX)]
        rec = groups.get((os.path.dirname(j), name))
        if rec is not None and rec["_json"] is None:
            rec["_json"] = j

    assets = []
    for rec in groups.values():
        frames = sorted(rec["_frames"])
        size = colors_max = None
        colors_union = set()
        for fp in frames:
            s, cols = _read_stats(fp)
            size = size or s
            colors_union |= cols
            colors_max = max(colors_max or 0, len(cols))
        if size is None and rec["_json"]:
            size = _json_frame_size(rec["_json"])
        # sheet-only 且无 JSON 时帧尺寸不可知：不拿 sheet 像素尺寸冒充帧尺寸
        n = len(frames)
        thumb = frames[0] if frames else (rec["_sheet"] or "")
        assets.append({
            "name": rec["name"],
            "dir": rec["dir"],
            "kind": "frames" if n > 1 else ("single" if n == 1 else "sheet"),
            "n_frames": n,
            "size": "{}x{}".format(*size) if size else None,
            "colors": colors_max,
            "colors_union": len(colors_union) if colors_union else None,
            "route": _json_route(rec["_json"]) if rec["_json"] else None,
            "sheet": _rel(rec["_sheet"], base) if rec["_sheet"] else None,
            "sheet_json": _rel(rec["_json"], base) if rec["_json"] else None,
            "thumb": _rel(thumb, base) if thumb else None,
            "_frames_abs": frames,
            "_sheet_abs": rec["_sheet"],
            "_json_abs": rec["_json"],
        })
    assets.sort(key=lambda a: (a["dir"], a["name"]))
    return assets


def build(paths, base=None):
    """扫描并组装清单（可直接 json.dump）。"""
    base = os.path.abspath(base or os.getcwd())
    assets = scan(paths, base)
    routes = {}
    for a in assets:
        k = a["route"] or "未标注"
        routes[k] = routes.get(k, 0) + 1
    return {
        "roots": [_rel(os.path.abspath(p), base) for p in paths],
        "summary": {
            "assets": len(assets),
            "frames": sum(a["n_frames"] for a in assets),
            "sheets": sum(1 for a in assets if a["sheet"]),
            "sheet_json": sum(1 for a in assets if a["sheet_json"]),
            "routes": routes,
        },
        "assets": [_public(a) for a in assets],
    }


# ---------- 渲染 ----------
def render_md(manifest):
    """清单 → Markdown 表格（无时间戳，重跑一致）。"""
    s = manifest["summary"]
    route_txt = "、".join("{}×{}".format(k, v) for k, v in sorted(s["routes"].items())) or "-"
    lines = [
        "# 资产清单",
        "",
        "> 由 `pixcli manifest` 生成（无时间戳，重跑逐字节一致）。",
        "> 扫描根：{}".format("、".join("`{}`".format(r) for r in manifest["roots"]) or "-"),
        "",
        "资产 {} 个 / 帧 {} / sheet {}（含 JSON {}）；来源路线 {}".format(
            s["assets"], s["frames"], s["sheets"], s["sheet_json"], route_txt),
        "",
        "| 名称 | 目录 | 类型 | 尺寸 | 帧数 | 色数 | 并集色 | 来源路线 | sheet | JSON |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for a in manifest["assets"]:
        lines.append("| `{}` | `{}` | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            a["name"], a["dir"], KIND_LABEL.get(a["kind"], a["kind"]), a["size"] or "-",
            a["n_frames"] or "-",
            a["colors"] if a["colors"] is not None else "-",
            a["colors_union"] if a["colors_union"] is not None else "-",
            a["route"] or "-",
            "✓" if a["sheet"] else "-", "✓" if a["sheet_json"] else "-"))
    lines.append("")
    return "\n".join(lines)


_HTML_CSS = """\
body{font:13px/1.6 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
     margin:24px;background:#14151c;color:#e6e6ef}
h1{font-size:18px;margin:0 0 4px}
.sum{color:#9a9ab0;margin-bottom:16px}
table{border-collapse:collapse;width:100%}
th,td{padding:6px 10px;border-bottom:1px solid #2a2b38;text-align:left;vertical-align:middle}
th{color:#9a9ab0;font-weight:600;background:#14151c}
td.n{white-space:nowrap}
img{image-rendering:pixelated;max-width:72px;max-height:72px;border-radius:4px;
    background:repeating-conic-gradient(#2a2b38 0 25%,#1b1c26 0 50%) 0 0/12px 12px}
code{color:#c8c8dd}
.ok{color:#7bd88f}.miss{color:#5a5b70}.route{color:#e8c07d}
"""


def render_html(manifest, out_path, base=None):
    """清单 → 单文件 HTML 看板（缩略图按相对路径引用资产，离线可开）。"""
    base = os.path.abspath(base or os.getcwd())
    out_dir = os.path.dirname(os.path.abspath(out_path))
    s = manifest["summary"]
    route_txt = "、".join("{}×{}".format(k, v) for k, v in sorted(s["routes"].items())) or "-"
    rows = []
    for a in manifest["assets"]:
        thumb = ""
        if a["thumb"]:
            src = _src_for(os.path.join(base, a["thumb"]), out_dir)
            thumb = '<img src="{}" alt="">'.format(html.escape(src, quote=True))
        rows.append(
            "<tr><td>{}</td><td class=\"n\"><code>{}</code></td><td class=\"n\"><code>{}</code></td>"
            "<td>{}</td><td class=\"n\">{}</td><td class=\"n\">{}</td><td class=\"n\">{}</td>"
            "<td class=\"route\">{}</td><td class=\"{}\">{}</td><td class=\"{}\">{}</td></tr>".format(
                thumb, html.escape(a["name"]), html.escape(a["dir"]),
                KIND_LABEL.get(a["kind"], a["kind"]), a["size"] or "-",
                a["n_frames"] or "-",
                a["colors"] if a["colors"] is not None else "-",
                html.escape(a["route"] or "-"),
                "ok" if a["sheet"] else "miss", "✓" if a["sheet"] else "—",
                "ok" if a["sheet_json"] else "miss", "✓" if a["sheet_json"] else "—"))
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>资产看板 · {} 资产</title>\n<style>\n{}</style>\n</head>\n<body>\n"
        "<h1>资产看板</h1>\n<div class=\"sum\">扫描根 {} ｜ 资产 {} 个 / 帧 {} / sheet {}"
        "（含 JSON {}）｜ 来源路线 {}</div>\n<table>\n"
        "<tr><th></th><th>名称</th><th>目录</th><th>类型</th><th>尺寸</th><th>帧数</th>"
        "<th>色数</th><th>来源路线</th><th>sheet</th><th>JSON</th></tr>\n{}\n"
        "</table>\n</body>\n</html>\n".format(
            s["assets"], _HTML_CSS,
            html.escape("、".join(manifest["roots"]) or "-"),
            s["assets"], s["frames"], s["sheets"], s["sheet_json"], html.escape(route_txt),
            "\n".join(rows)))


# ---------- 审计 ----------
def audit(assets, expected_size=None, max_colors=16, palette=None, frames=True, anim=True,
          atlas_frames=False, fidelity=False):
    """在清单上跑门禁 → [(asset, [(sev, msg), ...]), ...]（逐资产聚合，资产间不串组）。"""
    out = []
    for a in assets:
        issues = []
        if a["_frames_abs"]:
            for _kind, _ref, iss in checkmod.run(
                    a["_frames_abs"], expected_size, max_colors, palette, frames, anim):
                issues.extend(iss)
        # 帧命名（仅多帧组要求 <名称>_<两位起帧号>.png）
        if len(a["_frames_abs"]) > 1:
            for fp in a["_frames_abs"]:
                stem = os.path.splitext(os.path.basename(fp))[0]
                m = FRAME_NAME.match(stem)
                if not m or m.group("group") != a["name"]:
                    issues.append(("P2", "帧命名不符 `<名称>_<两位起帧号>.png`：{}".format(
                        os.path.basename(fp))))
        # sheet ↔ JSON 齐备性 + 一致性（契约 §1/§4.2）
        if a["_sheet_abs"] and not a["_json_abs"]:
            issues.append(("P1", "有 sheet 缺 `_sheet.json`（交付四件套 §1；`pixcli atlas` 无从校验）"))
        elif a["_json_abs"] and not a["_sheet_abs"]:
            issues.append(("P1", "有 `_sheet.json` 缺对应 sheet"))
        elif a["_sheet_abs"] and a["_json_abs"]:
            src = None
            if atlas_frames and a["_frames_abs"]:
                src = [Image.open(p).convert("RGBA") for p in a["_frames_abs"]]
            issues.extend(atlasmod.check(a["_sheet_abs"], a["_json_abs"], frames=src,
                                         fidelity=fidelity))
        out.append((a, issues))
    return out
