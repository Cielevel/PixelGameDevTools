# ROADMAP —— 未实施事项（跨组件）

> **用途**：集中记录「分析后确定要做、但尚未实施」的事项，避免散落在对话/提交里丢失。
> **口径**：只留**未做**的；完成一项即移入对应组件的 `CHANGELOG.md` / `README.md` 并从本表删除。
> **记于**：2026-09-09（来源：全仓归类整理 + 扩展方向评估 + 形态迁移定案三轮）。排序按「价值 ÷ 成本」。
> **主线背景**（2026-09-09「像素工具形态迁移」定案）：节点系统三阶段——Phase 0 管线配方（已交付）→ Phase 1 浏览器工作台 + CI/Pages（已交付）→ Phase 2 缓存与编辑面板。
> **历史口径**（2026-09-10）：本仓转公开时干净历史重开仓——本文件及 CHANGELOG 引用的旧提交哈希（`55b3dc9`/`4dd73c2`/`3648b0c` 等）以仓外私有存档的 git bundle 为准，不在当前历史中。

## 已交付（本轮，供追溯）

| 内容 | 说明 |
|---|---|
| 资产清单与审计 | `pixcli manifest` / `audit`（全工程门禁入口），提交 `3648b0c` |
| 交付门禁补全 | 契约 §4.2 判据 4/5、§3 hash 适配层、`check --atlas`；pixel-toolkit `v0.5.0` |
| 管线配方执行器（节点系统 Phase 0） | `pipeline.py` + `pixcli run`/`ops`（17 节点、门禁内联、双 parity 零差异）+ `tests/` 22 例；pixel-toolkit `v0.6.0`（2026-09-09） |
| 节点工作台 Phase 1（浏览器版） | `workbench/` v0.1.0：React Flow 配方画布 + Pyodide 同核执行（运行时自托管）+ node 烟测 + 浏览器实测；`source.video` 桌面限定（2026-09-09） |
| 本仓 CI + Pages 工作流 | `.github/workflows/ci.yml`（pytest + parity_frontend + workbench 构建/烟测）与 `deploy.yml`（Pages）落地；**推送后生效**（私有仓 Pages 需 Pro，转公开后可用） |
| 公开化（转 public） | 2026-09-10 执行：旧历史完整备份（git bundle，仓外私有存档）→ 红线移出（saint11-tutorials / asset-packs / samples / .zcode / .ai-images → 仓外私有存档）→ 文档全面改写（私有表述/构成表/复用步骤/imitator 源库口径）→ LICENSE（MIT）→ 干净历史重开仓。**待用户 force push + GitHub 侧转 public 后生效** |

## 未实施（按优先级）

| # | 事项 | 内容 | 落位 | 量级 |
|---|---|---|---|---|
| 1 | **核心模块单测补全** | pipeline 22 例 + workbench 烟测已入 CI；仍缺 palette/check/stability/atlas/standardize/manifest 各模块的单元覆盖（现靠管线 parity 间接盖到主路径） | `pixel-toolkit/tests/` | 中 |
| 2 | **asset-inspector 后处理对齐** | 孤立像素清除、平涂中值、色阶分配·区域众数、描边颜色/内描边（对齐 `canvas.outline_in`）——video-studio 有、静态图路径没有；**优先做成 pipeline 节点**（Python 核心一次实现，工作台与 CLI 共享） | pipeline 新节点 | 中 |
| 3 | **workbench Phase 2** | 内容寻址缓存与增量重算（配方 sha256 已预留）；MaskEditor 式编辑面板收编均衡笔刷/描边笔刷；预设库（预设=存下来的图）；浏览器视频源（`<video>` seek 抽帧，复用 video-studio 已验证方案） | `workbench/` | 中-大 |
| 4 | **MCP server 壳** | stdio MCP 包装 `pixcli`（子命令/管线配方 → tool），任何 MCP 客户端可直调；接口设计可参考 atelier（勿依赖其实现） | 新 `pixel-toolkit/mcp/` 或独立包 | 小-中 |
| 5 | **引擎导入适配** | 契约 §3「适配层只写一次」的 Unity `.meta`/Sprite Atlas、Godot `.tres`/`.import` 部分（Web 的 `--format hash` 已落地） | 新顶层 `engines/` | 中-大 |
| 6 | **纯程序验证素材** | `generation/README.md` 预留类别：确定性测试卡（色阶渐变 / 1px 棋盘 / alpha 边界 / 9-slice / 网格标定），供回归与 CI 当固定输入 | `pixel-toolkit/generation/verify/` | 小-中 |
| 7 | **调色板阶次生成** | 从锚点色按 OKLab 生成明暗阶并写回 palette `roles`，配合 `style_kit` 明暗带 | `palette.py` + `pixcli ramp` | 小 |
| 8 | **帧率重映射** | 采样资产事后调帧率 / 丢帧补帧（现只有 `video-std --fps` 一次性抽取） | `pixcli retime` | 小 |
| 9 | **pixel-normal 扩展** | 视频/GIF 序列阅览（其 README 自述待扩展）→ 法线驱动重打光 | `experimental/pixel-normal/` | 中 |

## 备查（非待办：口径已固化）

- **契约 §4.2 判据 4 的不可判定性**：对齐特征的原生稿与 k× 放大稿在像素上等价，故只作 P2 提示、需 `--fidelity` 开启——这是口径不是缺口，见契约 §4.2。
- **`pixcli manifest` / `audit` 的 `_NN` 分组歧义**：单图 `xxx_64.png` 会被归入 `xxx` 组（末尾数字一律视作帧号）——既有分组约定，见 `pixel-toolkit/README.md`「约定」。
