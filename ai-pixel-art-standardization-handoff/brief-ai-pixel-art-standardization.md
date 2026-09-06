# AI 像素图「完美标准化」测试交接简报

> 采集/整理：2026-09-06 · AtlasBrain（Hermes profile: atlasbrain）
> 用途：交给其他 Agent 做工具实测/评估（场景、事实、规则、候选工具、测试建议均已自包含）
> 包内另有两份完整归档原件可作深挖参考。

## 0. 场景与痛点

- Google Flow 生成像素图**只能下载 JPEG**（有损），分析工具数出上千种唯一颜色，肉眼只有十几种。
- 现有工具已提供：格子压缩（1K 图压到 32/64/128 等标准尺寸）+ 近似颜色合并，但效果不完美。
- 目标：找到/验证「把 AI 生成的像素图片完美标准化」的工具/流程/规则。

## 1. 关键事实（2026-09-06 采集）

1. **Google Flow 出 JPEG 是结构性的**：官方 Takeout 说明图片导出为 `.jpg`（support.google.com/flow/answer/17571126）；第三方测评称 Flow 把 2K Nano Banana 渲染压成 ~2MB JPEG，同模型在 Gemini app 下载为 PNG（zipic.app，第三方断言）。
2. **上千种 vs 十几种的根源**：JPEG = 8×8 块 DCT + 量化 + 色度抽样 → 块间微色差、硬边振铃、颜色渗边；色彩量化分不清伪影与细节，每个光晕/渗色各占一个色板位。AI 像素画本身还有 AA 软边、像素离网（mixels）、palette bloat。
3. **顺序即规则**：先网格还原 → 再调色板量化 → 最后帧规范化/导出。先减色后对齐网格 = 只是得到更少的一堆模糊颜色。
4. **对付 JPEG 噪声的正确武器**：网格单元内**鲁棒采样**（众数/几何中位数）而非区域平均——JPEG 色噪在降采样同时被统计吸收。

## 2. 标准化流水线（推荐流程）

- **Step 0 源头**：能换 PNG 渠道就换（Gemini app / Google AI Studio）。生成端提示词：透明或纯色背景、无抗锯齿、低分辨率（512 内）→ 网格更干净。
- **Step 1 网格还原（先于一切）**：AI 的逻辑像素不均匀且离网，盲平均会采到混合色。
  - 手测：数纯色长条跨多少真实像素（1024 图上块宽 ~16px ⇒ 真 64×64），NEAREST 降采样，斜线参差就试相邻尺寸。
  - 自动：SpriteGrid（梯度剖面+峰检测+置信度校验+幂等）、proper-pixel-art（Canny→Hough→聚类网格）、Pixel Art Fixer。
- **Step 2 单元内鲁棒采样**：每格取众数（proper-pixel-art）或几何中位数/Weiszfeld（SpriteGrid）。
- **Step 3 调色板量化**：定色数（单精灵 16-32 舒适；硬件色板 PICO-8 16 / Endesga 32 可作目标）→ 索引色转换、**关抖动** → 近重复色坍缩合并 → 最近色映射建议用**感知色距（OKLab/CIEDE2000）**而非 RGB 欧氏。通用件：pngquant、ImageMagick `-colors N`/`-remap p.png`、Pillow quantize。
- **Step 4 边缘硬化**：alpha 阈值（<50% 透明）或 chroma-key 全分辨率清理，防 halo 进色板变 fringe。
- **Step 5 多帧规范化**：全部帧共享同一网格 + 同一色板（防闪烁）；裁透明边距→统一画布→底部对齐（地面角色）。
- **Step 6 导出**：索引色 PNG；绝不二次 JPEG；放大只用 NEAREST（`convert x.png -filter point -resize 800% x.png`）。

## 3. 候选工具（供实测对比）

命令行/本地：
- **SpriteGrid** — `pip install spritegrid`；`spritegrid ai.png -o clean.png`（网格检测+几何中位数+量化位深 4-8、幂等、`--res 32x32` 强制精确尺寸、`spritegrid-crop -s 32` 切精灵、动画共享网格、ComfyUI 节点）。⭐5/MIT/最近 push 2026-07，README 自陈 not flawless → 需实测。
- **proper-pixel-art** — `pip install proper-pixel-art`；`ppa input.png -c 16`（Canny/Hough 网格+格内众数，无 torch，12k+ 下载，⭐515）。
- **Pixel Art Fixer** — 纯算法假像素→真网格（多语言实现 + 网页版 retrodiffusion.ai + 远程 MCP）。
- 量化通用件：pngquant / ImageMagick / Pillow。

网页端：Retro Diffusion tools（color-reducer）、Sorceress True Pixel/Pixel Snap、demake（kokutech.com，感知色距+自定义 .hex/.gpl 色板）、loopsprite Sprite Slicer（帧对齐）。

## 4. 对「现有工具」的升级建议（推演）

1. 格子压缩：先估真实网格，每格取众数/中位数（JPEG 噪声在压缩时吸收），不要整图盲平均。
2. 近似颜色合并 → 改成两步量化：定目标色数（8/16/32/64）→ 感知空间（OKLab）聚类出调色板 → 最近色映射 → 索引色 PNG。
3. 顺序检查：先压格子、后减颜色（勿反）。

## 5. 建议测试协议

- 同一张 JPEG 像素图样本，分别跑：SpriteGrid（默认参数 + `-q` 调低）、proper-pixel-art（`-c 8/16/32`）、Pixel Art Fixer、以及现有工具。
- 对比指标：输出唯一颜色数、目视质量（边缘是否硬、是否 fringe）、网格对齐（放大 NEAREST 看）、是否幂等、速度/依赖体积。
- 动画样本：验证跨帧共享网格/色板不闪烁。

## 6. 主要来源（2026-09-06）

- https://github.com/marksverdhei/spritegrid
- https://github.com/KennethJAllen/proper-pixel-art
- https://github.com/Retro-Diffusion/pixel-art-fixer
- https://loopsprite.com/slice/guide-fix-ai-pixel-art.html
- https://sorceress.games/blog/snap-an-image-to-pixel-art-ai-browser-sprite-ready
- https://image2pixel.net/jpg-to-pixel-art
- https://pixelartworkshop.com/guides/identify-ai-pixel-art-tells
- https://zipic.app/blog/compress-ai-generated-images
- https://support.google.com/flow/answer/17571126 （Flow Takeout: images (.jpg)）
- https://retrodiffusion.ai/tools/ · https://www.kokutech.com/tools/demake
- https://en.wikipedia.org/wiki/Color_quantization

## 7. 包内完整归档原件（AtlasBrain 知识库）

- `shelf-ai-pixel-art-standardization.md` ← Shelf/game-dev/ai-pixel-art-standardization.md（方法论全文）
- `deepdive-marksverdhei-spritegrid.md` ← ShelfGithub/deepdive/deepdive-marksverdhei-spritegrid.md（repo 档案）
