#!/usr/bin/env python3
"""像素美术工具 CLI。子命令：check / anim / sheet / unsheet / gif / html / contact / onion / preview / swatch / from-image / quantize / standardize / diff / video-std / stability / atlas / manifest / audit / scale / run / ops。

用法示例见同目录 README.md；各子命令 -h 查看参数。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anim
import atlas as atlasmod
import check as checkmod
import manifest as manifestmod
import palette as palmod
import pipeline as pipemod
import stability as stabmod
import standardize as stdmod
import video as vidmod
from PIL import Image


def _parse_size(s):
    try:
        w, h = s.lower().split("x")
        return (int(w), int(h))
    except Exception:
        raise argparse.ArgumentTypeError(f"尺寸格式应为 WxH，收到: {s}")


def _collect(inputs):
    files = []
    for p in inputs:
        if os.path.isdir(p):
            files += anim.expand_input(p)
        else:
            files.append(p)
    if not files:
        raise SystemExit("错误：未找到任何 PNG 输入")
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit("错误：文件不存在: " + ", ".join(missing))
    return files


def _load(inputs):
    return anim.load_frames(_collect(inputs))


def _require_inputs(paths):
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        raise SystemExit("错误：路径不存在: " + ", ".join(missing))


def _find_sheet_pairs(paths):
    """输入（文件/目录，目录递归）→ [(sheet.png, json 路径或 None), ...]（按路径排序）。"""
    pairs = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs.sort()
                for f in sorted(files):
                    if f.lower().endswith("_sheet.png"):
                        sp = os.path.join(root, f)
                        jp = os.path.splitext(sp)[0] + ".json"
                        pairs.append((sp, jp if os.path.isfile(jp) else None))
        elif p.lower().endswith("_sheet.png"):
            jp = os.path.splitext(p)[0] + ".json"
            pairs.append((p, jp if os.path.isfile(jp) else None))
    return pairs


# ---------- 子命令 ----------
def cmd_check(args):
    paths = _collect(args.inputs)
    palette = palmod.Palette.load(args.palette) if args.palette else None
    results = checkmod.run(
        paths,
        expected_size=args.size,
        max_colors=args.max_colors,
        palette=palette,
        frames=not args.no_frames,
        anim=not args.no_anim,
        components_max=args.components_max,
    )
    n_sev = {"P0": 0, "P1": 0, "P2": 0}
    for kind, ref, issues in results:
        if kind == "group":
            print("[帧组 {}]".format(ref))
        else:
            bbox = "bbox={}".format(ref["bbox"]) if ref["bbox"] else "空帧"
            print("[图] {:<28} {}x{}  色{:<3} 域{:<2} {}".format(
                ref["name"], ref["size"][0], ref["size"][1], ref["n_colors"],
                ref["n_components"], bbox))
        for sev, msg in issues:
            n_sev[sev] += 1
            print("  {} {}".format(sev, msg))
    total = sum(1 for kind, _, _ in results if kind == "image")
    if args.atlas:
        for sheet, js in _find_sheet_pairs(args.inputs):
            print("[atlas {}]".format(os.path.basename(sheet)))
            if js is None:
                n_sev["P1"] += 1
                print("  P1 缺 {}（sheet 需随附 Aseprite JSON，契约 §1 交付四件套）".format(
                    os.path.splitext(os.path.basename(sheet))[0] + ".json"))
                continue
            for sev, msg in atlasmod.check(sheet, js, fidelity=args.fidelity):
                n_sev[sev] += 1
                print("  {} {}".format(sev, msg))
    if n_sev["P0"] or n_sev["P1"]:
        print("汇总: {} 张，P0×{} P1×{} P2×{} → 不通过".format(
            total, n_sev["P0"], n_sev["P1"], n_sev["P2"]))
        return 1
    print("汇总: {} 张，P0×0 P1×0 P2×{} → 通过".format(total, n_sev["P2"]))
    return 0


def cmd_anim(args):
    paths = _collect(args.inputs)
    infos = [checkmod.analyze(p)[0] for p in paths]
    stats = checkmod.frame_stats(infos)
    if stats is None:
        print("少于 2 帧，无动画统计")
        return 0
    print("[anim] {} 帧  面积(不透明px): {}".format(
        len(stats["names"]), " ".join(str(a) for a in stats["areas"])))
    for pr in stats["pairs"]:
        mark = "  <= {}".format(pr["mark"]) if pr["mark"] else ""
        print("  {} → {}  diff {:.2f}{}".format(pr["a"], pr["b"], pr["ratio"], mark))
    if stats["loop"]:
        lp = stats["loop"]
        mark = "  <= {}".format(lp["mark"]) if lp["mark"] else ""
        print("  {} → {}（循环）  diff {:.2f}{}".format(lp["a"], lp["b"], lp["ratio"], mark))
    return 0


def cmd_onion(args):
    frames = _load(args.inputs)
    anim.onion_sheet(frames, args.out, scale=args.scale, cols=args.cols)
    print("已写出 {}（{} 帧，红=上一帧 蓝=下一帧，首尾回绕）".format(args.out, len(frames)))
    return 0


def cmd_quantize(args):
    files = _collect(args.inputs)
    palette = palmod.Palette.load(args.palette)
    out_is_dir = len(files) > 1 or os.path.isdir(args.out) or args.out.endswith(("/", "\\"))
    if out_is_dir:
        os.makedirs(args.out, exist_ok=True)
    for f in files:
        # 先在源图上做 alpha 两态化，使 --alpha-threshold 真正生效；
        # 否则 quantize 会把所有 a!=0 像素强制成 255，后续两态化成为空操作
        img = palmod.enforce_alpha(Image.open(f).convert("RGBA"), args.alpha_threshold)
        before = len(palmod.count_colors(img))
        out = palmod.quantize(img, palette)
        after = len(palmod.count_colors(out))
        dst = os.path.join(args.out, os.path.basename(f)) if out_is_dir else args.out
        out.save(dst)
        print("{}: {} 色 → 归板后 {} 色 → {}".format(os.path.basename(f), before, after, dst))
    return 0


def cmd_standardize(args):
    """AI 像素图标准化：网格还原 + 单元鲁棒采样 + OKLab 量化（多输入共享网格与色板）。"""
    files = _collect(args.inputs)
    images = [Image.open(f).convert("RGBA") for f in files]
    grid = args.grid if args.grid == "auto" else (
        int(args.grid) if args.grid.isdigit() else args.grid)
    bg = args.bg
    if bg not in ("auto", "keep") and bg.startswith("#"):
        bg = palmod.hex_to_rgb(bg)
    palette = palmod.Palette.load(args.palette) if args.palette else None
    if len(images) > 1:
        outs, rep = stdmod.standardize_frames(
            images, grid=grid, sampling=args.sampling, colors=args.colors,
            palette=palette, bg=bg, bg_tol=args.bg_tol)
        pairs = list(zip(files, outs))
        cell = rep["grid_cell"]
        gtxt = "{}x{}（共享）".format(*cell) if isinstance(cell, tuple) else str(cell)
    else:
        out, rep = stdmod.standardize(
            images[0], grid=grid, sampling=args.sampling, colors=args.colors,
            palette=palette, bg=bg, bg_tol=args.bg_tol)
        pairs = [(files[0], out)]
        outs = [out]
        g = rep["grid"]
        org = g.get("origin") or (0, 0)
        gtxt = "{}x{}".format(*g["cell"])
        if org != (0, 0):
            gtxt += "@{},{}".format(*org)
        gtxt += "（置信度 {}）".format(g["conf"]) if g.get("conf") is not None else "（手动）"
    out_is_dir = len(pairs) > 1 or os.path.isdir(args.out) or args.out.endswith(("/", "\\"))
    if out_is_dir:
        os.makedirs(args.out, exist_ok=True)
    dsts = []
    for f, out in pairs:
        dst = os.path.join(args.out, os.path.splitext(os.path.basename(f))[0] + "_std.png") \
            if out_is_dir else args.out
        out.save(dst)
        dsts.append(dst)
    bgtxt = "背景 {}→透明".format(palmod.rgb_to_hex(rep["bg"])) if rep.get("bg") else "背景保留"
    print("[std] {} 张：网格 {} → {}x{}  {}  色数 {}　量化 {}".format(
        len(files), gtxt, *outs[0].size, bgtxt, rep["colors_out"],
        rep.get("quantize") or "-"))
    for dst in dsts:
        print("  → {}".format(dst))
    return 0


def cmd_video_std(args):
    """AI 像素视频标准化：抽帧 → 裁剪/缩放 → 时间维滤波 → 跨帧共享量化 → 帧/GIF/HTML/sheet。"""
    box = args.box if args.box else None
    rep = vidmod.video_standardize(
        args.video, args.out,
        fps=args.fps, size=args.size, crop=args.crop, box=box,
        bg_tol=args.bg_tol, colors=args.colors, palette=args.palette,
        outline=args.outline, make_gif=not args.no_gif, make_html=not args.no_html,
        keep_frames=not args.no_frames, grid=args.grid, sampling=args.sampling,
        bg=args.bg, key=args.key, fit=args.fit, temporal=args.temporal,
        stabilize=args.stabilize, make_sheet=not args.no_sheet)
    print("[video-std] {} {}x{} {}fps {} → {} 帧 {}（{}）".format(
        os.path.basename(args.video), rep["width"], rep["height"], rep["fps"],
        rep["codec"], rep["frames_used"],
        "裁剪{}".format(rep["crop"]) if rep.get("crop") else "不裁剪",
        "绿幕抠像" if rep.get("key") else "非绿幕"))
    print("  → {}".format(rep["out"]))
    co = rep.get("colors_out") or []
    detail = "{}..{}".format(co[0], co[-1]) if len(co) > 3 else co
    print("  → 量化: {}；输出色数 {}（{} 帧）".format(
        rep.get("quantize") or "-", detail, len(co)))
    if rep.get("temporal"):
        print("  → 时间维滤波: 窗口 {} 帧（共享色板量化之前）".format(rep["temporal"]))
    if rep.get("stabilize"):
        print("  → 时间众数稳定: 窗口 {} 帧（量化后）".format(rep["stabilize"]))
    if rep.get("sheet"):
        print("  → sheet+元数据: {} / {}".format(
            os.path.basename(rep["sheet"]), os.path.basename(rep["atlas"])))
    return 0


def cmd_stability(args):
    """稳定性判据（方案 §1）：静态格/核心静态格帧间变色率 + 单格平均色数；按档位判门禁。"""
    paths = _collect(args.inputs)
    stats = stabmod.analyze_paths(paths)
    max_flip, max_colors = stabmod.preset(args.preset)
    if args.max_flip is not None:
        max_flip = args.max_flip
    if args.max_colors is not None:
        max_colors = args.max_colors
    ok, issues = stabmod.verdict(stats, max_flip, max_colors, args.min_static)
    if args.json:
        print(json.dumps(dict(stats or {}, ok=ok, issues=issues, preset=args.preset,
                              maxFlip=max_flip, maxColors=max_colors), ensure_ascii=False))
    else:
        print("[stability] {} 帧 {}　档位 {}".format(len(paths), paths[0], args.preset))
        print("  " + stabmod.format_stats(stats))
        print("  静态格变色率 {:.1f}% / 核心 {:.1f}%  门禁 ≤{:.1f}%".format(
            stats["flipAll"], stats["flipCore"], max_flip))
        print("  单格平均色数 {:.2f}  门禁 ≤{:.2f}".format(stats["avgColors"], max_colors))
        for msg in issues:
            print("  ✗ " + msg)
        print("  → {}".format("通过" if ok else "不通过"))
    return 0 if ok else 1


def cmd_atlas(args):
    """sheet ↔ Aseprite JSON 门禁（契约 §4.2）；通过后可按 --format hash 转换、--palette-out 落调色板。"""
    frames = None
    if args.frames:
        frames = anim.load_frames(anim.expand_input(args.frames))
    issues = atlasmod.check(args.sheet, args.json, frames=frames,
                            fidelity=args.fidelity)
    n_sev = {"P0": 0, "P1": 0, "P2": 0}
    for sev, msg in issues:
        n_sev[sev] += 1
        print("  {} {}".format(sev, msg))
    ok = not (n_sev["P0"] or n_sev["P1"])
    if ok and args.format == "hash":
        if not args.out:
            print("错误：--format hash 需 -o 指定输出 JSON")
            return 2
        with open(args.json, encoding="utf-8") as fp:
            meta = json.load(fp)
        with open(args.out, "w", encoding="utf-8") as fp:
            json.dump(atlasmod.to_hash(meta), fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        print("  已写 TexturePacker JSON Hash → {}".format(args.out))
    if ok and args.palette_out:
        with Image.open(args.sheet) as im:
            colors = {c for c, _ in palmod.count_colors(im)}
        palmod.export_palette(colors, args.palette_out)
        print("  已写调色板（{} 色）→ {}".format(len(colors), args.palette_out))
    if not ok:
        print("汇总: P0×{} P1×{} P2×{} → 不通过".format(
            n_sev["P0"], n_sev["P1"], n_sev["P2"]))
        return 1
    print("汇总: P0×0 P1×0 P2×{} → 通过（{} ↔ {}）".format(
        n_sev["P2"], os.path.basename(args.sheet), os.path.basename(args.json)))
    return 0


def cmd_manifest(args):
    """资产清单：扫描 → manifest.json + manifest.md（+ --html 看板）；只读盘点，不设门禁。"""
    _require_inputs(args.inputs)
    base = os.getcwd()
    man = manifestmod.build(args.inputs, base=base)
    os.makedirs(args.out, exist_ok=True)
    json_path = os.path.join(args.out, "manifest.json")
    md_path = os.path.join(args.out, "manifest.md")
    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump(man, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
    with open(md_path, "w", encoding="utf-8") as fp:
        fp.write(manifestmod.render_md(man))
    s = man["summary"]
    if not s["assets"]:
        print("警告：未找到任何 PNG 资产（检查路径是否指对）")
    print("[manifest] 资产 {}（帧 {} / sheet {}，含 JSON {}）".format(
        s["assets"], s["frames"], s["sheets"], s["sheet_json"]))
    print("           清单 → {}".format(json_path))
    print("           表格 → {}".format(md_path))
    if args.html:
        html_dir = os.path.dirname(os.path.abspath(args.html))
        os.makedirs(html_dir, exist_ok=True)
        with open(args.html, "w", encoding="utf-8") as fp:
            fp.write(manifestmod.render_html(man, args.html, base=base))
        print("           看板 → {}".format(args.html))
    return 0


def cmd_audit(args):
    """全量审计：清单 + check 逐帧/帧组 + atlas 一致性 + sheet/JSON 齐备，P0/P1 存在 exit 1。"""
    _require_inputs(args.inputs)
    base = os.getcwd()
    assets = manifestmod.scan(args.inputs, base=base)
    if not assets:
        print("错误：未找到任何 PNG 资产（检查路径是否指对）")
        return 1
    palette = palmod.Palette.load(args.palette) if args.palette else None
    results = manifestmod.audit(
        assets, expected_size=args.size, max_colors=args.max_colors, palette=palette,
        frames=not args.no_frames, anim=not args.no_anim, atlas_frames=args.atlas_frames,
        fidelity=args.fidelity)
    n_sev = {"P0": 0, "P1": 0, "P2": 0}
    for a, issues in results:
        print("[资产] {:<28} {:<7} {:>3}帧  色{:<3} {}{}".format(
            a["name"], a["size"] or "-", a["n_frames"],
            a["colors"] if a["colors"] is not None else "-", a["route"] or "-",
            "  sheet" if a["sheet"] else ""))
        for sev, msg in issues:
            n_sev[sev] += 1
            print("  {} {}".format(sev, msg))
    tail = "资产 {}（帧 {} / sheet {}），P0×{} P1×{} P2×{}".format(
        len(results), sum(a["n_frames"] for a, _ in results),
        sum(1 for a, _ in results if a["sheet"]),
        n_sev["P0"], n_sev["P1"], n_sev["P2"])
    if n_sev["P0"] or n_sev["P1"]:
        print("汇总: {} → 不通过".format(tail))
        return 1
    print("汇总: {} → 通过".format(tail))
    return 0


def _pixel_diff(pa, pb):
    """逐像素比对两张 PNG（RGBA）。返回 (diffs, note)：diffs=None 表示尺寸不同。"""
    a = Image.open(pa).convert("RGBA")
    b = Image.open(pb).convert("RGBA")
    if a.size != b.size:
        return None, "尺寸 {}x{} != {}x{}".format(a.size[0], a.size[1], b.size[0], b.size[1])
    ap, bp = a.load(), b.load()
    w, h = a.size
    diffs = [(x, y) for y in range(h) for x in range(w) if ap[x, y] != bp[x, y]]
    return diffs, ""


def _print_diff(diffs, note):
    if diffs is None:
        print("  {}".format(note))
        return
    if not diffs:
        print("  一致")
        return
    xs = [p[0] for p in diffs]
    ys = [p[1] for p in diffs]
    print("  差异 {} px，bbox=({},{})..({},{})，首几处: {}".format(
        len(diffs), min(xs), min(ys), max(xs), max(ys), diffs[:6]))


def cmd_diff(args):
    a, b = args.a, args.b
    if os.path.isdir(a) and os.path.isdir(b):
        names_a = {f for f in os.listdir(a) if f.lower().endswith(".png")}
        names_b = {f for f in os.listdir(b) if f.lower().endswith(".png")}
        n_same = n_diff = 0
        for f in sorted(names_a & names_b):
            diffs, note = _pixel_diff(os.path.join(a, f), os.path.join(b, f))
            if diffs:
                n_diff += 1
                print("DIFF {}".format(f))
                _print_diff(diffs, note)
            else:
                n_same += 1
        rc = 0
        for f in sorted(names_a - names_b):
            print("仅在 {}: {}".format(a, f))
            rc = 1
        for f in sorted(names_b - names_a):
            print("仅在 {}: {}".format(b, f))
            rc = 1
        print("目录比对：共有 {}（一致 {}，差异 {}），仅单侧 {}".format(
            len(names_a & names_b), n_same, n_diff, len(names_a ^ names_b)))
        return 1 if (rc or n_diff) else 0
    if os.path.isdir(a) or os.path.isdir(b):
        raise SystemExit("错误：目录比对要求两个参数都是目录")
    diffs, note = _pixel_diff(a, b)
    if diffs is None:
        print("{} vs {}：{}".format(a, b, note))
        return 1
    if not diffs:
        print("{} vs {}：像素级一致".format(a, b))
        return 0
    print("{} vs {}：".format(a, b))
    _print_diff(diffs, note)
    return 1


def cmd_sheet(args):
    frames = _load(args.inputs)
    sheet = anim.build_sheet(frames, horizontal=not args.vertical)
    sheet.save(args.out)
    print("已写出 {}（{} 帧，帧尺寸 {}x{}）".format(args.out, len(frames), *frames[0].size))
    return 0


def cmd_unsheet(args):
    sheet = Image.open(args.sheet)
    frames = anim.slice_sheet(sheet, args.size[0], args.size[1], horizontal=not args.vertical)
    os.makedirs(args.out, exist_ok=True)
    prefix = args.prefix or "frame"
    for i, f in enumerate(frames):
        f.save(os.path.join(args.out, "{}_{:02d}.png".format(prefix, i)))
    print("已切出 {} 帧到 {}（前缀 {}）".format(len(frames), args.out, prefix))
    return 0


def cmd_gif(args):
    frames = _load(args.inputs)
    anim.export_gif(frames, args.out, fps=args.fps, pingpong=args.pingpong)
    print("已写出 {}（{} 帧，{} fps{}）".format(
        args.out, len(frames), args.fps, "，往复" if args.pingpong else ""))
    return 0


def cmd_html(args):
    frames = _load(args.inputs)
    anim.export_html(frames, args.out, title=args.title, fps=args.fps, zoom=args.zoom)
    print("已写出 {}".format(args.out))
    return 0


def cmd_contact(args):
    frames = _load(args.inputs)
    anim.contact_sheet(frames, args.out, scale=args.scale, cols=args.cols, grid=args.grid)
    print("已写出 {}".format(args.out))
    return 0


def cmd_preview(args):
    frames = _load(args.inputs)
    os.makedirs(args.out, exist_ok=True)
    stem = os.path.join(args.out, args.name)
    gif_path = stem + ".gif"
    html_path = stem + ".html"
    contact_path = stem + "_contact.png"
    anim.export_gif(frames, gif_path, fps=args.fps, pingpong=args.pingpong)
    anim.export_html(frames, html_path, title="{}（{} 帧 / {} fps）".format(
        args.name, len(frames), args.fps), fps=args.fps, zoom=args.zoom)
    anim.contact_sheet(frames, contact_path, scale=args.zoom, cols=args.cols)
    print("预览三件套 →\n  {}\n  {}\n  {}".format(gif_path, html_path, contact_path))
    return 0


def cmd_swatch(args):
    p = palmod.Palette.load(args.palette)
    anim_out = args.out or (os.path.splitext(args.palette)[0] + "_swatch.png")
    palmod.export_swatch(p.colors, anim_out, roles=p.roles)
    print("已写出 {}（{} 色）".format(anim_out, len(p.colors)))
    return 0


def cmd_from_image(args):
    img = Image.open(args.image).convert("RGBA")
    colors = palmod.palette_from_image(img, max_colors=args.max_colors)
    p = palmod.Palette(name=args.name or os.path.splitext(os.path.basename(args.image))[0],
                       colors=colors)
    p.save(args.out)
    print("已写出 {}（提取 {} 色）".format(args.out, len(colors)))
    return 0


def cmd_scale(args):
    img = Image.open(args.image).convert("RGBA")
    anim.scale_nearest(img, args.factor).save(args.out)
    print("已写出 {}（{}x → {}x{}）".format(
        args.out, args.factor, img.size[0] * args.factor, img.size[1] * args.factor))
    return 0


def cmd_run(args):
    """执行管线配方 JSON（节点系统 Phase 0）：线性 stage 列表，确定性执行，门禁内联拦截。"""
    try:
        graph, sha = pipemod.load_graph(args.graph)
        if args.out:
            graph.setdefault("output", {})["dir"] = args.out
        report = pipemod.run(graph, dry_run=args.dry_run, log=print)
    except pipemod.PipelineError as e:
        print("错误：{}".format(e))
        return 2
    return 0 if report["ok"] else 1


def cmd_ops(args):
    """列出管线可用节点与参数（节点工作台 / Agent 自省入口）。"""
    cats = {"source": "源", "transform": "变换", "export": "导出", "gate": "门禁"}
    if args.json:
        out = {"version": pipemod.SCHEMA_VERSION,
               "ops": [{k: v for k, v in d.items() if k != "fn"}
                       for d in pipemod.OPS.values()]}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    print("[pipeline] 可用节点 {} 个（配方 version {}，pixcli run 执行）".format(
        len(pipemod.OPS), pipemod.SCHEMA_VERSION))
    for cat in ("source", "transform", "export", "gate"):
        group = [d for d in pipemod.OPS.values() if d["category"] == cat]
        if not group:
            continue
        print("\n{}（{}）".format(cats[cat], len(group)))
        for d in group:
            print("  {:<18} {}".format(d["name"], d["title"]))
            for prm in d["params"]:
                mark = "*" if prm["required"] else " "
                default = "" if prm["default"] is None \
                    else "（默认 {}）".format(prm["default"])
                print("    {} {:<14} {:<8} {}{}".format(
                    mark, prm["key"], prm["type"].split(":")[0], prm["help"], default))
    print("\n标注：* = 必填；配方结构与示例见 pipeline.py 模块注释与 examples/*.pipeline.json")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pixcli", description="像素美术创作工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="程序化自检（尺寸/模式/alpha 两态/色数/调色板/帧对齐/动画一致性/孤立像素/连通域；帧组按前缀自动聚合）")
    p.add_argument("inputs", nargs="+", help="PNG 文件或目录（可混多资产，帧组按文件名前缀自动分组）")
    p.add_argument("--size", type=_parse_size, help="期望尺寸 WxH")
    p.add_argument("--max-colors", type=int, default=16)
    p.add_argument("--palette", help="调色板 JSON，校验颜色是否都在板内")
    p.add_argument("--components-max", type=int, default=None,
                   help="连通域上限（不透明 4 连通域数 > N 报 P1）；碎影/群落类资产按需设置")
    p.add_argument("--no-frames", action="store_true", help="关闭帧组对齐检查")
    p.add_argument("--no-anim", action="store_true", help="关闭动画一致性检查（死帧/跳变/循环突断）")
    p.add_argument("--atlas", action="store_true",
                   help="附加 sheet↔JSON 一致性检查（目录内 *_sheet.png 自动配对，缺 JSON 记 P1）")
    p.add_argument("--fidelity", action="store_true", help="附带采样保真提示（判据 4：疑似整数倍放大稿，只出 P2）")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("anim", help="帧组动画统计（相邻/循环 diff 率、面积序列；信息用，不设门禁）")
    p.add_argument("inputs", nargs="+")
    p.set_defaults(fn=cmd_anim)

    p = sub.add_parser("onion", help="洋葱皮静态检查图（红=上一帧 蓝=下一帧，首尾回绕）")
    p.add_argument("inputs", nargs="+")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--scale", type=int, default=6)
    p.add_argument("--cols", type=int, default=None)
    p.set_defaults(fn=cmd_onion)

    p = sub.add_parser("sheet", help="帧 → 横向/纵向 sprite sheet")
    p.add_argument("inputs", nargs="+")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--vertical", action="store_true")
    p.set_defaults(fn=cmd_sheet)

    p = sub.add_parser("unsheet", help="sprite sheet → 帧序列")
    p.add_argument("sheet")
    p.add_argument("--size", type=_parse_size, required=True, help="单帧尺寸 WxH")
    p.add_argument("-o", "--out", required=True, help="输出目录")
    p.add_argument("--prefix", help="输出文件名前缀（默认 frame）")
    p.add_argument("--vertical", action="store_true")
    p.set_defaults(fn=cmd_unsheet)

    p = sub.add_parser("gif", help="帧 → 循环 GIF")
    p.add_argument("inputs", nargs="+")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--fps", type=int, default=10)
    p.add_argument("--pingpong", action="store_true", help="往复播放（0..n-1..0）")
    p.set_defaults(fn=cmd_gif)

    p = sub.add_parser("html", help="帧 → 自包含 HTML 播放器")
    p.add_argument("inputs", nargs="+")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--fps", type=int, default=10)
    p.add_argument("--zoom", type=int, default=6)
    p.add_argument("--title", default="Pixel Animation")
    p.set_defaults(fn=cmd_html)

    p = sub.add_parser("contact", help="帧 → 放大逐帧检查图（--grid 叠像素网格与坐标刻度）")
    p.add_argument("inputs", nargs="+")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--scale", type=int, default=6)
    p.add_argument("--cols", type=int, default=None)
    p.add_argument("--grid", action="store_true", help="叠 1px 像素网格，每 8px 亮线并标坐标（scale≥4）")
    p.set_defaults(fn=cmd_contact)

    p = sub.add_parser("preview", help="一键预览：GIF + HTML 播放器 + 放大检查图")
    p.add_argument("inputs", nargs="+")
    p.add_argument("--out", required=True, help="输出目录（建议 previews/）")
    p.add_argument("--name", required=True, help="输出文件名主干")
    p.add_argument("--fps", type=int, default=10)
    p.add_argument("--zoom", type=int, default=6)
    p.add_argument("--cols", type=int, default=None)
    p.add_argument("--pingpong", action="store_true")
    p.set_defaults(fn=cmd_preview)

    p = sub.add_parser("swatch", help="调色板 JSON → 色条 PNG")
    p.add_argument("palette")
    p.add_argument("-o", "--out", default=None)
    p.set_defaults(fn=cmd_swatch)

    p = sub.add_parser("from-image", help="图像 → 调色板 JSON（按频次取色）")
    p.add_argument("image")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--max-colors", type=int, default=16)
    p.add_argument("--name", default=None)
    p.set_defaults(fn=cmd_from_image)

    p = sub.add_parser("quantize", help="图像归入调色板 + alpha 两态化（结构性保色，导入/模仿路径用；OKLab 感知色距最近色）")
    p.add_argument("inputs", nargs="+")
    p.add_argument("--palette", required=True, help="调色板 JSON")
    p.add_argument("-o", "--out", required=True, help="输出文件（单输入）或目录（多输入）")
    p.add_argument("--alpha-threshold", type=int, default=128)
    p.set_defaults(fn=cmd_quantize)

    p = sub.add_parser("standardize",
                       help="AI 像素图标准化：网格还原 + 单元鲁棒采样（众数/中位数）+ OKLab 量化；多输入自动共享网格与色板（防闪烁）")
    p.add_argument("inputs", nargs="+", help="JPEG/PNG 等源图（AI 生成或放大图）；多输入视为动画帧")
    p.add_argument("-o", "--out", required=True, help="输出文件（单输入）或目录（多输入，命名 <原名>_std.png）")
    p.add_argument("--grid", default="auto",
                   help="每格源像素数：auto（梯度峰距自动检测）| N（方格）| WxH；检测置信度不足时报错提示手动指定")
    p.add_argument("--sampling", choices=("mode", "median"), default="mode",
                   help="单元采样：mode=格内众数（默认，JPEG 噪声吸收）| median=逐通道中位数")
    p.add_argument("--colors", type=int, default=16,
                   help="目标色数（OKLab 加权 k-means，确定性）；0 = 不量化")
    p.add_argument("--palette", help="映射到工程调色板 JSON（优先于 --colors）")
    p.add_argument("--bg", default="auto", help="背景：auto（四角一致色判定）| keep | #rrggbb")
    p.add_argument("--bg-tol", type=int, default=16, help="背景判定 RGB 距离容差")
    p.set_defaults(fn=cmd_standardize)

    p = sub.add_parser("diff", help="像素级比对（一致 exit 0）：文件↔文件 或 目录↔目录（重构/改参零差异验证）")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(fn=cmd_diff)

    p = sub.add_parser("video-std",
                       help="AI 像素视频标准化：ffmpeg 抽帧 → 角色区裁剪 → 像素化降采样 → 跨帧共享 OKLab 量化 → 帧序列+GIF+HTML 播放器（AI 动态视频无稳定网格，默认走降采样而非网格还原）")
    p.add_argument("video", help="输入视频（mp4/webm/mov；需要 ffmpeg）")
    p.add_argument("-o", "--out", required=True, help="输出目录（帧序列 <名>_NN.png + <名>.gif + <名>.html）")
    p.add_argument("--fps", type=float, default=None, help="重采样帧率（默认视频原生；如 24 源 → 12 减半）")
    p.add_argument("--size", type=_parse_size, default=None, help="目标像素尺寸 WxH（如 64x64；默认不缩放仅量化）")
    p.add_argument("--fit", choices=("contain", "stretch"), default="contain",
                   help="缩放到 --size 的方式：contain=等比适配居中留边（默认，不变形）| stretch=直接拉伸（可能变扁/变瘦）")
    p.add_argument("--crop", choices=("auto", "none", "fixed"), default="auto",
                   help="auto=全程合并内容 bbox 裁剪（默认）| none=不裁剪 | fixed=用 --box")
    p.add_argument("--box", default=None, help="固定裁剪框 x0,y0,x1,y1（配合 --crop fixed）")
    p.add_argument("--bg-tol", type=int, default=60, help="背景判定亮度差阈值")
    p.add_argument("--bg", default="auto", help="背景透明化：auto（四角众数判定，默认）| keep（不透明化）| #rrggbb")
    p.add_argument("--key", choices=("auto", "green", "none"), default="auto",
                   help="绿幕抠像：auto（四角检测到绿幕则抠像）| green（强制）| none（不用）；色度判定不受灰衣影响")
    p.add_argument("--colors", type=int, default=16, help="目标色数（跨帧合并聚类）；0=不量化")
    p.add_argument("--palette", help="映射到工程调色板 JSON（优先于 --colors）")
    p.add_argument("--grid", default=None, help="指定逻辑网格 N（仅当视频确为网格放大时；默认 None=像素化降采样）")
    p.add_argument("--sampling", choices=("mode", "median"), default="mode",
                   help="网格采样方式（--grid 时生效）")
    p.add_argument("--outline", default=None, help="1px 内描边色 #rrggbb（可选，逐帧描边）")
    p.add_argument("--no-gif", action="store_true", help="不导出 GIF")
    p.add_argument("--no-html", action="store_true", help="不导出 HTML 播放器")
    p.add_argument("--no-frames", action="store_true", help="不导出帧序列 PNG（仅 GIF/HTML）")
    p.add_argument("--temporal", type=int, default=0,
                   help="时间维滤波窗口帧数（奇数；0=关，**默认 0**）：量化前逐像素沿时间轴取中值，"
                        "运动感知（与相邻帧同态就保留）——拖影仍比众数明显，一般用 --stabilize 代替")
    p.add_argument("--stabilize", type=int, default=3,
                   help="时间众数稳定窗口帧数（0=关，**默认 3**）：量化后逐像素取窗口众数、平局保留当前帧，"
                        "只替换少数派 → 闪烁抑制与低拖影兼得（与 video-studio「后处理·时间稳定」同口径）")
    p.add_argument("--no-sheet", action="store_true",
                   help="不导出 <名>_sheet.png + <名>_sheet.json（Aseprite JSON Hash）")
    p.set_defaults(fn=cmd_video_std)

    p = sub.add_parser("stability",
                       help="稳定性门禁（方案 §1）：静态格/核心静态格帧间变色率 + 单格平均色数；"
                            "超标或样本不足 exit 1（可接 CI）")
    p.add_argument("inputs", nargs="+", help="帧 PNG 文件或目录（按文件名排序即时间序）")
    p.add_argument("--preset", choices=sorted(stabmod.PRESETS), default="strict",
                   help="阈值档位：strict=§1 门禁 5%%/3.0（默认）| standard=验收档 10%%/3.5 | "
                        "quick=回归探测档 15%%/4.0；显式 --max-flip/--max-colors 覆盖档位")
    p.add_argument("--max-flip", type=float, default=None,
                   help="核心静态格变色率上限 %%（不给则用档位值）")
    p.add_argument("--max-colors", type=float, default=None,
                   help="单格平均色数上限（不给则用档位值）")
    p.add_argument("--min-static", type=int, default=stabmod.STATIC_MIN,
                   help="静态格下限，低于此数报样本不足（默认 %(default)s）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出指标（供脚本比对）")
    p.set_defaults(fn=cmd_stability)

    p = sub.add_parser("atlas",
                       help="sprite sheet ↔ Aseprite JSON 一致性门禁（契约 §4.2）：帧数/矩形越界/"
                            "矩形重叠/trim/pivot/tags 连续（+ --frames 时逐帧逐像素比对）")
    p.add_argument("sheet", help="sprite sheet PNG")
    p.add_argument("json", help="Aseprite JSON（Hash 变体）")
    p.add_argument("--frames", help="源帧目录或文件（给了就做 sheet 裁出图与源帧的逐像素比对）")
    p.add_argument("--format", choices=["hash"],
                   help="通过后另存转换格式：hash = TexturePacker JSON Hash（Web 适配层，契约 §3）")
    p.add_argument("-o", "--out", help="--format hash 的输出 JSON 路径")
    p.add_argument("--palette-out",
                   help="通过后落调色板文件（.gpl = GIMP；其他扩展名 = 本仓 JSON；契约 §4.2 判据 5）")
    p.add_argument("--fidelity", action="store_true", help="附带采样保真提示（判据 4：疑似整数倍放大稿，只出 P2）")
    p.set_defaults(fn=cmd_atlas)

    p = sub.add_parser("manifest",
                       help="资产清单：扫描文件/目录（递归）→ manifest.json + manifest.md，"
                            "--html 出单文件看板；只读盘点不设门禁")
    p.add_argument("inputs", nargs="+", help="PNG 文件或目录（目录递归扫描）")
    p.add_argument("-o", "--out", default=".", help="输出目录（manifest.json / manifest.md，默认当前目录）")
    p.add_argument("--html", help="另出单文件 HTML 看板（相对路径引用资产，离线可开）")
    p.set_defaults(fn=cmd_manifest)

    p = sub.add_parser("audit",
                       help="全量审计：清单 + check 逐帧/帧组 + atlas 一致性 + sheet/JSON 齐备，"
                            "P0/P1 存在 exit 1（交付前/CI 的全工程入口）")
    p.add_argument("inputs", nargs="+", help="PNG 文件或目录（目录递归扫描）")
    p.add_argument("--size", type=_parse_size, help="期望帧尺寸 WxH")
    p.add_argument("--max-colors", type=int, default=16)
    p.add_argument("--palette", help="调色板 JSON，校验颜色是否都在板内")
    p.add_argument("--no-frames", action="store_true", help="关闭帧组对齐检查")
    p.add_argument("--no-anim", action="store_true", help="关闭动画一致性检查")
    p.add_argument("--atlas-frames", action="store_true",
                   help="atlas 校验时逐帧逐像素比对（慢；默认只查元数据）")
    p.add_argument("--fidelity", action="store_true", help="附带采样保真提示（判据 4：疑似整数倍放大稿，只出 P2）")
    p.set_defaults(fn=cmd_audit)

    p = sub.add_parser("scale", help="nearest 整数倍放大（预览用）")
    p.add_argument("image")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--factor", type=int, default=8)
    p.set_defaults(fn=cmd_scale)

    p = sub.add_parser("run",
                       help="执行管线配方 JSON（节点系统 Phase 0）：源→变换→导出→门禁，"
                            "确定性执行（同输入同参数逐字节一致），门禁不通过 exit 1")
    p.add_argument("graph", help="管线配方 JSON 路径（结构见 pipeline.py 模块注释 / examples/）")
    p.add_argument("-o", "--out", help="覆盖配方的 output.dir")
    p.add_argument("--dry-run", action="store_true",
                   help="只校验配方与打印执行计划，不读源、不写文件")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("ops", help="列出管线可用节点与参数（--json 供节点工作台/Agent 读取）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出节点注册表")
    p.set_defaults(fn=cmd_ops)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
