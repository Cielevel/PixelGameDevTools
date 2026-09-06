#!/usr/bin/env python3
"""动画测试：4 帧 JPEG → 各工具处理后测跨帧闪烁（静态像素在帧间的色彩一致性）。

模式一（逐帧独立）：所有单图工具逐帧处理，测天然跨帧稳定性。
模式二（共享网格管线）：spritegrid process_animation / ppa GIF 管线。
闪烁率 = 4 帧输出中，GT 静态像素（真值同色且不透明）出现 ≥2 种输出色的比例。
"""
import io
import os
import subprocess
import sys
from collections import Counter

from PIL import Image

LAB = "/tmp/pas-lab"
VENV_BIN = os.path.join(LAB, ".venv", "bin")
SAMPLES = os.path.join(LAB, "samples")
OUT = os.path.join(LAB, "out_anim")
sys.path.insert(0, LAB)

FRAMES = [0, 2, 3, 6]
JPEG = [os.path.join(SAMPLES, "anim", "f{}.jpg".format(i)) for i in FRAMES]
GT = [Image.open(os.path.join(SAMPLES, "gt", "f{}.png".format(i))).convert("RGBA") for i in FRAMES]

os.makedirs(OUT, exist_ok=True)

gif_path = os.path.join(SAMPLES, "anim.gif")
# GIF 输入（共享网格管线用）：JPEG 帧 → GIF。
# 注意：必须全帧共享同一参考色板，否则逐帧自适应量化本身就会引入跨帧色漂。
_rgb = [Image.open(p).convert("RGB") for p in JPEG]
_tall = Image.new("RGB", (_rgb[0].width, _rgb[0].height * len(_rgb)))
for k, im in enumerate(_rgb):
    _tall.paste(im, (0, im.height * k))
_ref = _tall.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
_pframes = [im.quantize(palette=_ref, dither=Image.Dither.NONE) for im in _rgb]
_pframes[0].save(gif_path, save_all=True, append_images=_pframes[1:], duration=120, loop=0)

# ------------------------------------------------------------- 工具封装 ----
def _nearest(im, size):
    return im.convert("RGBA").resize(size, Image.NEAREST)

def merge_threshold(img, t):
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
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a:
                nr, ng, nb = mapping[(r, g, b)]
                px[x, y] = (nr, ng, nb, 255)
    return out

def run_baseline(p):
    return merge_threshold(_nearest(Image.open(p), (32, 32)), 30)

def run_spritegrid(p):
    out = p + ".sg.png"
    subprocess.run([os.path.join(VENV_BIN, "spritegrid"), p, "-o", out], check=True, capture_output=True)
    return Image.open(out).convert("RGBA")

def run_ppa(p):
    out = p + ".ppa.png"
    subprocess.run([os.path.join(VENV_BIN, "ppa"), p, "-o", out], check=True, capture_output=True)
    return Image.open(out).convert("RGBA")

def run_pixfix(p):
    import pixelfixer.api as api
    res = api.process(open(p, "rb").read())
    return Image.open(io.BytesIO(res["png"])).convert("RGBA")

try:
    import bench_std
    def run_std(p):
        return bench_std.run(p)
    HAS_STD = True
except ImportError:
    HAS_STD = False

PER_FRAME = {
    "baseline": run_baseline,
    "spritegrid": run_spritegrid,
    "ppa": run_ppa,
    "pixfix": run_pixfix,
}
if HAS_STD:
    PER_FRAME["standardize"] = run_std

# ------------------------------------------------------------- 闪烁指标 ----
def to32(im):
    return im if im.size == (32, 32) else _nearest(im, (32, 32))

def static_mask():
    gt_ps = [g.load() for g in GT]
    mask, colors = set(), {}
    for y in range(32):
        for x in range(32):
            cs = [gt_ps[k][x, y] for k in range(4)]
            if all(c[3] > 0 for c in cs) and len({c[:3] for c in cs}) == 1:
                mask.add((x, y))
                colors[(x, y)] = cs[0][:3]
    return mask, colors

def flicker(frames32):
    mask, colors = static_mask()
    bad = 0
    for x, y in mask:
        vals = {frames32[k].load()[x, y][:3] for k in range(4)}
        if len(vals) > 1:
            bad += 1
    palettes = [len({c[:3] for c in f.getdata() if c[3] > 0}) for f in frames32]
    return round(100.0 * bad / len(mask), 1), palettes

def report(name, frames32):
    fl, pals = flicker(frames32)
    print("{:<24} 闪烁{:<6}% 各帧色数 {}".format(name, fl, pals))
    return fl, pals

results = {}

# ---- 模式一：逐帧独立
print("== 模式一：逐帧独立处理（4 帧 JPEG）==")
for name, runner in PER_FRAME.items():
    outs = []
    for p in JPEG:
        try:
            outs.append(to32(runner(p)))
        except Exception as e:
            print(name, "失败:", str(e)[:80])
            outs = []
            break
    if outs:
        results["perframe:" + name] = report(name, outs)
        for k, f in enumerate(outs):
            f.save(os.path.join(OUT, "{}_f{}.png".format(name, FRAMES[k])))

# ---- 模式二：共享网格管线
print("== 模式二：共享网格管线 ==")
try:
    from spritegrid.animation import process_animation
    outgif = os.path.join(OUT, "spritegrid_anim.gif")
    frames = process_animation(gif_path, outgif, quantize=8)
    results["shared:spritegrid"] = report("spritegrid(共享网格GIF)", [to32(f) for f in frames])
except Exception as e:
    print("spritegrid 共享网格失败:", str(e)[:120])
try:
    outdir = os.path.join(OUT, "ppa_gif")
    subprocess.run([os.path.join(VENV_BIN, "ppa"), gif_path, "-o", outdir], check=True, capture_output=True)
    got = sorted([os.path.join(outdir, f) for f in os.listdir(outdir) if f.lower().endswith((".png", ".gif"))])
    frames = [Image.open(p).convert("RGBA") for p in got]
    # 单个 GIF 文件时拆多帧
    if len(frames) == 1 and got and got[0].endswith(".gif"):
        im = Image.open(got[0])
        frames = []
        for i in range(im.n_frames):
            im.seek(i)
            frames.append(im.convert("RGBA"))
    if frames:
        results["shared:ppa"] = report("ppa(GIF管线)", [to32(f) for f in frames])
except Exception as e:
    print("ppa GIF 管线失败:", str(e)[:120])

# ---- 模式三：本工程 standardize_frames（共享网格 + 跨帧合并聚类色板，输出 PNG 序列）
if HAS_STD:
    try:
        import standardize as _std
        ims = [Image.open(p) for p in JPEG]
        outs, rep = _std.standardize_frames(ims, colors=16)
        results["shared:standardize"] = report("standardize(共享网格+色板)", [to32(o) for o in outs])
        print("   rep:", rep)
        for k, o in enumerate(outs):
            o.save(os.path.join(OUT, "standardize_shared_f{}.png".format(FRAMES[k])))
    except Exception as e:
        print("standardize 共享失败:", str(e)[:200])

print("\n完成 →", OUT)
