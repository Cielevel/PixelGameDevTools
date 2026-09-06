"""sprites 子目录布局约定 —— 资产名前缀决定其子目录（2026-09-03 整理定案）。

与 docs/美术清单.md 章节一一对应：
  player/  玩家（player_*，64×64；2026-09-05 player1 转设 NPC 后暂空置，待重新立项）
  npc/     NPC（npc_*，64×64）
  mob/     敌人（mob_*，小怪 32×32 / 精英 32×48 / Boss 64×64）
  bullet/  武器与弹体（proj_* / wpn_* / ebullet_*）
  fx/      特效（fx_*）
  pickup/  拾取（pick_*）
  icon/    UI 图标（icon_*，32×32）
  base/    风格基准资产（不在清单，如 slime_idle）
新增资产按前缀自动归位；前缀匹配不到时落 base/ 并在交付说明中提示主代理确认。
"""
from __future__ import annotations

import os

PREFIX_DIRS = {
    "player": "player",
    "npc": "npc",
    "mob": "mob",
    "boss": "mob",
    "proj": "bullet",
    "wpn": "bullet",
    "ebullet": "bullet",
    "fx": "fx",
    "pick": "pickup",
    "icon": "icon",
}
FALLBACK_DIR = "base"  # 风格基准 / 清单外资产


def sprite_dir(sprites_root, stem_or_name, makedirs=True):
    """按资产名（stem 或完整文件名）前缀返回其子目录路径。"""
    name = os.path.basename(str(stem_or_name))
    sub = FALLBACK_DIR
    for prefix, dirname in PREFIX_DIRS.items():
        if name.startswith(prefix + "_") or name == prefix:
            sub = dirname
            break
    d = os.path.join(sprites_root, sub)
    if makedirs:
        os.makedirs(d, exist_ok=True)
    return d
