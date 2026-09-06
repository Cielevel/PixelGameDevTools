#!/usr/bin/env python3
"""AI 像素图标准化：JPEG/大图源 → 真网格 + 干净调色板的还原流水线。

针对 ai-pixel-art-standardization-handoff 交接包的痛点与升级建议实现：
- 网格还原先于一切：亮度梯度剖面 + 去均值自相关找主导周期（含格线相位），
  比相邻峰间距对「精灵不跨满画布、大量格线无过渡」更稳健；--grid 可强制
- 单元内鲁棒采样：每格取众数（默认）或逐通道中位数——JPEG 块噪声在压缩时被
  统计吸收，不做整图盲平均；±1 相位误差也被格内多数色吸收
- OKLab 感知色距量化：定目标色数 → 加权 k-means（确定性）→ 最近色映射；
  映射工程调色板同样走感知色距
- 动画多帧共享网格 + 共享色板（多输入自动启用），防跨帧闪烁
- 输出对齐工程基准：RGBA、alpha 两态、原生（还原后）尺寸、无插值

纯 Pillow 实现，零额外依赖；全程确定性，重跑零差异（可过 pixcli diff）。
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from palette import count_colors, oklab_dist2, rgb_to_oklab
from PIL import Image

MIN_CELL = 2           # 网格检测的最小格距（小于此视为已是原生像素）
MAX_CELL = 128         # 网格检测的最大格距（像素画逻辑格合理范围；超出用 --grid 强制）
ALIGNED_MAX_SIDE = 64  # 短边 ≤ 此值视为已是原生网格（配合唯一色数判据）
ALIGNED_MAX_COLORS = 64
CONF_MIN = 0.35        # 自相关置信度门限（校准：模糊+JPEG 样本 0.47，随机噪声 <0.1）


# ------------------------------------------------------------ 网格检测 ----
def _gradient_profiles(im):
    """亮度梯度剖面：gx[x] = 第 x 列与其右邻列的竖向平均 |ΔL|；gy 同理按行。"""
    W, H = im.size
    L = list(im.convert("L").getdata())
    gx = [0.0] * W
    for x in range(W - 1):
        c0 = L[x::W]
        c1 = L[x + 1::W]
        gx[x] = sum(abs(a - b) for a, b in zip(c0, c1)) / H
    gy = [0.0] * H
    for y in range(H - 1):
        r0 = L[y * W:(y + 1) * W]
        r1 = L[(y + 1) * W:(y + 2) * W]
        gy[y] = sum(abs(a - b) for a, b in zip(r0, r1)) / W
    return gx, gy


def _autocorr_period(profile, max_cell=MAX_CELL):
    """去均值自相关找主导周期（格距）。

    相比「相邻峰间距」对缺失格线（精灵不跨满画布时大量格线无过渡）更稳健：
    缺线只贡献 0 分量，不会错位。得分接近时细分到更小的半周期。
    返回 (period|None, conf)；conf = 该周期自相关 / 剖面能量。
    """
    n = len(profile)
    mean = sum(profile) / n
    z = [v - mean for v in profile]
    energy = sum(v * v for v in z) / n
    if energy <= 1e-9:
        return None, 0.0
    max_p = min(max_cell, n // 2)
    if max_p < MIN_CELL:
        return 1, 1.0
    scores = {}
    for p in range(MIN_CELL, max_p + 1):
        scores[p] = sum(z[i] * z[i + p] for i in range(n - p)) / (n - p)
    best_p = max(scores, key=lambda k: scores[k])
    best_s = scores[best_p]
    p = best_p
    while p % 2 == 0 and p // 2 >= MIN_CELL and scores[p // 2] >= 0.7 * best_s:
        p //= 2
    return p, max(0.0, scores[p] / energy)


def _phase_offset(profile, p):
    """格线相位：φ ∈ [0,p) 使边界采样和最大；格内容起点 = (φ+1) % p。"""
    n = len(profile)
    best_phi, best_s = 0, -1.0
    for phi in range(p):
        s = sum(profile[x] for x in range(phi, n, p))
        if s > best_s:
            best_s, best_phi = s, phi
    return (best_phi + 1) % p


def _snap_divisor(size, s):
    """格距优先取画布的整数因子（容差 ±2 内就近吸附；仅相位归零时适用）。"""
    if s is None:
        return None
    if size % s == 0:
        return s
    for d in (1, 2):
        if s - d >= MIN_CELL and size % (s - d) == 0:
            return s - d
        if size % (s + d) == 0:
            return s + d
    return s


def detect_grid(im):
    """估计逻辑网格（每格源像素数与格内容起点）。

    返回 dict：ok / cell=(cw,ch) / origin=(ox,oy) / cells=(cols,rows) / conf / note。
    短边 ≤ ALIGNED_MAX_SIDE 且唯一色 ≤ ALIGNED_MAX_COLORS 的输入直接视为
    已对齐（真像素画进门，无需还原）。
    """
    W, H = im.size
    if W <= ALIGNED_MAX_SIDE and H <= ALIGNED_MAX_SIDE and \
            len(count_colors(im)) <= ALIGNED_MAX_COLORS:
        return {"ok": True, "cell": (1, 1), "origin": (0, 0), "cells": (W, H),
                "conf": 1.0, "note": "小图少色，视为已对齐网格"}
    gx, gy = _gradient_profiles(im)
    sx, cx = _autocorr_period(gx)
    sy, cy = _autocorr_period(gy)
    if not sx or not sy:
        return {"ok": False, "cell": None, "origin": (0, 0), "cells": None,
                "conf": 0.0, "note": "剖面无有效梯度能量"}
    conf = round(min(cx, cy), 2)
    ox, oy = _phase_offset(gx, sx), _phase_offset(gy, sy)
    if conf < CONF_MIN:
        return {"ok": False, "cell": (sx, sy), "origin": (ox, oy),
                "cells": (max(1, (W - ox) // sx), max(1, (H - oy) // sy)),
                "conf": conf, "note": "自相关置信度不足"}
    # 相位归零（画布即网格）时把格距吸附为画布整数因子
    if ox == 0:
        sx = _snap_divisor(W, sx)
    if oy == 0:
        sy = _snap_divisor(H, sy)
    return {"ok": True, "cell": (sx, sy), "origin": (ox, oy),
            "cells": (max(1, (W - ox) // sx), max(1, (H - oy) // sy)),
            "conf": conf,
            "note": "已吸附画布因子" if ox == 0 or oy == 0 else ""}


# ---------------------------------------------------------- 单元内采样 ----
def corner_background(im, tol=8):
    """四角 2×2 均值一致 → 返回背景 RGB；否则 None（无法可靠判定）。"""
    W, H = im.size
    rgb = im.convert("RGBA")
    pts = []
    for x, y in ((0, 0), (W - 2, 0), (0, H - 2), (W - 2, H - 2)):
        blk = [rgb.getpixel((min(x + dx, W - 1), min(y + dy, H - 1)))
               for dx in (0, 1) for dy in (0, 1)]
        pts.append(tuple(sum(p[i] for p in blk) // 4 for i in range(3)))
    base = pts[0]
    if all(max(abs(c[i] - base[i]) for i in range(3)) <= tol for c in pts[1:]):
        return base
    return None


def _median(values):
    vs = sorted(values)
    n = len(vs)
    return vs[n // 2] if n % 2 else (vs[n // 2 - 1] + vs[n // 2]) // 2


def sample_cells(im, cw, ch, method="mode", bg=None, bg_tol=16, ox=0, oy=0):
    """按网格单元采样：每格取一个代表色（众数或逐通道中位数）。

    (ox,oy) 为格内容起点（格线相位，见 detect_grid）；输出只含完整格。
    源图带有效 alpha 时按格两态化（透明占比 ≥ 1/2 → 透明）；
    否则若给 bg（RGB 元组），代表色与背景距离 ≤ bg_tol（RGB 欧氏）的格判为背景
    候选，且只删除「从画布边界连通」的背景——被主体包住的同类色格（如白底图上
    的白色高光）保留，不挖洞。
    """
    im = im.convert("RGBA")
    W, H = im.size
    cols, rows = max(1, (W - ox) // cw), max(1, (H - oy) // ch)
    data = list(im.getdata())
    has_alpha = any(p[3] < 255 for p in data)
    tol2 = bg_tol * bg_tol
    grid = [[None] * cols for _ in range(rows)]
    for cy in range(rows):
        y0 = oy + cy * ch
        for cx in range(cols):
            x0 = ox + cx * cw
            pxs = []
            for dy in range(ch):
                base = (y0 + dy) * W + x0
                pxs.extend(data[base:base + cw])
            if has_alpha:
                solid = [p for p in pxs if p[3] > 0]
                if len(solid) * 2 <= len(pxs):
                    continue
                pxs = solid
            if method == "median":
                c = (_median([p[0] for p in pxs]), _median([p[1] for p in pxs]),
                     _median([p[2] for p in pxs]))
            else:
                # 众数分桶投票：先按 8 级/通道分桶（吸收 ±3 噪声，防平局摇摆），
                # 胜桶取均值后再做一次 ±5 邻域 mean-shift——桶窗口会截断噪声分布，
                # 重收尾部让代表色无偏（均匀格零损失，噪声格收敛到簇中心）
                bcount = Counter()
                bsum = {}
                for p in pxs:
                    bk = (((p[0] + 4) >> 3) << 10) | (((p[1] + 4) >> 3) << 5) | ((p[2] + 4) >> 3)
                    bcount[bk] += 1
                    s = bsum.get(bk)
                    if s is None:
                        bsum[bk] = [p[0], p[1], p[2], 1]
                    else:
                        s[0] += p[0]
                        s[1] += p[1]
                        s[2] += p[2]
                        s[3] += 1
                bk = max(bcount.items(), key=lambda t: (t[1], -t[0]))[0]
                s = bsum[bk]
                core = (s[0] / s[3], s[1] / s[3], s[2] / s[3])
                acc = [0, 0, 0, 0]
                for p in pxs:
                    if max(abs(p[i] - core[i]) for i in range(3)) <= 5:
                        acc[0] += p[0]
                        acc[1] += p[1]
                        acc[2] += p[2]
                        acc[3] += 1
                c = (round(acc[0] / acc[3]), round(acc[1] / acc[3]), round(acc[2] / acc[3]))
            grid[cy][cx] = c
    if bg is not None and not has_alpha:
        near = [[c is not None and
                 (c[0] - bg[0]) ** 2 + (c[1] - bg[1]) ** 2 + (c[2] - bg[2]) ** 2 <= tol2
                 for c in row] for row in grid]
        stack = [(x, y) for x in range(cols) for y in (0, rows - 1) if near[y][x]] + \
                [(x, y) for y in range(rows) for x in (0, cols - 1) if near[y][x]]
        seen = set(stack)
        while stack:
            x, y = stack.pop()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < cols and 0 <= ny < rows and near[ny][nx] and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        for y in range(rows):
            for x in range(cols):
                if (x, y) in seen:
                    grid[y][x] = None
    out = Image.new("RGBA", (cols, rows), (0, 0, 0, 0))
    op = out.load()
    for y in range(rows):
        for x in range(cols):
            c = grid[y][x]
            if c is not None:
                op[x, y] = (c[0], c[1], c[2], 255)
    return out


# ------------------------------------------------- OKLab 调色板量化 ----
def build_palette_k(color_counts, k, iters=24):
    """确定性加权 k-means 色板（OKLab 空间）。

    color_counts: [((r,g,b), n)]；k 上限。种子 = 最高频色 + 最远点补齐，
    Lloyd 迭代收敛，簇代表色取簇内最高频原色（贴近真实像素色，平局取 RGB 小者）。
    返回 [(rgb, lab)] 按簇占比降序。
    """
    uniq = sorted(color_counts, key=lambda t: (-t[1], t[0]))
    if k <= 0 or len(uniq) <= k:
        return [(rgb, rgb_to_oklab(rgb)) for rgb, _ in uniq]
    items = [(rgb, n, rgb_to_oklab(rgb)) for rgb, n in uniq]
    seeds = [items[0][2]]
    chosen = {0}
    while len(seeds) < k:
        bi, bd = None, -1.0
        for i, it in enumerate(items):
            if i in chosen:
                continue
            d = min(oklab_dist2(it[2], s) for s in seeds)
            if d > bd:
                bd, bi = d, i
        seeds.append(items[bi][2])
        chosen.add(bi)
    assign = [0] * len(items)
    for _ in range(iters):
        changed = False
        for i, it in enumerate(items):
            j = min(range(len(seeds)), key=lambda s: oklab_dist2(it[2], seeds[s]))
            if j != assign[i]:
                assign[i] = j
                changed = True
        if not changed:
            break
        for s in range(len(seeds)):
            members = [it for i, it in enumerate(items) if assign[i] == s]
            if not members:
                continue
            tw = sum(m[1] for m in members)
            seeds[s] = tuple(
                sum(m[2][d] * m[1] for m in members) / tw for d in range(3))
    clusters = {}
    for i, it in enumerate(items):
        clusters.setdefault(assign[i], []).append(it)
    ranked = sorted(clusters.values(), key=lambda ms: -sum(m[1] for m in ms))
    out = []
    for members in ranked:
        rep = max(members, key=lambda m: (m[1], tuple(-c for c in m[0])))[0]
        out.append((rep, rgb_to_oklab(rep)))
    return out


def map_with_palette(img, pal):
    """把 img 的不透明像素按 OKLab 最近色映射到 pal（[(rgb, lab)]）。"""
    mapping = {}
    op = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = op[x, y]
            if a == 0:
                continue
            key = (r, g, b)
            if key not in mapping:
                lab = rgb_to_oklab(key)
                mapping[key] = min(pal, key=lambda p: oklab_dist2(lab, p[1]))[0]
            t = mapping[key]
            op[x, y] = (t[0], t[1], t[2], 255)
    return img


def quantize_image(img, k):
    """对已采样的小图按目标色数量化（OKLab k-means 色板 + 最近色映射）。"""
    cnt = Counter((p[0], p[1], p[2]) for p in img.getdata() if p[3] > 0)
    if not cnt:
        return img
    pal = build_palette_k(list(cnt.items()), k)
    return map_with_palette(img, pal)


def snap_to_palette(img, palette):
    """把图映射到工程调色板（palette.Palette 对象，感知色距最近色）。"""
    pal = [(c, rgb_to_oklab(c)) for c in palette.colors]
    return map_with_palette(img, pal)


# -------------------------------------------------------------- 主流程 ----
def _parse_grid(grid):
    if grid == "auto":
        return "auto"
    if isinstance(grid, int):
        return (grid, grid)
    s = str(grid).lower().split("x")
    if len(s) == 2 and s[0].isdigit() and s[1].isdigit():
        return (int(s[0]), int(s[1]))
    raise ValueError("grid 参数应为 auto / N / WxH，收到: {}".format(grid))


def _resolve_grid(im, grid):
    if grid != "auto":
        cw, ch = _parse_grid(grid)
        gx, gy = _gradient_profiles(im)
        ox, oy = _phase_offset(gx, cw), _phase_offset(gy, ch)
        return {"ok": True, "cell": (cw, ch), "origin": (ox, oy),
                "cells": (max(1, (im.size[0] - ox) // cw),
                          max(1, (im.size[1] - oy) // ch)),
                "conf": None, "note": "手动指定（相位自动）"}
    g = detect_grid(im)
    if not g["ok"]:
        raise ValueError("网格检测置信度不足（conf={}，{}）；"
                         "请用 --grid 手动指定每格源像素数".format(g["conf"], g["note"]))
    return g


def _pick_bg(im, bg):
    return corner_background(im) if bg == "auto" else (bg if isinstance(bg, tuple) else None)


def standardize(im, grid="auto", sampling="mode", colors=16, palette=None,
                bg="auto", bg_tol=16):
    """单图标准化。返回 (out_image, report)。

    palette 为 palette.Palette 对象时优先映射工程色板；否则 colors>0 走 k-means 量化。
    bg: "auto"（四角检测）| "keep" | (r,g,b)。
    """
    im = im.convert("RGBA")
    rep = {"src_size": im.size}
    g = _resolve_grid(im, grid)
    rep["grid"] = g
    cw, ch = g["cell"]
    if (cw, ch) == (1, 1):
        out = im.copy()
        rep["bg"] = None
    else:
        bgc = _pick_bg(im, bg)
        rep["bg"] = bgc
        out = sample_cells(im, cw, ch, method=sampling, bg=bgc, bg_tol=bg_tol,
                           ox=g["origin"][0], oy=g["origin"][1])
    rep["colors_sampled"] = len(count_colors(out))
    if palette is not None:
        out = snap_to_palette(out, palette)
        rep["quantize"] = "palette:{}".format(palette.name)
    elif colors and colors > 0:
        out = quantize_image(out, colors)
        rep["quantize"] = "k={}".format(colors)
    else:
        rep["quantize"] = None
    rep["colors_out"] = len(count_colors(out))
    return out, rep


def standardize_frames(images, grid="auto", sampling="mode", colors=16,
                       palette=None, bg="auto", bg_tol=16, shared=True):
    """多帧标准化：跨帧共享网格与色板（防闪烁）。返回 ([out], report)。

    shared=True 时网格取各帧检测结果的众数，色板对全部帧采样结果合并聚类。
    """
    grids = [_resolve_grid(im, grid) for im in images]
    cell_used = None
    if shared:
        cw, ch = Counter(g["cell"] for g in grids).most_common(1)[0][0]
        cell_used = (cw, ch)
    sampled = []
    bgs = []
    for im, g in zip(images, grids):
        im = im.convert("RGBA")
        gcw, gch = cell_used or g["cell"]
        bgc = _pick_bg(im, bg)
        bgs.append(bgc)
        sampled.append(sample_cells(im, gcw, gch, method=sampling, bg=bgc,
                                    bg_tol=bg_tol, ox=g["origin"][0], oy=g["origin"][1])
                       if (gcw, gch) != (1, 1) else im.copy())
    outs = []
    if palette is not None:
        for s in sampled:
            outs.append(snap_to_palette(s, palette))
        quant = "palette:{}".format(palette.name)
    elif colors and colors > 0:
        pooled = Counter()
        for s in sampled:
            pooled.update((p[0], p[1], p[2]) for p in s.getdata() if p[3] > 0)
        pal = build_palette_k(list(pooled.items()), colors)
        for s in sampled:
            outs.append(map_with_palette(s, pal))
        quant = "k={}（跨帧合并聚类）".format(colors)
    else:
        outs = list(sampled)
        quant = None
    rep = {"frames": len(images),
           "grid_cell": cell_used or [g["cell"] for g in grids],
           "bg": bgs[0], "quantize": quant,
           "colors_out": [len(count_colors(o)) for o in outs]}
    return outs, rep
