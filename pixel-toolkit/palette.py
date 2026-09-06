"""调色板：JSON 色值表读写、最近色映射、量化、alpha 两态化、色条导出。

JSON 格式（存放于 `assets/palettes/`）：
{
  "name": "slime",
  "colors": ["#0b1e3a", "#123c6b", ...],
  "roles": {"outline": "#0b1e3a", "shadow": "#123c6b", "mid": "...", "light": "...", "highlight": "..."}
}
roles 可选；colors 建议按 明→暗 或按用途排列，单张精灵 ≤16 色（含描边色）。
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field

from PIL import Image, ImageDraw


def hex_to_rgb(s):
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*tuple(rgb)[:3])


@dataclass
class Palette:
    name: str = "palette"
    colors: list = field(default_factory=list)   # [(r,g,b), ...]
    roles: dict = field(default_factory=dict)    # {"outline": (r,g,b), ...}

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        colors = [hex_to_rgb(c) if isinstance(c, str) else tuple(c) for c in data.get("colors", [])]
        roles = {
            k: (hex_to_rgb(v) if isinstance(v, str) else tuple(v))
            for k, v in data.get("roles", {}).items()
        }
        return cls(name=data.get("name", "palette"), colors=colors, roles=roles)

    def save(self, path):
        data = {"name": self.name, "colors": [rgb_to_hex(c) for c in self.colors]}
        if self.roles:
            data["roles"] = {k: rgb_to_hex(v) for k, v in self.roles.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def has(self, rgb):
        return tuple(rgb)[:3] in self.colors

    def nearest(self, rgb):
        """最近色映射（OKLab 感知色距；2026-09-06 起 RGB 欧氏升级为感知色距）。"""
        lab = rgb_to_oklab(rgb)
        return min(self.colors, key=lambda c: oklab_dist2(lab, rgb_to_oklab(c)))

    def index(self, rgb):
        try:
            return self.colors.index(tuple(rgb)[:3])
        except ValueError:
            return -1


# ---------------------------------------------------------------- OKLab ----
# OKLab 感知色空间（Björn Ottosson, 2020）：最近色映射在 OKLab 空间做距离计算，
# 比 RGB 欧氏更贴近人眼色差（交接包标准化流水线 Step 3 的映射规则）。

def _srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_to_srgb(v):
    if v <= 0.0:
        return 0
    v = 12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055
    return max(0, min(255, round(v * 255)))


def rgb_to_oklab(rgb):
    r, g, b = (_srgb_to_lin(c) for c in tuple(rgb)[:3])
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklab_to_rgb(lab):
    L, A, B = lab
    l_ = L + 0.3963377774 * A + 0.2158037573 * B
    m_ = L - 0.1055613458 * A - 0.0638541728 * B
    s_ = L - 0.0894841775 * A - 1.2914855480 * B
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return tuple(_lin_to_srgb(v) for v in (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    ))


def oklab_dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def count_colors(img):
    """不透明像素唯一色计数：[((r,g,b), n), ...] 按数量降序。"""
    img = img.convert("RGBA")
    cnt = Counter()
    for r, g, b, a in img.getdata():
        if a:
            cnt[(r, g, b)] += 1
    return cnt.most_common()


def palette_from_image(img, max_colors=16):
    """从图像提取调色板（按出现频次取前 max_colors 种）。"""
    return [c for c, _ in count_colors(img)[:max_colors]]


def quantize(img, palette):
    """不透明像素归入调色板（精确命中优先，否则 OKLab 最近色）；alpha 保持两态。

    唯一色 → 目标色的映射整表预计算（大图逐像素查表，避免重复距离计算）。
    """
    src = img.convert("RGBA")
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    exact = {c: c for c in palette.colors}
    mapping = {}
    sp, op = src.load(), out.load()
    w, h = src.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a == 0:
                continue
            c = (r, g, b)
            t = exact.get(c)
            if t is None:
                if c not in mapping:
                    mapping[c] = palette.nearest(c)
                t = mapping[c]
            op[x, y] = (t[0], t[1], t[2], 255)
    return out


def enforce_alpha(img, threshold=128):
    """alpha 两态化：>= threshold → 255，否则 0。"""
    img = img.convert("RGBA")
    out = img.copy()
    op = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = op[x, y]
            na = 255 if a >= threshold else 0
            if na != a:
                op[x, y] = (r, g, b, na)
    return out


def export_swatch(colors, path, cell=16, roles=None):
    """竖排色条 PNG：每行一个色块 + [角色名] 色值，用于人工核对。"""
    roles = roles or {}
    colors = list(colors)
    # 画布宽度按最长标签自适应（不小于旧固定宽度，保持既有色条输出不变）
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    labels = []
    for c in colors:
        label = next((k + " " for k, v in roles.items() if tuple(v)[:3] == tuple(c)[:3]), "")
        labels.append(label + rgb_to_hex(c))
    text_w = max((probe.textlength(t) for t in labels), default=0)
    width = max(cell + 140, cell + 12 + int(text_w) + 8)
    img = Image.new("RGBA", (width, len(colors) * (cell + 4) + 8), (24, 26, 30, 255))
    d = ImageDraw.Draw(img)
    for i, c in enumerate(colors):
        y = 4 + i * (cell + 4)
        d.rectangle([4, y, 4 + cell, y + cell], fill=(c[0], c[1], c[2], 255), outline=(70, 74, 82, 255))
        d.text((cell + 12, y + (cell - 10) // 2), labels[i], fill=(225, 228, 235, 255))
    img.save(path)
