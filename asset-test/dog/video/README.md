# dog/video — 边牧像素视频（AI 生成 → 像素动画标准化流水线溯源）

> 本目录记录 `asset-test` 的视频标准化案例：AI 生成像素视频 → `pixcli video-std` 标准化。
> 时间：2026-09-06。工具：本仓 `pixel-toolkit/`（`pixcli video-std`，依赖 ffmpeg）。

## 文件清单

| 文件 | 说明 |
|------|------|
| `origin_video.mp4` | **源**：即梦 AI 生成像素视频（1280×720，24fps，8s，192 帧，H.264+AAC，~4.8MB）。与 `../picture/` 图片测试同源（均为 AI 生成边牧） |

> `video-std` 的标准化产物（帧序列/GIF/HTML）为过程产物，本目录不入库
> （可复现：重新运行 `pixcli video-std origin_video.mp4 -o <out>/ --size 64x64` 即可）。

## 视频特征（实测 2026-09-06）

- 内容：边牧 Idle 动画（轻微摆动/转头），深灰背景（约 #343434），角色位于画面中部
- 角色运动范围（全程合并 bbox）：约 (476,166)-(742,546) = 266×380 px
- **网格检测不可靠**：帧间检测 cell 2×4~6×6 乱跳、conf 0.57~0.70——AI 动态视频是平滑运动+深度压缩，
  **无稳定逻辑网格**，因此不能走 `standardize --grid` 网格还原，走 `video-std` 像素化降采样

## 标准化管线（`pixcli video-std`）

1. **抽帧**：ffmpeg 解码 → 原生帧 PNG（默认全帧率，`--fps` 可重采样）
2. **裁剪**：`--crop auto` 全程合并内容 bbox（躲避逐帧裁剪抖动）；`--crop fixed --box` 手动
3. **降采样**：`--size 64x64` 面积平均降采样（无网格时保留每格主色，防摩尔纹）
4. **背景透明化**：`--bg auto` 四角众数 + 边界 4-连通清除（主体包住的高光保留），alpha 两态
5. **量化**：`--colors 16` 跨帧共享色板 OKLab k-means（防闪烁）；`--outline` 时主体量化 k=colors-1 留描边配额
6. **描边**（可选）：`--outline #rrggbb` 1px 内描边（Canvas.outline_in）
7. **输出**：帧序列 `<名>_NN.png` + `<名>.gif` + `<名>.html`（播放器）

## 关键决策记录

1. **降采样而非网格还原**：AI 动态视频无稳定网格（实测证据见上），网格还原不适用；平滑动画→像素图用面积平均。
2. **固定裁剪框**：`auto` 用**全程合并 bbox**（Idle 运动幅度小，固定框帧间稳定），不用逐帧跟踪（避免裁剪抖动）。
3. **色数 ≤16 含描边**：描边时主体量化到 15 色 + 描边 1 色 = 16 色；跨帧合并聚类保证帧间不闪色。
4. **背景透明化在量化前**：背景色不进色板（否则深灰背景占 51% 会吃配额）；连通清除不开洞。
5. **人工门禁**：`pixcli check --size 64x64 --max-colors 16 <帧序列>` 验收（P2 孤立像素提示为边缘碎点，非拦截）；
   `pixcli anim` 看运动数据（面积/帧间 diff 应平稳，无跳变）。

## 复现命令

```bash
# 完整标准化（192 帧全帧，64×64，16 色含描边，透明背景）
python3 pixel-toolkit/pixcli.py video-std asset-test/dog/video/origin_video.mp4 \
    -o <out_dir>/ --size 64x64 --outline '#182b54' --colors 16

# 验收
python3 pixel-toolkit/pixcli.py check --size 64x64 --max-colors 16 <out_dir>/<名>_0*.png
```
