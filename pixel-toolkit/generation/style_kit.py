"""风格基准库 —— 源自史莱姆（slime_idle，2026-09-03 定案）的明暗与造型惯例。

供 pixel-artist 复用（效率模式默认、全量模式同样可用），保证系列资产风格一致：
- 光源左上；明暗阶次 shadow → mid → light → highlight（+ glint 亮芯 / 眼神光）
- 轮廓偏移法明暗带：向光源方向采样出界 = 受光；向背光方向出界 = 背光
- 贴地接触阴影（最下 N 行压暗）
- 穹顶剪影：圆凸轮廓的逐行宽度序列，适合软体/圆润怪物与 squash & stretch
- 眼神光：每只眼左上角 1px，闭眼帧也保留（防循环中白点闪没）

用法约定：颜色一律取自角色调色板 `Palette.load(...).roles`（先入板再使用）；
绘制收尾统一 `Canvas.outline_in(roles["outline"])` 形成 1px 闭合内描边。
参考实现：同目录 `gen_slime_idle.py`。新怪物以既有资产为模板，
只改几何与配色参数，不另发明明暗模型。
"""
from __future__ import annotations

import math

# ---- 明暗模型参数（slime 基准值，同类对象可直接沿用，按对象微调走关键字参数） ----
BAND = 2              # 轮廓带检测距离（px）
LIGHT_V = 0.35        # 受光带只出现在竖直参数 v < LIGHT_V 的上部
LIGHT_U = 0.15        # 受光带只出现在水平参数 u < LIGHT_U 的偏左一侧
SHADOW_DIAG_V = -0.35
SHADOW_SIDE_V = 0.15  # 侧向背光带只出现在 v > SHADOW_SIDE_V（右下侧）
BOTTOM_SHADOW = 2     # 贴地接触阴影行数


def dome_widths(w_start, w_full, n_d):
    """穹顶各行宽度：w_start → w_full，偶数步进，大步进靠上（凸穹顶，圆形像素阶梯）。"""
    # 步数必须少于可用步进预算，保证穹顶至少一次大步进（否则收敛成圆锥尖）
    n_d = min(n_d, (w_full - w_start) // 2)
    steps = n_d - 1
    total = (w_full - w_start) // 2
    base = total // steps
    extra = total - base * steps
    deltas = sorted((2 * (base + (1 if i < extra else 0)) for i in range(steps)), reverse=True)
    ws = [w_start]
    for d in deltas:
        ws.append(ws[-1] + d)
    return ws


def body_rows(cx, w, h, w_start, n_d, ground_y):
    """穹顶剪影的逐行 (xl, xr)，水平居中于 cx，底行左右各收 1px（贴地圆角）。

    返回 (rows, y_top)；rows 覆盖 y_top .. ground_y（脚底贴地）。
    """
    dome = dome_widths(w_start, w, n_d)
    widths = dome + [w] * (h - n_d - 1) + [w - 2]
    y_top = ground_y + 1 - h
    rows = []
    for wd in widths:
        half = wd / 2.0
        rows.append((int(math.ceil(cx - half - 1e-9)), int(math.floor(cx + half + 1e-9))))
    return rows, y_top


def shade_body(c, rows, y_top, cx, roles, *, band=BAND, light_v=LIGHT_V, light_u=LIGHT_U,
               shadow_diag_v=SHADOW_DIAG_V, shadow_side_v=SHADOW_SIDE_V,
               bottom_shadow=BOTTOM_SHADOW):
    """标准明暗：mid 填充 + 轮廓偏移受光/背光带 + 贴地接触阴影（光源左上）。

    rows/y_top 来自 `body_rows`；roles 为调色板角色表（shadow/mid/light 必需）。
    """
    h = len(rows)
    y_bot = y_top + h - 1
    cy = (y_top + y_bot) / 2.0
    ry = h / 2.0
    rx = max(xr - xl + 1 for xl, xr in rows) / 2.0

    def row_at(y):
        return rows[y - y_top] if 0 <= y - y_top < h else None

    def op(x, y):
        r = row_at(y)
        return r is not None and r[0] <= x <= r[1]

    for j, (xl, xr) in enumerate(rows):
        y = y_top + j
        v = (y - cy) / ry
        for x in range(xl, xr + 1):
            u = (x - cx) / rx
            lit = (not op(x - band, y - band) or not op(x - band, y)) \
                and v < light_v and u < light_u        # 左上轮廓受光，右上保持中间调
            shade = ((not op(x + band, y + band) or not op(x + band, y)) and v > shadow_diag_v) \
                or (not op(x + band, y) and v > shadow_side_v)
            if j >= h - bottom_shadow:
                col = roles["shadow"]
            elif lit:
                col = roles["light"]
            elif shade:
                col = roles["shadow"]
            else:
                col = roles["mid"]
            c.px(x, y, col)


def highlight_blob(c, cx, y_top, rx, h, roles, *, kx=0.18, ky=0.22, glint=True):
    """左上高光团（随 w/h 缩放）+ 可选白色亮芯，与眼睛/描边保持间隔。"""
    hx = cx - rx * kx
    hy = y_top + h * ky
    hrx = max(1.4, rx * kx)
    hry = max(0.9, h * 0.065)
    c.ellipse(hx, hy, hrx, hry, roles["highlight"])
    if glint:
        c.px(round(hx - hrx * 0.3), round(hy - hry * 0.2), roles["glint"])


def eye_glints(c, left_r, right_l, eye_top, ew, roles):
    """每只眼左上角 1px 眼神光（与左上光源同侧；闭眼帧也保留，防循环白点闪没）。

    left_r / right_l：左眼最右列 / 右眼最左列；ew：眼宽。
    """
    c.px(left_r - ew + 1, eye_top, roles["glint"])
    c.px(right_l, eye_top, roles["glint"])


# ---- 掩码版：任意剪影（非穹顶行表）走同一明暗模型 ----
def rows_to_inside(rows, dy=0):
    """行表 [(y, xl, xr)] -> inside(x, y) 判定（整体可带垂直位移 dy）。

    同 y 多行（如背拱与耳朵）取并集，禁止静默覆盖；产物供 `shade_mask` 使用。
    """
    table = {}
    for y, xl, xr in rows:
        k = y + dy
        if k in table:
            table[k] = (min(table[k][0], xl), max(table[k][1], xr))
        else:
            table[k] = (xl, xr)

    def inside(x, y):
        r = table.get(y)
        return r is not None and r[0] <= x <= r[1]

    return inside


def shade_mask(c, inside, mid, light, shadow, *, band=BAND, bottom_shadow=BOTTOM_SHADOW):
    """`shade_body` 的掩码版：对 c 上全部不透明像素套用轮廓偏移法明暗（光源左上）。

    inside(x, y) -> 剪影判定（可由 `rows_to_inside` 生成）；v/u 以剪影 bbox 归一化。
    """
    xs, ys = [], []
    for y in range(c.h):
        for x in range(c.w):
            if inside(x, y):
                xs.append(x)
                ys.append(y)
    if not xs:
        return
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    rx = max((x1 - x0) / 2.0, 0.5)
    ry = max((y1 - y0) / 2.0, 0.5)
    for y in range(y0, y1 + 1):
        v = (y - cy) / ry
        for x in range(x0, x1 + 1):
            if not inside(x, y):
                continue
            u = (x - cx) / rx
            lit = (not inside(x - band, y - band) or not inside(x - band, y)) \
                and v < LIGHT_V and u < LIGHT_U
            sh = ((not inside(x + band, y + band) or not inside(x + band, y))
                  and v > SHADOW_DIAG_V) \
                or (not inside(x + band, y) and v > SHADOW_SIDE_V)
            if y > y1 - bottom_shadow:
                col = shadow
            elif lit:
                col = light
            elif sh:
                col = shadow
            else:
                col = mid
            c.px(x, y, col)


# ============================================================ 通用绘制基元 ----
# （2026-09-04 自 gen_player.py 原样下沉：玩家形象作废清理，基元为共享设施）
# ---------------------------------------------------------------- 基元 ----
def line_pts(p0, p1):
    """Bresenham 线段上的全部整数点（含两端）。"""
    pts = []
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    return pts


def tube(pts, w):
    """折线加粗为 w×w 方块链 → 像素集合（肢体/围巾）。"""
    s = set()
    lo, hi = -(w // 2), w - w // 2
    for i in range(len(pts) - 1):
        for (x, y) in line_pts(pts[i], pts[i + 1]):
            for ox in range(lo, hi):
                for oy in range(lo, hi):
                    s.add((x + ox, y + oy))
    return s


def rows_to_set(rows, dx=0, dy=0):
    """行表 [(y, x0, x1), ...] → 像素集合（可整体偏移）。"""
    s = set()
    for (y, x0, x1) in rows:
        for x in range(x0, x1 + 1):
            s.add((x + dx, y + dy))
    return s


def paint(c, s, trio):
    """统一明暗：mid 填充；右/下缺邻 → dark；否则左/上缺邻 → light（光源左上）。"""
    mid, light, dark = trio
    for (x, y) in s:
        c.px(x, y, mid)
    for (x, y) in sorted(s):
        if (x + 1, y) not in s or (x, y + 1) not in s:
            c.px(x, y, dark)
        elif (x - 1, y) not in s or (x, y - 1) not in s:
            c.px(x, y, light)


def flat(c, s, col):
    for (x, y) in s:
        c.px(x, y, col)
