---
title: SpriteGrid（marksverdhei）：AI 像素画网格检测 + 鲁棒采样清洗器（CLI/ComfyUI/Python）
collected: 2026-09-06
updated: 2026-09-06
tags: [github, pixel-art, python, image-processing, ai, comfyui]
sources:
  - https://github.com/marksverdhei/spritegrid
  - https://pypi.org/project/spritegrid/
agent: atlasbrain
status: active
---

# deepdive: marksverdhei/spritegrid —— AI 像素画 → 真像素画的信号处理清洗器

> 采集：2026-09-06 GitHub API / README / PyPI；星数会变动。

## 核心数据（采集于 2026-09-06，GitHub API）

- **GitHub**: [marksverdhei/spritegrid](https://github.com/marksverdhei/spritegrid)
- **Star**: ⭐ 5
- **Fork**: 2
- **License**: MIT
- **主要语言**: Python（PyPI 包 `spritegrid`，检出 v0.2.0 为最新 release，2026-09-06）
- **创建时间**: 2025-04-06
- **活跃度**: 中低 — 最近 push 2026-07-10（动画支持 #53 @ 2026-06-28、ANSI half-block #54、降采样向量化 #55）；最近 release 0.2.0；单作者项目
- **依赖**: numpy / scipy / opencv / Pillow（视频走 OpenCV）
- **平台**: Python 3.12+，CLI + Python API + ComfyUI 自定义节点

## 功能/用途

把扩散模型产出的「高分辨率、像素错位、颜色发灰噪」的伪像素画，通过**信号处理恢复真实像素网格**并降采样成干净的单色像素画（true resolution）。比 proper-pixel-art 的 Canny/Hough 路线更偏梯度分析/峰检测；输出对网格对齐良好的输入（如 Flux）效果最佳。

## 算法（README「How It Works」）

1. 梯度分析：算水平/垂直方向梯度剖面
2. 峰检测：SciPy peak detection + 置信度打分，找主导网格间距
3. 网格校验：纵横比 + 置信度阈值，拒绝假网格
4. 幂等检查：输出尺寸==输入则视为已干净（可安全留在工作流里不重复处理）
5. **几何中位数采样**：每个网格单元用 Weiszfeld 算法稳健地聚成一个像素颜色（对单元内 JPEG 色噪/混色鲁棒）
6. 可选量化：颜色位深 4-8（越低色板越紧）

## 亮点（Agent / 用户工具相关性）

- **直接命中「AI 像素图 → 完美标准化」**：网格检测 + 单元内鲁棒采样 + 量化，一条命令 `spritegrid ai.png -o clean.png`
- **动画/多帧**：跨帧聚合梯度剖面检测**一个共享网格**，全部帧用同一网格+色板 → 时间稳定不闪烁（与 proper-pixel-art 的「共享 grid+palette」思路一致）
- **精确输出尺寸**：`--res 32x32` 强制 NEAREST 到目标分辨率、`spritegrid-crop -s 32` 直接切 32×32 精灵、`--aspectratio`、`--center`、`-p` padding —— 对应用户工具的 32/64/128 标准格子需求
- ComfyUI 节点 + pixelated 预览扩展（防浏览器插值糊化）；批处理、ASCII/ANSI 预览、`--symmetric` 水平镜像约束、DBSCAN 背景移除、去背景后 crop
- 幂等设计 = 适合嵌进生成工作流出图后处理（同 proper-pixel-art / pixel-art-fixer 的定位，且更「信号处理」、参数更少）

## 局限/注意

- ⭐ 极少、单作者、活跃度中低：README 自陈「works but not yet flawless」（PyPI 0.1.1 时代页面），生产采用前应实测
- 对「网格已对齐」的输入稳健性最好；生成端配合提示词（低分辨率 512 内、无 AA、透明背景）效果更佳（README Tips）
- 依赖 numpy/scipy/opencv，非零体积；无 torch（比 PixelOE 轻）

## 与 AtlasBrain 相关性

- 与 proper-pixel-art / pixel-art-fixer 同属「生成后清洗」路线第三名候选：网格检测思路不同（梯度 vs Canny/Hough），可对比实测后二选一或互补；值得列入 ThirdPartyLibs 试用候选
- 清洗家族方法论文档：`Shelf/game-dev/ai-pixel-art-standardization.md`（2026-09-06）

## 来源

- README：https://github.com/marksverdhei/spritegrid
- PyPI：https://pypi.org/project/spritegrid/
- ComfyUI 节点目录：https://github.com/marksverdhei/spritegrid/tree/main/src/spritegrid/comfyui
