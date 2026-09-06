---
title: AI 像素图「完美标准化」：JPEG 有损源 → 干净索引色像素画（流程/规则/工具）
collected: 2026-09-06
updated: 2026-09-06
tags: [pixel-art, image-processing, game-dev, jpeg, tools]
sources:
  - https://github.com/marksverdhei/spritegrid
  - https://github.com/KennethJAllen/proper-pixel-art
  - https://github.com/Retro-Diffusion/pixel-art-fixer
  - https://loopsprite.com/slice/guide-fix-ai-pixel-art.html
  - https://sorceress.games/blog/snap-an-image-to-pixel-art-ai-browser-sprite-ready
  - https://image2pixel.net/jpg-to-pixel-art
  - https://pixelartworkshop.com/guides/identify-ai-pixel-art-tells
  - https://zipic.app/blog/compress-ai-generated-images
  - https://support.google.com/flow/answer/17571126?hl=en
  - https://retrodiffusion.ai/tools/
  - https://www.kokutech.com/tools/demake
  - https://en.wikipedia.org/wiki/Color_quantization
agent: atlasbrain
status: active
---

# AI 像素图「完美标准化」方法论：从 JPEG 有损源到干净像素画

> 采集：2026-09-06。主题（Cielevel 指定）：Google Flow 生成的像素图只能以 JPEG 下载 → 有损压缩让分析工具数出上千种颜色、肉眼却只有十几种；现有「格子压缩 + 近似颜色合并」不完美，求更好的工具/流程/规则。

## TL;DR（核心结论）

1. **最优解在源头**：Google Flow 结构上给 JPEG（下载/导出与官方 Takeout 均 .jpg），若换成同一模型在 Gemini app / Google AI Studio 出图可拿 PNG（4K）——直接消灭 JPEG 噪声。JPEG 已定时才需要下面全套清洗。
2. **顺序即规则**：先**网格还原**（对齐真实像素格）→ 再**调色板量化**，最后**帧规范化/导出**。先减色后对齐网格＝只是得到更少的一堆模糊颜色（loopsprite 原话意）。
3. **对付 JPEG 噪声的正确武器不是事后「颜色合并」，而是网格单元内的鲁棒采样**：每个逻辑像素取单元内**众数 / 几何中位数**（proper-pixel-art、SpriteGrid 做法），JPEG 的 8×8 块色噪与振铃会被统计性地压掉。
4. 输出永远是**无抖动索引色 PNG**（CLUT ≤256 色，常用 16-64）；放大只用 NEAREST。色板跨帧共享（防动画闪烁）。

## 一、问题根源：为什么「上千种 vs 十几种」

- **JPEG 编码本质**：8×8 块 DCT + 量化 + 色度抽样（chroma subsampling），产生块间微色差、硬边「振铃」光晕、颜色渗出边缘 1-2px（image2pixel.net 说明）。
- **量化分不清伪影与细节**：色彩量化（quantization）把每种环/渗色当成值得保留的颜色 → 光晕各占一个色板位、渗边变成一圈错色 fringe（image2pixel.net；pixelartworkshop.com「palette bloat」）。
- **扩散模型本身加码**：即使无 JPEG，AI「像素画」也是高分辨率平滑画再假装像素——AA 软边 + 像素离网（mixels）+ 每逻辑像素内多种近似色（palette explosion；loopsprite guide；pixelartworkshop 的索引色审计法：转 Indexed 若需 256+ 色即 AI 产物）。
- 你的现象 = JPEG 色噪（每个 8×8 块内轻微不同的「同一种颜色」）+ AI 软边渐变 → 逐像素统计上千唯一 RGB；肉眼的「十几种」是网格平均后的感知。

**Google Flow 侧事实（2026-09-06 采集）**：
- 第三方测评称 Flow 把 2K Nano Banana 渲染压成 ~2MB JPEG 下载；同模型 Gemini app 下载为 PNG（zipic.app，第三方断言，非 Google 官方）。
- Google 官方：Flow Takeout 导出 media 文件夹图片为 `.jpg`（[支持页](https://support.google.com/flow/answer/17571126?hl=en)原文：generated or uploaded images (.jpg)）。→ JPEG 是 Flow 的结构性输出，不是操作失误。
- 规避候选（未经本机验证，需自查）：Gemini app / Google AI Studio 同模型 PNG 出图；Flow 内「Download project」格式未在官方文档明确逐条列出（管理页仅视频类给 GIF/视频选项）。

## 二、标准化流水线（推荐顺序 + 依据）

### Step 0 · 源头（能免则免）
- 生成端换 PNG 渠道（见上）；提示词层面：指定「透明/纯色背景、无抗锯齿、低分辨率（512 内）」让网格更干净（SpriteGrid README Tips；sorceress：prompt 加 "centered subject, clean flat background" 一条就省掉背景清理）。

### Step 1 · 网格还原（先于一切；对你=升级「格子压缩」）
AI 的逻辑像素尺寸不均匀且离网，直接按 1k→64 平均降采样会错位采到两个逻辑像素的混合色。两条路：
- **手测法**：数一段纯色长条横跨多少真实像素 → 判定真实分辨率（1024 图上块宽 ~16px ⇒ 真 64×64）；用 **NEAREST** 降采样到该尺寸；斜线若参差说明尺寸猜错，试相邻值（loopsprite guide）。
- **自动检测**：SpriteGrid 梯度剖面 + 峰检测找主导间距、置信度校验、幂等（`spritegrid ai.png -o clean.png`）；proper-pixel-art 走 Canny 边缘 → Hough 直线 → 聚类出网格（`ppa input.png`）；pixel-art-fixer 网页/CLI 亦可。均输出「一逻辑像素 = 一输出像素」的真分辨率图。
- 顺序依据：loopsprite「downscale to the true pixel grid first, before palette」；sorceress「cleanup 在 full source resolution、downscale 之前做」。

### Step 2 · 单元内鲁棒采样（JPEG 噪声吸收点）
每个网格单元取一个代表色：**众数**（proper-pixel-art：cell 内最常见色）或**几何中位数**（SpriteGrid：Weiszfeld 算法，比均值对离群色噪更稳健）。单元内 JPEG 色噪/AA 混色被统计性地忽略——这正是你「格子压缩」可升级的关键：区域平均会被 JPEG 噪拉偏，众数/中位数不会。

### Step 3 · 调色板量化（替代/升级「近似颜色合并」）
1. **先定色数**：单角色精灵 16-32 舒适区（loopsprite）；SpriteGrid 量化位深 4-8（越低越紧）；经典硬件色板 PICO-8 16 / Endesga 32 / Sweetie-16 / NES 54 等可直接当目标（sorceress 八预设；色板源见 Lospec）。
2. **索引色转换、关抖动**：dithering 是敌人——它把噪声当细节撒开（loopsprite）；4-8 色小色板用无抖动，16-54 色才考虑 Floyd-Steinberg（sorceress 规则）。
3. **合并近重复色**：AI 爱给三四个几乎一样的棕 → 手工/脚本坍缩为 1 个（loopsprite 强调 palette swap 时受益）。
4. **映射用感知色距**：最近色匹配建议在 OKLab/CIEDE2000 之类感知空间做，而非 RGB 欧氏（demake 等浏览器转换器宣传 perceptual distance 最近色映射；RGB 近邻易产生可见色差/带状）。
5. **通用量化件**：pngquant（中位切分）、ImageMagick `-colors N` / `-remap palette.png`、Pillow `quantize`（median cut / fast octree）——算法族 median-cut / octree / k-means，见 Wikipedia Color quantization；输出索引色 PNG（CLUT 存色板、像素只存索引，simplesize 说明）。

### Step 4 · 边缘/alpha 硬化（防 halo 进色板）
降采样后仍有 AA 残余环：alpha 阈值（<50% 透明、≥50% 不透明，loopsprite）；或 chroma-key + 多遍边缘清理在降尺度前于全分辨率做（sorceress Auto Edge Chroma——防 AI 软边变成量化后的 fringe）。

### Step 5 · 多帧/批量规范化
- **共享同一网格 + 同一色板**（SpriteGrid 动画模式聚合各帧梯度剖面定一个共享网格；proper-pixel-art 对视频抽帧一次定网格+色板；sorceress temporal-stability pass）——否则同一种阴影色在帧 3 和帧 14 映射到不同色板位 → 闪烁。
- 帧裁剪透明边距 → 统一画布尺寸 → **底部对齐**（脚踩同一 Y，消除走路抖动；漂浮物用中心对齐）（loopsprite）。

### Step 6 · 导出与展示规则
- 索引色 PNG；绝不再存 JPEG；放大永远 NEAREST（`convert x.png -filter point -resize 800% x.png`；SpriteGrid/Pillow `Image.NEAREST`）。
- 目标尺寸：`--res 32x32` 可强制精确输出（SpriteGrid）；你现有的 32/64/128 档位与主流精灵尺寸一致，问题只在采样与配色方法。

## 三、工具矩阵（2026-09-06）

**命令行 / 可注入（本地）**
- SpriteGrid（CLI/Python/ComfyUI）：网格检测+鲁棒采样+量化，一条命令；动画共享网格。档案：ShelfGithub/deepdive/deepdive-marksverdhei-spritegrid.md
- proper-pixel-art（CLI/API，无 torch）：Canny/Hough 网格 + 单元众数；视频共享 grid+palette。档案：ShelfGithub/deepdive/deepdive-kennethjallen-proper-pixel-art.md
- Pixel Art Fixer（多语言实现 + 网页 + 远程 MCP）：纯算法假像素画→真网格。档案：ShelfGithub/deepdive/deepdive-retro-diffusion-pixel-art-fixer.md
- 量化通用件：pngquant / ImageMagick（`-colors`/`-remap`/`-filter point`）/ Pillow quantize
- Aseprite（GUI/headless CLI）：Indexed 模式是手工精修的事实标准。档案：ShelfGithub/deepdive/deepdive-aseprite-aseprite.md

**网页端**
- Retro Diffusion 工具集（color-reducer / pixel-art-fixer 网页版等）：https://retrodiffusion.ai/tools/
- Sorceress True Pixel / Pixel Snap（浏览器，色板预设+抖动模式+帧时间稳定，付费/订阅向）
- demake（kokutech.com/tools/demake）：感知色距映射到 PICO-8/Endesga/自定义 .hex/.gpl 色板，16-512 尺寸档，本地浏览器处理
- loopsprite Sprite Slicer（帧自动裁剪对齐，浏览器本地）
- image2pixel.net（JPG 源注意其「块平均吸收压缩网格」思路）
- beadpattern.net 系（拼豆色板硬约束场景的最近色映射参考，若你的工具面向拼豆/串珠更相关）

**生成端规避**
- Gemini app / Google AI Studio（PNG）；提示词见 Step 0。

## 四、对你现有工具的具体升级建议（推演，非来源断言）

1. **格子压缩**：不要对整图盲平均。先估真实网格（或对好对齐的 AI 输出直接按格采样），每格取**众数/中位数**；这样 JPEG 色噪在压缩同时被吸收，而不是留到后面让「颜色合并」猜。
2. **近似颜色合并 → 量化两步**：①定目标色数（8/16/32/64 档）②在感知空间（OKLab）聚类出调色板后做最近色映射，输出索引色 PNG。JPEG 噪点的正确去处是 Step 2 的鲁棒采样，不是靠合并阈值事后糊。
3. **顺序检查**：你的流程若先合并颜色再压格子，建议对调——先压到标准格、再量化。
4. **可先对照实验**：同一张 JPEG 分别跑 SpriteGrid / proper-pixel-art / 你的工具，比对输出色数与目视质量（候选入 ThirdPartyLibs 试用，尚未实测）。

## 参考来源（2026-09-06 采集）

- SpriteGrid README/算法：https://github.com/marksverdhei/spritegrid
- proper-pixel-art README/算法：https://github.com/KennethJAllen/proper-pixel-art
- Pixel Art Fixer：https://github.com/Retro-Diffusion/pixel-art-fixer
- loopsprite《How to Fix AI-Generated Pixel Art…》：https://loopsprite.com/slice/guide-fix-ai-pixel-art.html
- sorceress《Snap an Image to Pixel Art AI》：https://sorceress.games/blog/snap-an-image-to-pixel-art-ai-browser-sprite-ready
- image2pixel《JPG to Pixel Art》：https://image2pixel.net/jpg-to-pixel-art
- pixelartworkshop《Identify AI Pixel Art Tells》：https://pixelartworkshop.com/guides/identify-ai-pixel-art-tells
- zipic《Compress AI Images》（Flow JPEG 断言）：https://zipic.app/blog/compress-ai-generated-images
- Google Flow Takeout 格式官方说明：https://support.google.com/flow/answer/17571126?hl=en
- Google Flow 资产管理页：https://support.google.com/flow/answer/16935308?hl=en
- Retro Diffusion 工具集：https://retrodiffusion.ai/tools/
- demake：https://www.kokutech.com/tools/demake
- Color quantization（Wikipedia）：https://en.wikipedia.org/wiki/Color_quantization

## 关联档案

- ShelfGithub/deepdive/deepdive-marksverdhei-spritegrid.md（2026-09-06 新）
- ShelfGithub/deepdive/deepdive-kennethjallen-proper-pixel-art.md、deepdive-retro-diffusion-pixel-art-fixer.md、deepdive-kohakublueleaf-pixeloe.md、deepdive-sedthh-pyxelate.md、deepdive-aseprite-aseprite.md
- Shelf/ai/pixel-art-agent-drawing.md（像素画 Agent 方法论）、Shelf/ai/lightweight-injectable-pixel-tools.md
- Shelf/game-dev/frameronin-ai-pixel-platform.md（一站式 AI 像素素材平台）
