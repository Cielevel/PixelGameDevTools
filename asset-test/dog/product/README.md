# dog/product — 边牧像素角色产物（标准化最终交付）

> 本目录存放 `video-std` 标准化后的**最终交付物**（sprite sheet），供游戏工程直接接线使用。
> 源追溯见 `../video/README.md`（绿幕源、管线参数、决策记录）；图片标准化溯源见 `../picture/README.md`。

## 产物清单

| 文件 | 规格 | 说明 |
|------|------|------|
| `dog_border_collie_idle_sheet.png` | 7808×64（122 帧 × 64×64，RGBA） | **Idle 动画横向 sprite sheet（朝右/原版）**：绿幕标准化 + 纯黑描边 + 16 色 + 透明背景；12fps 采样（源 24fps 减半），对应源视频 0~10s |
| `dog_border_collie_idle_mirror_sheet.png` | 7808×64（122 帧 × 64×64，RGBA） | **同动画水平镜像版（朝左）**：左右朝向双套动画；帧序、规格与原版完全一致，仅左右对称翻转 |

## 规格（工程规范对齐）

- 单帧：64×64 RGBA，alpha 两态（0/255），透明背景
- 色数：≤16（含纯黑描边 `#000000`；主体 15 色 + 描边 1 色）
- 描边：1px 纯黑闭合内描边（`Canvas.outline_in` 语义）
- sheet：横向，帧宽 = 原生宽（64），命名 `<名称>_sheet.png`
- 源动画：24fps 抽取 → 12fps（122 帧 ≈ 10.1s，循环无缝）；如需 24fps 全帧（240 帧），用 `--fps 24` 复现

## 用途

- **游戏内 Idle 动画**：按帧裁剪逐帧播放；左右朝向引用对应 sheet（朝右 = 原版，朝左 = 镜像版）
- **引擎导入**：sprite sheet 单图 + 帧尺寸 64×64、帧数 122、帧率 12fps 即可接线

## 复现命令

```bash
# ① 标准化（仓库根运行；绿幕源 → 122 帧 64×64 透明背景 16 色黑描边）
python3 pixel-toolkit/pixcli.py video-std asset-test/dog/video/origin_video_greenbg.mp4 \
    -o /tmp/dog_std/ --size 64x64 --outline '#000000' --colors 16

# ② 拼 sheet（原版）
python3 pixel-toolkit/pixcli.py sheet /tmp/dog_std/origin_video_greenbg_*.png \
    -o asset-test/dog/product/dog_border_collie_idle_sheet.png

# ③ 镜像版：先对帧序列做水平翻转（PIL FLIP_LEFT_RIGHT），再同法拼 sheet
```
