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
        rgb = tuple(rgb)[:3]
        return min(
            self.colors,
            key=lambda c: (c[0] - rgb[0]) ** 2 + (c[1] - rgb[1]) ** 2 + (c[2] - rgb[2]) ** 2,
        )

    def index(self, rgb):
        try:
            return self.colors.index(tuple(rgb)[:3])
        except ValueError:
            return -1


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
    """不透明像素归入调色板（精确命中优先，否则最近色）；alpha 保持两态。"""
    src = img.convert("RGBA")
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    sp, op = src.load(), out.load()
    exact = {c: c for c in palette.colors}
    w, h = src.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a == 0:
                continue
            c = (r, g, b)
            c = exact.get(c) or palette.nearest(c)
            op[x, y] = (c[0], c[1], c[2], 255)
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
