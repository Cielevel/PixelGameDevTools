"""像素画布：逐像素精确的绘制基元（无抗锯齿、无插值），供脚本化生成精灵。

约定（与工作区 `AGENTS.md` 一致）：
- 颜色一律 RGBA 四元组（3 元组自动补 alpha=255）；alpha 只用 0 / 255 两态
- 坐标为整数像素；椭圆等基元按像素中心判定，同参数左右/上下对称
"""
from __future__ import annotations

import math

from PIL import Image

TRANSPARENT = (0, 0, 0, 0)
NEIGH4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _rgba(c):
    c = tuple(c)
    if len(c) == 3:
        return (c[0], c[1], c[2], 255)
    return (c[0], c[1], c[2], c[3])


class Canvas:
    """RGBA 像素画布。所有绘制操作逐像素写入，不产生中间透明度。"""

    def __init__(self, w, h):
        self.w = int(w)
        self.h = int(h)
        self.img = Image.new("RGBA", (self.w, self.h), TRANSPARENT)

    # ---------- 基础 ----------
    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.putpixel((x, y), _rgba(c))

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.img.getpixel((int(x), int(y)))
        return TRANSPARENT

    def opaque(self, x, y):
        return self.get(x, y)[3] != 0

    def clear(self):
        self.img = Image.new("RGBA", (self.w, self.h), TRANSPARENT)

    def copy(self):
        c = Canvas(self.w, self.h)
        c.img = self.img.copy()
        return c

    def to_image(self):
        return self.img.copy()

    def save(self, path):
        self.img.save(path)

    @classmethod
    def from_image(cls, img):
        c = cls(*img.size)
        c.img = img.convert("RGBA").copy()
        return c

    # ---------- 线 / 矩形 ----------
    def hline(self, x0, x1, y, c):
        for x in range(int(min(x0, x1)), int(max(x0, x1)) + 1):
            self.px(x, y, c)

    def vline(self, x, y0, y1, c):
        for y in range(int(min(y0, y1)), int(max(y0, y1)) + 1):
            self.px(x, y, c)

    def line(self, x0, y0, x1, y1, c):
        """Bresenham 直线。"""
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.px(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def rect(self, x, y, w, h, c, fill=True):
        x, y, w, h = int(x), int(y), int(w), int(h)
        if fill:
            for yy in range(y, y + h):
                self.hline(x, x + w - 1, yy, c)
        else:
            self.hline(x, x + w - 1, y, c)
            self.hline(x, x + w - 1, y + h - 1, c)
            self.vline(x, y, y + h - 1, c)
            self.vline(x + w - 1, y, y + h - 1, c)

    # ---------- 椭圆 ----------
    def _ellipse_mask(self, cx, cy, rx, ry):
        """返回 {y: (xmin, xmax)}；按像素中心判定，保证整数对称。"""
        rx = max(float(rx), 0.5)
        ry = max(float(ry), 0.5)
        x0 = int(math.floor(cx - rx))
        x1 = int(math.ceil(cx + rx))
        y0 = int(math.floor(cy - ry))
        y1 = int(math.ceil(cy + ry))
        mask = {}
        for y in range(y0, y1 + 1):
            row = []
            for x in range(x0, x1 + 1):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    row.append(x)
            if row:
                mask[y] = (min(row), max(row))
        return mask

    def ellipse(self, cx, cy, rx, ry, c, fill=True):
        """以 (cx, cy) 为中心、半径 rx/ry 的椭圆（可小数，内部判定对称取整）。"""
        mask = self._ellipse_mask(cx, cy, rx, ry)
        for y, (xa, xb) in sorted(mask.items()):
            if fill:
                self.hline(xa, xb, y, c)
            else:
                self.px(xa, y, c)
                self.px(xb, y, c)

    def ellipse_outline(self, cx, cy, rx, ry, c):
        """1px 闭合同心椭圆轮廓（填充集合的边界）。"""
        pts = set()
        for y, (xa, xb) in self._ellipse_mask(cx, cy, rx, ry).items():
            for x in range(xa, xb + 1):
                pts.add((x, y))
        for (x, y) in pts:
            if any((x + dx, y + dy) not in pts for dx, dy in NEIGH4):
                self.px(x, y, c)

    # ---------- 轮廓 ----------
    def outline_in(self, c):
        """内描边：不透明区域中与透明相邻的像素染为 c（闭合一 px 外轮廓）。"""
        pts = [
            (x, y)
            for y in range(self.h)
            for x in range(self.w)
            if self.opaque(x, y) and any(not self.opaque(x + dx, y + dy) for dx, dy in NEIGH4)
        ]
        for x, y in pts:
            self.px(x, y, c)

    def outline_out(self, c):
        """外描边：紧贴不透明区域的透明像素染为 c（不改动主体颜色）。"""
        pts = [
            (x, y)
            for y in range(self.h)
            for x in range(self.w)
            if not self.opaque(x, y) and any(self.opaque(x + dx, y + dy) for dx, dy in NEIGH4)
        ]
        for x, y in pts:
            self.px(x, y, c)

    # ---------- 变换 / 合成 ----------
    def mirror_left_to_right(self):
        """左半水平镜像覆盖右半（奇数宽时中列不动），用于对称造型。"""
        half = self.img.crop((0, 0, self.w // 2, self.h))
        self.img.paste(half.transpose(Image.FLIP_LEFT_RIGHT), (self.w - self.w // 2, 0))

    def shift(self, dx, dy):
        """整体位移，越界丢弃。"""
        base = Image.new("RGBA", (self.w, self.h), TRANSPARENT)
        base.paste(self.img, (int(dx), int(dy)))
        self.img = base

    def paste(self, src, dx=0, dy=0):
        """把另一 Canvas / Image 叠加进来：只复制其不透明像素（不擦除底层）。"""
        simg = src.img if isinstance(src, Canvas) else src.convert("RGBA")
        sw, sh = simg.size
        sp = simg.load()
        for yy in range(sh):
            for xx in range(sw):
                p = sp[xx, yy]
                if p[3] != 0:
                    self.px(dx + xx, dy + yy, p)

    def replace_color(self, old, new):
        """精确色替换（含 alpha 比较）。"""
        old, new = _rgba(old), _rgba(new)
        for y in range(self.h):
            for x in range(self.w):
                if self.img.getpixel((x, y)) == old:
                    self.img.putpixel((x, y), new)
