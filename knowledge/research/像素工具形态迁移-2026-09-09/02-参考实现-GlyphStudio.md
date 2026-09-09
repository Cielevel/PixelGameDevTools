---
title: GlyphStudio（mcp-tool-shop-org/glyphstudio）——Tauri v2 桌面像素工作室 + 76 工具 MCP server 一体
collected: 2026-09-09
updated: 2026-09-09
tags: [github, pixel-art, tauri, mcp, agents, rust, cross-platform]
sources:
  - https://github.com/mcp-tool-shop-org/glyphstudio
  - https://mcp-tool-shop-org.github.io/glyphstudio/
agent: atlasbrain
status: active
---

# GlyphStudio

### 基本信息
- **GitHub**: [mcp-tool-shop-org/glyphstudio](https://github.com/mcp-tool-shop-org/glyphstudio)
- **Star**: ⭐ 0（采集于 2026-09-09）
- **Fork**: 0
- **License**: MIT
- **主要语言**: TypeScript（含 Rust 后端；Tauri v2 + React + Rust）
- **创建时间**: 2026-03-14
- **活跃度**: 🔥 高（最近推送 2026-09-07；Release v1.0.1 于 2026-09-08、v1.0.0 于 2026-03-18）
- **仓库体积**: 约 4.6MB（`diskUsage`，2026-09-09）

### 功能/用途
面向「像素资产」的桌面工作室（stills / motion / variants / reusable parts / structured output）：绘制、逐帧动画（onion skin、timing holds）、文档变体（方向/姿态）与调色板变体（重映射配色）、可复用部件（part 库 + 跨工程 stamp）、一键 bundle 导出（基础图 + 变体 + 配色变体，文件名模板 `{name}-{variant}-{palette}.png`）。
**关键点：它同时自带一个 MCP server**，把完整的精灵编辑能力暴露给 LLM——与桌面应用共用同一套 domain 逻辑、同一份像素缓冲、同一套 undo/redo。

### 架构（对我们最有参考价值的部分）
- `apps/desktop/`：React + Zustand + HTML Canvas 前端；`src-tauri/` 为 Rust 后端（权威像素缓冲与图层合成、笔画事务与 undo/redo、项目持久化/自动保存/崩溃恢复、导出管线 PNG/sprite sheet/animated GIF/bundle、场景合成引擎含相机与回放）。
- `packages/domain`、`packages/api-contract`（Tauri IPC 类型）、`packages/state`（状态管理 + 光栅操作 + 历史，2,575+ 测试）。
- `packages/mcp-sprite-server`：**Node.js MCP server，76 tools + 6 resources，stdio 传输**，无 React/无浏览器（headless Zustand store，每会话一份），复用与桌面端相同的 `domain` / `state` 代码；可接 Claude Desktop / Claude Code / 任意 MCP 客户端。
- 测试量：README 标注 4,550+ passing。

### 亮点（为什么值得关注）
- **「桌面壳 + Agent 原生」一体化的现成范本**：不是给 GUI 外挂一个 CLI，而是 UI 与 MCP 共用同一领域层——这正是「面向用户与 Agent 友好」最干净的实现方式。
- 与 `PixelGameDevTools` 的跨引擎交付契约（sheet.png + sheet.json + .aseprite + 预览）高度同构：它的 bundle 导出与「变体/配色变体」机制可作为我们导出端的产品化参考。
- 技术选型与路线 A 完全一致（Tauri v2），且演示了 Rust 后端 + Web 前端 + Node MCP 三件套的分层切法。
- 提供 showcase interchange JSON（可导入的规范工程文件），有「结构化产物」意识。

### 风险 / 未验证
- ⭐0、fork 0、组织新，**无社区验证**；不宜直接生产依赖，只作设计参考。
- 是否支持读写 `.aseprite` 未见说明（未验证）；是否与我们既有 Aseprite JSON Hash 契约兼容需实测。
- 各平台分发/签名细节未在 README 体现（未验证）。

### 来源
- README（`gh api repos/mcp-tool-shop-org/glyphstudio/readme`，采集 2026-09-09）
- 落地页：https://mcp-tool-shop-org.github.io/glyphstudio/
- 主题出处：`Shelf/game-dev/pixel-tool-form-migration.md`（形态 1 / 形态 7）
