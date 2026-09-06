"""sprites 子目录布局约定 —— 资产名前缀决定其子目录。

PREFIX_DIRS 为典型像素游戏的通用起步默认，按目标工程的资产清单修订
（映射与尺寸档位以工作区 AGENTS.md 为准，见仓库 README「适配清单」）：
  player/  玩家（player_*）
  npc/     NPC（npc_*）
  mob/     敌人（mob_*）
  bullet/  武器与弹体（proj_* / wpn_* / ebullet_*）
  fx/      特效（fx_*）
  pickup/  拾取（pick_*）
  icon/    UI 图标（icon_*）
  base/    风格基准资产（清单外，如 slime_idle）
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
