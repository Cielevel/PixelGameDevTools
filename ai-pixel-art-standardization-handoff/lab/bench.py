#!/usr/bin/env python3
"""AI 像素图标准化对照实验驱动脚本（交接包测试协议的落地）。

工具：
  baseline      复刻 asset-inspector 现有链路：NEAREST 缩格 1/32（先验人工选档）+ RGB 阈值 30 众数归并
  baseline_only 仅 NEAREST 缩格（隔离归并的贡献）
  spritegrid{,_q5,_q4}   SpriteGrid 自动网格检测（+ 量化位深变体）
  ppa{,_c8,_c16,_c32}    proper-pixel-art（+ 目标色数变体）
  pixfix{,_c16,_c32}     Pixel Art Fixer Python 实现（+ 目标色数变体）
  standardize   本工程新实现（bench_std 模块存在时自动加入）

样本：sampleA_f0.jpg（良性）、sampleB_f2_hard.jpg（模糊+JPEG 困难）
指标：尺寸 / 唯一色数(不透明) / 对真值命中率 / 色板外像素占比 / 背景残留 / 耗时 / 幂等
动画：4 帧 JPEG，各工具逐帧处理 + spritegrid/ppa 走共享网格管线；测静态像素闪烁率
"""
import io
import json
import os
import subprocess
import sys
import time
from collections import Counter

from PIL import Image

LAB = "/tmp/pas-lab"
VENV_BIN = os.path.join(LAB, ".venv", "bin")
SAMPLES = os.path.join(LAB, "samples")
OUT = os.path.join(LAB, "out")
GT = os.path.join(SAMPLES, "gt")
sys.path.insert(0, LAB)

SAMPLES_META = [
    ("A", os.path.join(SAMPLES, "sampleA_f0.jpg"), os.path.join(GT, "f0.png")),
    ("B", os.path.join(SAMPLES, "sampleB_f2_hard.jpg"), os.path.join(GT, "f2.png")),
]
ANIM_FRAMES = [0, 2, 3, 6]

# --------------------------------------------------------------- 工具实现 ----
def _nearest_resize(im, size):
    return im.convert("RGBA").resize(size, Image.NEAREST)

def _timed(fn):
    def run(in_path):
        t0 = time.perf_counter()
        im = fn(in_path)
        return im, time.perf_counter() - t0
    return run

def baseline_run(in_path):
    im = Image.open(in_path).convert("RGBA")
    small = _nearest_resize(im, (32, 32))
    return merge_threshold(small, 30)

def baseline_only_run(in_path):
    im = Image.open(in_path).convert("RGBA")
    return _nearest_resize(im, (32, 32))

def merge_threshold(img, t):
    """asset-inspector「合并阈值」复刻：颜色按占比排序，阈值内归并到众数代表色。"""
    cnt = Counter(px[:3] for px in img.getdata() if px[3] > 0)
    reps, mapping = [], {}
    for c, _ in cnt.most_common():
        for r in reps:
            if (c[0]-r[0])**2 + (c[1]-r[1])**2 + (c[2]-r[2])**2 <= t*t:
                mapping[c] = r
                break
        else:
            reps.append(c)
            mapping[c] = c
    out = img.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a:
                nr, ng, nb = mapping[(r, g, b)]
                px[x, y] = (nr, ng, nb, 255)
    return out

def spritegrid_cmd(extra):
    def run(in_path):
        out = in_path + ".sg.png"
        t0 = time.perf_counter()
        subprocess.run([os.path.join(VENV_BIN, "spritegrid"), in_path, "-o", out] + extra,
                       check=True, capture_output=True)
        dt = time.perf_counter() - t0
        return Image.open(out).convert("RGBA"), dt
    return run

def ppa_cmd(extra):
    def run(in_path):
        out = in_path + ".ppa.png"
        t0 = time.perf_counter()
        subprocess.run([os.path.join(VENV_BIN, "ppa"), in_path, "-o", out] + extra,
                       check=True, capture_output=True)
        dt = time.perf_counter() - t0
        return Image.open(out).convert("RGBA"), dt
    return run

def pixfix_run(**kw):
    def run(in_path):
        import pixelfixer.api as api
        data = open(in_path, "rb").read()
        t0 = time.perf_counter()
        res = api.process(data, **kw)
        dt = time.perf_counter() - t0
        im = Image.open(io.BytesIO(res["png"])).convert("RGBA")
        im.info["detected"] = (res.get("cols"), res.get("rows"), res.get("step_x"), res.get("confidence"))
        return im, dt
    return run

def standardize_run(in_path):
    import bench_std              # 新工具的薄封装（升级完成后填充）
    t0 = time.perf_counter()
    im = bench_std.run(in_path)
    dt = time.perf_counter() - t0
    return im, dt

TOOLS = [
    ("baseline", _timed(baseline_run)),
    ("baseline_only", _timed(baseline_only_run)),
    ("spritegrid", spritegrid_cmd([])),
    ("spritegrid_q5", spritegrid_cmd(["-q", "5"])),
    ("spritegrid_q4", spritegrid_cmd(["-q", "4"])),
    ("ppa", ppa_cmd([])),
    ("ppa_c8", ppa_cmd(["-c", "8"])),
    ("ppa_c16", ppa_cmd(["-c", "16"])),
    ("ppa_c32", ppa_cmd(["-c", "32"])),
    ("pixfix", pixfix_run()),
    ("pixfix_c16", pixfix_run(k_colors=16)),
    ("pixfix_c32", pixfix_run(k_colors=32)),
]
if os.path.exists(os.path.join(LAB, "bench_std.py")):
    import bench_std
    TOOLS.append(("standardize", _timed(bench_std.run)))
    if hasattr(bench_std, "run_c16"):
        TOOLS.append(("standardize_c16", _timed(bench_std.run_c16)))

# ------------------------------------------------------------------- 指标 ----
def gt_info(gt_path):
    gt = Image.open(gt_path).convert("RGBA")
    px = gt.load()
    w, h = gt.size
    opaque = [(x, y) for y in range(h) for x in range(w) if px[x, y][3] > 0]
    pal = set(px[x, y][:3] for x, y in opaque)
    return gt, opaque, pal

def metrics(out_im, gt, gt_opaque, gt_pal):
    w0, h0 = gt.size
    raw_size = out_im.size
    if out_im.size != (w0, h0):
        out_im = _nearest_resize(out_im, (w0, h0))
    op = out_im.load()
    gtp = gt.load()
    gw, gh = gt.size
    transparent_total = gw * gh - len(gt_opaque)

    def score_at(dx, dy):
        hit = hit_tol = outside_pal = 0
        for x, y in gt_opaque:
            sx, sy = x + dx, y + dy
            if 0 <= sx < gw and 0 <= sy < gh:
                c = op[sx, sy]
            else:
                c = (0, 0, 0)
            g = gtp[x, y][:3]
            if c[:3] == g:
                hit += 1
            if max(abs(c[i] - g[i]) for i in range(3)) <= 4:
                hit_tol += 1
            if not any(max(abs(c[i] - p[i]) for i in range(3)) <= 4 for p in gt_pal):
                outside_pal += 1
        return hit, hit_tol, outside_pal

    best = max(
        (score_at(dx, dy) + (dx, dy) for dx in range(-3, 4) for dy in range(-3, 4)),
        key=lambda t: (t[1], t[0]),
    )
    hit, hit_tol, outside_pal, bdx, bdy = best
    bleed = sum(1 for y in range(gh) for x in range(gw)
                if gtp[x, y][3] == 0 and op[x, y][3] > 0)
    colors = Counter(c[:3] for c in out_im.getdata() if c[3] > 0)
    return {
        "raw_size": raw_size,
        "colors": len(colors),
        "match": round(100.0 * hit / len(gt_opaque), 1),
        "match_tol": round(100.0 * hit_tol / len(gt_opaque), 1),
        "match_off": (bdx, bdy),
        "offpal": round(100.0 * outside_pal / len(gt_opaque), 1),
        "bleed": round(100.0 * bleed / max(transparent_total, 1), 1),
    }

def idempotency(runner, out_im, tmp_path):
    out_im.save(tmp_path)
    try:
        im2, _ = runner(tmp_path)
        if im2.size != out_im.size:
            im2 = _nearest_resize(im2, out_im.size)
        diff = sum(1 for a, b in zip(out_im.convert("RGBA").getdata(), im2.convert("RGBA").getdata()) if a != b)
        return {"diff_px": diff, "idem": diff == 0}
    except Exception as e:
        return {"diff_px": -1, "idem": None, "err": str(e)[:80]}

# ------------------------------------------------------------------- 主流程 ----
def main():
    os.makedirs(OUT, exist_ok=True)
    results = {}
    for tag, in_path, gt_path in SAMPLES_META:
        gt, gt_opaque, gt_pal = gt_info(gt_path)
        for name, runner in TOOLS:
            key = "{}:{}".format(name, tag)
            try:
                out_im, dt = runner(in_path)
            except Exception as e:
                results[key] = {"error": str(e)[:120]}
                print("{:<22} {:<2} 失败: {}".format(name, tag, str(e)[:80]))
                continue
            det = out_im.info.get("detected")
            m = metrics(out_im, gt, gt_opaque, gt_pal)
            idem = idempotency(runner, out_im, os.path.join(OUT, "{}_{}_idem.png".format(name, tag)))
            out_im.save(os.path.join(OUT, "{}_{}.png".format(name, tag)))
            results[key] = {"t_s": round(dt, 2), **m, **idem, "detected": det}
            print("{:<22} {:<2} 尺寸{:<10} 色{:<4} 容差命中{:<6}% 精确{:<6}% @{} 色板外{:<5}% 残留{:<5}% 幂等{:<5} {:.2f}s {}".format(
                name, tag, str(m["raw_size"]), m["colors"], m["match_tol"], m["match"], str(m["match_off"]),
                m["offpal"], m["bleed"], str(idem["idem"]), dt,
                "det={}".format(det) if det else ""))
    with open(os.path.join(LAB, "results.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("\nresults.json 写入完成")

if __name__ == "__main__":
    main()
