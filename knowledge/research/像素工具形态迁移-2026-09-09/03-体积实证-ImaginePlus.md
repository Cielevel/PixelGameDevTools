---
title: Imagine Plus（xianfei/Imagine-plus）——Tauri 2 重写图像工具，打包体积实证（macOS dmg 4.7–5.3MB）
collected: 2026-09-09
updated: 2026-09-09
tags: [github, tauri, rust, image, cross-platform, tool]
sources:
  - https://github.com/xianfei/Imagine-plus
  - https://github.com/xianfei/Imagine-plus/releases
agent: atlasbrain
status: active
---

# Imagine Plus

### 基本信息
- **GitHub**: [xianfei/Imagine-plus](https://github.com/xianfei/Imagine-plus)
- **Star**: ⭐ 60（采集于 2026-09-09）
- **Fork**: 5
- **License**: MIT（仓库声明；技术栈含 GPL 组件，见下「许可注意」）
- **主要语言**: TypeScript（前端）+ Rust（Tauri 2 外壳与图像管线）
- **创建时间**: 2025-02-13
- **活跃度**: 🔥 高（最近推送 2026-09-02；最新 Release v0.10.4 于 2026-09-02）
- **仓库体积**: 约 8.7MB（`diskUsage`，2026-09-09）

### 功能/用途
图像格式转换 / 压缩 / 批量缩放桌面应用：JPG/PNG/WebP/AVIF/HEIC/BMP 互转，保留元数据、渐进编码、对比模式、批量缩放。项目含两个分支：`master` 为 Electron 版，当前分支为 **Tauri 2 重写版**。

### 体积实证（本条目最有价值的数据；Release v0.10.4 资产实测，采集 2026-09-09）
| 平台/包 | 体积 |
|---|---|
| macOS arm64 .dmg | **4.71MB** |
| macOS x64 .dmg | **5.28MB** |
| Windows x64 setup.exe | **4.54MB** |
| Windows x64 .msi | 6.41MB |
| Windows x64 portable.exe | 18.29MB |
| Linux x64 .deb | 6.11MB |
| Linux x64 .rpm | 6.11MB |
| Linux x64 .AppImage | 83.46MB |

→ 结论：**Tauri 2 的「安装包」可做到 5MB 级**（远低于 Electron 的 100MB+）；但**打包格式影响巨大**（同代码 AppImage 83MB vs deb 6MB），选格式时要实测，不能只看「Tauri 很小」的口号。

### 技术栈（可直接借鉴的 Rust 图像管线）
- 静态链接的 Rust 编解码栈：**mozjpeg**（JPEG，sharp 同款编码器）、**libimagequant**（PNG 调色板量化）、**libwebp**、**ravif/rav1e**（AVIF）、macOS **ImageIO** 解码 HEIC/AVIF（其他平台回退 webview libheif）、**fast_image_resize**（SIMD Lanczos3 缩放）、**img-parts**（EXIF/ICC 元数据保留）。
- 全部编进单一二进制；Node.js 仅构建期（Vite 打包 React UI），**运行期无 Node 运行时**。

### 亮点（为什么值得关注）
- 「Web 前端 + Rust 后端」迁移的**同源对照实验**：同一应用 Electron 版 ~100MB+ vs Tauri 版 ~9MB（README 口径），实际 dmg 4.7–5.3MB。
- 证明了「把重计算搬到 Rust 侧」在图像处理场景完全可行，且能保住 Web 前端的开发效率。
- 打包/发布流程成熟（多平台 Release 资产 + 下载量），可作为路线 A 的工程参考。

### 许可注意
- README 自述使用 **libimagequant**（GPL-3.0-or-later）做调色板量化；仓库自身声明 MIT。**若照抄该技术栈用于闭源分发，需先核对其授权方式**（未验证其实际授权）。替代：`quantette`（Rust 实现）或购买 pngquant 商业授权。

### 来源
- README（`gh api repos/xianfei/Imagine-plus/readme`，采集 2026-09-09）
- Release 资产体积：`gh release view v0.10.4 -R xianfei/Imagine-plus`（采集 2026-09-09）
- 主题出处：`Shelf/game-dev/pixel-tool-form-migration.md`（形态 1）
