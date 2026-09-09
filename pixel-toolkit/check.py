"""程序化自检：尺寸 / 模式 / alpha 两态 / 色数 / 调色板 / 帧组锚点对齐 / 动画一致性 / 孤立像素 / 连通域。

返回结构化 issue 列表，级别 P0（必须修）/ P1（应修）/ P2（建议）；
与 pixel-reviewer 的分级口径一致，供交付前快速把关。
"""
from __future__ import annotations

import os
import re
import statistics
from collections import Counter

from PIL import Image

from palette import rgb_to_hex

NEIGH4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

# 帧组识别：stem 末尾的 _NN（两位帧号）剥离后即组键，如 hero_idle_03 → hero_idle
FRAME_NO = re.compile(r"_(\d+)$")

# 动画一致性阈值（帧间像素 diff 率 = 变化像素 / 不透明并集）
ANIM_JUMP_RATIO = 0.85   # 单对 diff 率超过此值才可能算跳变
ANIM_JUMP_FACTOR = 1.8   # 且需超过其余相邻对中位数的该倍数
ANIM_LOOP_FACTOR = 1.5   # 循环闭合 diff 超过最大相邻 diff 的该倍数
ANIM_LOOP_MARGIN = 0.10


def _component_sizes(opaque):
    """不透明像素 4 连通域面积序列（由大到小）。供主体/碎影拓扑判读（U8 沉淀方法）。"""
    seen = set()
    sizes = []
    for start in opaque:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        n = 0
        while stack:
            x, y = stack.pop()
            n += 1
            for dx, dy in NEIGH4:
                nb = (x + dx, y + dy)
                if nb in opaque and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        sizes.append(n)
    return sorted(sizes, reverse=True)


def analyze(path, expected_size=None, max_colors=16, palette=None, components_max=None):
    """单图检查。返回 (info dict, issues list)，issue = (级别, 消息)。"""
    issues = []
    img = Image.open(path)
    mode = img.mode
    if mode != "RGBA":
        issues.append(("P1", f"色彩模式 {mode} != RGBA"))
    img = img.convert("RGBA")
    w, h = img.size
    if expected_size and (w, h) != tuple(expected_size):
        issues.append(("P0", f"尺寸 {w}x{h} != 期望 {expected_size[0]}x{expected_size[1]}"))

    alphas = set()
    colors = Counter()
    opaque = set()
    px = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            alphas.add(a)
            if a:
                colors[(r, g, b)] += 1
                opaque.add((x, y))

    bad_alpha = sorted(a for a in alphas if a not in (0, 255))
    if bad_alpha:
        issues.append(("P0", f"alpha 存在中间值 {bad_alpha[:6]}（要求两态 0/255）"))
    if len(colors) > max_colors:
        issues.append(("P1", f"唯一色 {len(colors)} > 上限 {max_colors}"))
    if palette is not None:
        allowed = set(palette.colors)
        off = [c for c in colors if c not in allowed]
        if off:
            issues.append((
                "P1",
                f"调色板外颜色 {len(off)} 种: " + ", ".join(rgb_to_hex(c) for c in off[:8]),
            ))

    if opaque:
        xs = [p[0] for p in opaque]
        ys = [p[1] for p in opaque]
        bbox = (min(xs), min(ys), max(xs), max(ys))
    else:
        issues.append(("P1", "整图为透明空帧"))
        bbox = None

    strays = []
    for (x, y) in sorted(opaque):
        if all((x + dx, y + dy) not in opaque for dx, dy in NEIGH4):
            strays.append((x, y))
            if len(strays) >= 8:
                break
    if strays:
        issues.append(("P2", f"孤立像素（4 邻域无相邻不透明像素）{len(strays)} 处起: {strays[:6]}"))

    comp_sizes = _component_sizes(opaque) if opaque else []
    if components_max is not None and len(comp_sizes) > components_max:
        issues.append((
            "P1",
            f"连通域 {len(comp_sizes)} > 上限 {components_max}（面积序列 {comp_sizes[:8]}；"
            "碎影/群落类资产按需用 --components-max，误粘连带会减少域数）",
        ))

    info = {
        "path": path,
        "name": os.path.basename(path),
        "size": (w, h),
        "mode": mode,
        "colors": colors,
        "n_colors": len(colors),
        "n_opaque": sum(colors.values()),
        "bbox": bbox,
        "components": comp_sizes,
        "n_components": len(comp_sizes),
        "img": img,
    }
    return info, issues


def _pair_diff(a, b):
    """相邻帧像素 diff 率：变化像素 / 不透明并集（alpha 或颜色任一变化即算变化）。"""
    w, h = a.size
    pa, pb = a.load(), b.load()
    union = changed = 0
    for y in range(h):
        for x in range(w):
            qa, qb = pa[x, y], pb[x, y]
            if qa[3] or qb[3]:
                union += 1
                if qa != qb:
                    changed += 1
    return changed / union if union else 0.0


def frame_dynamics(infos):
    """帧组动画一致性：死帧（相邻帧像素全同）P1；异常跳变、循环首尾突断 P2。

    尺寸不一致时直接跳过（frame_alignment 已报 P0）；diff 率阈值见模块头 ANIM_*。
    """
    issues = []
    imgs = [i["img"] for i in infos]
    names = [i["name"] for i in infos]
    n = len(imgs)
    if n < 2:
        return issues
    ratios = []
    for i in range(n - 1):
        if imgs[i].size != imgs[i + 1].size:
            return issues
        r = _pair_diff(imgs[i], imgs[i + 1])
        ratios.append(r)
        if r == 0.0:
            issues.append(("P1", f"死帧：{names[i]} 与 {names[i + 1]} 像素完全相同（动画未动或重复导出）"))
    nz = [r for r in ratios if r > 0]
    if len(nz) >= 2:
        med = statistics.median(nz)
        for i, r in enumerate(ratios):
            if r > ANIM_JUMP_RATIO and r > ANIM_JUMP_FACTOR * med:
                issues.append(("P2", f"帧间跳变：{names[i]} → {names[i + 1]} diff 率 {r:.2f}"
                                      f"（其余对中位数 {med:.2f}）"))
    if n > 2 and nz:
        loop = _pair_diff(imgs[-1], imgs[0])
        mx = max(nz)
        if loop > ANIM_LOOP_FACTOR * mx + ANIM_LOOP_MARGIN:
            issues.append(("P2", f"循环首尾突断：{names[-1]} → {names[0]} diff 率 {loop:.2f}"
                                      f"（最大相邻 {mx:.2f}）"))
    return issues


def frame_stats(infos):
    """帧组动画统计（供 `pixcli anim` 展示，不设门禁）：面积序列、相邻 diff 率、循环闭合。

    返回 dict（names/areas/pairs/loop），pair/loop 附 mark 标记（死帧/跳变?/循环突断?）；少于 2 帧返回 None。
    """
    n = len(infos)
    if n < 2:
        return None
    imgs = [i["img"] for i in infos]
    names = [i["name"] for i in infos]
    areas = [i["n_opaque"] for i in infos]
    pairs = []
    for i in range(n - 1):
        if imgs[i].size != imgs[i + 1].size:
            break
        r = _pair_diff(imgs[i], imgs[i + 1])
        mark = "死帧" if r == 0.0 else ""
        pairs.append({"a": names[i], "b": names[i + 1], "ratio": r, "mark": mark})
    nz = [p["ratio"] for p in pairs if p["ratio"] > 0]
    if len(nz) >= 2:
        med = statistics.median(nz)
        for p in pairs:
            if p["ratio"] > ANIM_JUMP_RATIO and p["ratio"] > ANIM_JUMP_FACTOR * med and not p["mark"]:
                p["mark"] = "跳变?"
    loop = None
    if n > 2 and len(pairs) == n - 1 and nz:
        loop = {"a": names[-1], "b": names[0],
                "ratio": _pair_diff(imgs[-1], imgs[0]),
                "mark": ""}
        if loop["ratio"] > ANIM_LOOP_FACTOR * max(nz) + ANIM_LOOP_MARGIN:
            loop["mark"] = "循环突断?"
    return {"names": names, "areas": areas, "pairs": pairs, "loop": loop}


def frame_alignment(infos, center_tol=1):
    """帧组一致性：帧尺寸一致、脚底（bbox bottom）对齐、水平中心漂移 ≤ tol。"""
    issues = []
    if len(infos) < 2:
        return issues
    sizes = {tuple(i["size"]) for i in infos}
    if len(sizes) > 1:
        issues.append(("P0", f"帧尺寸不一致: {sorted(sizes)}"))
    boxes = [(i["name"], i["bbox"]) for i in infos if i["bbox"]]
    if len(boxes) < 2:
        return issues
    bottoms = {b[3] for _, b in boxes}
    if len(bottoms) > 1:
        issues.append(("P1", f"脚底未对齐（bbox bottom 不一致）: {sorted(bottoms)}"))
    centers = {round((b[0] + b[2]) / 2) for _, b in boxes}
    if max(centers) - min(centers) > center_tol:
        issues.append(("P1", f"水平中心漂移超过 {center_tol}px: {sorted(centers)}"))
    return issues


def group_stem(path):
    """文件路径 → 帧组键：stem 去掉末尾帧号 _NN（无帧号则整个 stem）。"""
    stem = os.path.splitext(os.path.basename(path))[0]
    return FRAME_NO.sub("", stem)


def run(paths, expected_size=None, max_colors=16, palette=None, frames=True, anim=True,
        components_max=None):
    """批量检查。返回 [(kind, ref, issues), ...]：kind='image' 时 ref=info dict；
    kind='group' 时 ref=帧组键（帧组级问题：对齐 / 动画一致性）。

    帧组按文件名前缀自动聚合（hero_idle_00..07 → hero_idle 一组），
    整目录混检时各资产各自成组互不干扰；组内不足 2 帧不做帧组检查。
    """
    results = []
    infos = []
    for p in paths:
        info, issues = analyze(p, expected_size, max_colors, palette, components_max)
        infos.append(info)
        results.append(("image", info, issues))
    if frames:
        groups = {}
        order = []
        for p, info in zip(paths, infos):
            key = group_stem(p)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(info)
        for key in order:
            group = groups[key]
            if len(group) < 2:
                continue
            extra = frame_alignment(group)
            if anim:
                extra += frame_dynamics(group)
            if extra:
                results.append(("group", key, extra))
    return results
