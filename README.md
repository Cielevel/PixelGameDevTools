# PixelGameDevTools —— 像素游戏工具/参考库

> **定位：纯净的像素游戏美术工具与参考库**——只含项目无关的工具代码、通用流程与参考资料，不与任何具体游戏工程的内容耦合。开源（MIT），欢迎自取。
> 2026-09-06 自 DeepTideSurvivors（深潮幸存者）工程抽离为独立仓库，抽离后已剥离全部源工程专属内容（基准档位/资产名/工程文档引用）；2026-09-10 转公开：干净历史重开仓（此前演进史以 git bundle 私有存档，红线内容不随仓分发）。

## 构成

| 目录 | 内容 |
|---|---|
| `pixel-toolkit/` | pixcli 像素美术 CLI 与核心库（Python 3 + Pillow，唯一第三方依赖）。共用基础库：`palette`（调色板 JSON、量化归板、alpha 两态）/ `anim`（帧 IO、sprite sheet 拼切、GIF/自包含 HTML 播放器、洋葱皮检查图）/ `check`（程序化门禁：尺寸/alpha/色数/对齐/动画一致性/连通域）/ `stability`（时间稳定性判据：静态格/核心静态格帧间变色率 + 单格平均色数）/ `atlas`（sprite sheet ↔ Aseprite JSON 一致性门禁）/ `layout`（sprites 子目录布局约定）/ `manifest`（资产清单与审计：扫描目录 → manifest.json/md + 单 HTML 看板，`audit` 聚合 check/atlas 门禁）；`video.py` 与 `video-studio.html` 管线含**时间平滑**（压帧间闪烁；默认由时间众数稳定承担：`--stabilize` 3 帧、量化前中值 `--temporal` 默认关）并导出 `_sheet.png`+`_sheet.json`；`generation/` 为**纯程序化生成素材方案**独立类别（`canvas` 逐像素绘制基元 / `style_kit` 明暗与造型风格基准库 / `gen_*.py` 生成脚本，按约定自建）；`pipeline.py` + `pixcli run`/`ops` 为**管线配方执行器**（节点系统 Phase 0：线性 stage JSON 确定性执行，17 节点含内联门禁，与既有 CLI 逐像素零差异，`tests/` 22 例回归、`examples/` 示例配方）；`README.md` 为完整命令文档 |
| `workbench/` | **像素管线节点工作台（浏览器版，节点系统 Phase 1，2026-09-09）**：React Flow 画布编辑管线配方 JSON，**Pyodide 加载 pixel-toolkit 同一份源码**在浏览器执行（一核两宿主：与 `pixcli run`/CI 逐字节同产物；处理全在本地，素材不上传，Pyodide 运行时自托管零外部请求）；节点面板由 `pixcli ops` 注册表驱动；导出 JSON 交 `pixcli run` 复现；GitHub Actions 构建部署 Pages（`.github/workflows/`）。见其 `README.md` |
| `asset-inspector/` | 素材处理与验收工具（纯静态单 HTML，双击即用，离线，Win/macOS）：接收图片 / GIF / 视频素材——尺寸档位合规检查（档位表可自定义、tile 整除、整数倍缩放适配）、**结构与帧组验收**（连通域/孤立像素/脚底对齐，对齐 `pixcli check`）、颜色提取罗列与近似色合并（阈值可调）+ 最近邻缩格 + 保存 PNG、**工程调色板载入与归板**（`assets/palettes/*.json`，OKLab 最近色）、**队列批量处理/导出（ZIP）**、自动描黑边（附加/转换，非破坏层）+ 描边笔刷 + 均衡笔刷（残点修复）、GIF/视频逐帧检视、像素级取色、导出工程调色板 JSON（与 pixel-toolkit 调色板格式一致） |
| `scene-previewer/` | 场景预览台（纯静态单 HTML，双击即用）：tilemap + sprite 摆位、分层帧动画（本体层+配件层同钟合成）播放、整数倍最近邻缩放、踩格线——素材「游戏内比例实感」的正式视检环境，避免放大看图的认知偏差；底部 SCENE 数据即接入点 |
| `agent-pipeline/` | ZCode 多 agent 像素美术流水线（8 个 agent + shared 公共基线）：artist/reviewer 效率版与全量版、loop-reviewer（循环动画专项）、imitator+reviewer（有源参考的模仿绘制）、quick（形象设计快稿）；`shared/` 收拢共同约定（像素资产约定/技法纪律/审查框架/**资产来源路线 authored·sampled 分流口径**），**agent 定义只含各自差量，改基准只改 AGENTS.md 一处**；外加 pixcli skill（工具速查与门禁判读） |
| `templates/` | `pixel-art-repro.yml`：GitHub Actions 资产可复现 workflow（重跑全部 gen 脚本 → 与在盘资产逐像素 diff → `pixcli audit` 全量门禁）；`gitattributes`：PNG/GIF 等一律 binary 防换行归一化误伤；`gitignore-pixel-game`：本类工程的 .gitignore 起步模板 |
| `knowledge/` | 方法论与参考资料（**带 `README.md` 索引，标注现行/已实施/归档**）：《像素法则》（Saint11 教学方法提炼，**含版权口径说明**）、《参考图生成约束》、《即梦生图-Mac自动化手册》、《路径与部署映射》（**本仓路径 ↔ 部署路径**，读文档前先看它）、像素视频两篇（工具改进方案含未采纳路线附录 / 高清素材路线评估）；`standardization/` AI 标准化交接包归档、`research/` 3 项调研（**2026-09-09 形态迁移调研包——「一核两宿主」节点系统路线的定案依据，已采纳** + 2026-09-03 两篇通用调研） |
| `experimental/` | 实验级功能孵化区（**原型阶段，不构成稳定承诺**）：主线工具链之外的实验，各子目录自包含、独立演化（`pixel-normal/`——像素法线实验室，P0 查看器 + P1 转换器 + P2 距离场 bevel/调色板感知光照 + P2 批处理全部实现；`standardization-bench/`——AI 标准化对照实验工装，历史存档） |

> **未实施事项**：跨组件待办集中记在根 `ROADMAP.md`（只留未做的；完成一项即移入对应组件的 `CHANGELOG.md`/`README.md` 并从该文件删除）。

## 版本表（2026-09-08 统一格式）

| 组件 | 版本 | 说明 |
|---|---|---|
| `pixel-toolkit/`（pixcli 与核心库） | `v0.6.0` | **管线配方**（`pipeline.py` + `pixcli run`/`ops`，节点系统 Phase 0：17 节点线性 stage JSON、门禁内联、与既有 CLI 逐像素零差异、`tests/` 22 例回归）；此前：资产清单/审计（`pixcli manifest` / `audit`）+ 交付门禁补全（契约 §4.2 判据 4/5、§3 hash 适配层、`check --atlas`）；完成项与实测见 `pixel-toolkit/CHANGELOG.md` |
| `video-studio.html`（视频工作台） | `v2.1.0` | 时间平滑（时间维中值默认关 + 后处理·时间稳定默认 3 帧众数）+ 稳定性读数 + `_sheet.json`（含来源路线）+ 可选后处理（色阶分配/平涂/孤立清除）+ 原生网格检测重采样 |
| `asset-inspector.html`（静态像素工作台） | `Chaos v0.4.0` | 归板 + 批量导出 + 结构/帧组验收 + sheet/JSON 导出（缩格保留 alpha）+ 均衡笔刷（绿幕/蓝幕残点逐像素均衡修复，吸附已有色，参数调整自动重放） |
| `scene-previewer/scene.html` | `v0.1.0` | 首次登记 |
| `workbench/`（节点工作台·浏览器版） | `v0.1.0` | 首版：React Flow 配方画布 + Pyodide 同核执行（自托管运行时）+ 产物下载；`source.video` 桌面限定；实测记录见其 README |
| `experimental/pixel-normal/pixel-normal.html` | `v0.2.0` | P0–P2 全实现（P2 批处理已完成） |

口径：语义版本 `vMAJOR.MINOR.PATCH`；版本号只表示**各自迭代轮次**，不跨组件比较。此前 video-studio 记 `v1.8`、asset-inspector 记 `Chaos_0.1.0/0.2.0`，2026-09-08 整理时统一格式。

## 复用步骤（接入新游戏工程）

1. 拷贝工具链到新工程：
   - `pixel-toolkit/` → 新工程 `tools/pixelart/`
   - `agent-pipeline/agents/` → 新工程 `.zcode/agents/`；`agent-pipeline/shared/` → 新工程 `.zcode/agents/shared/`；`agent-pipeline/skills/pixcli/` → 新工程 `.zcode/skills/pixcli/`
   - 方法论文档 `knowledge/像素法则.md`、`参考图生成约束.md`、`即梦生图-Mac自动化手册.md` → 新工程 `docs/`（agent 定义按 `docs/` 路径引用）
2. 模板包**自备**：imitator 系 agent 以「有源参考的模板包」为动作源——将你自有/购得的模板包放入新工程 `assets/template/`（本仓不分发任何第三方资产包；「借动作不借皮」，成品须是按工程形象重绘的自产资产）
3. 按 `templates/` 落 `.gitattributes` / `.gitignore`；需要 CI 资产门禁时启用 `templates/pixel-art-repro.yml`（落位与调整见 `templates/README.md`）
4. 在新工程 `AGENTS.md` 里定基准（tile 像素密度 / 尺寸档位 / 视角与朝向 / 帧数指引 / 调色板与目录 / 画面方向）——这是 shared 约定、`layout.py` 前缀映射、各 agent 审查单与 CI 门禁的**唯一基准输入；改基准只改 AGENTS.md 一处**
5. 首个风格基准资产定案后，把明暗造型参数沉淀进 `generation/style_kit.py`，后续资产全部复用

> **路径口径**：以上「新工程路径」与「本仓路径」的完整对照见 `knowledge/路径与部署映射.md`；`experimental/`、`knowledge/research|standardization/` **不部署**（只服务本仓）。

## 适配清单（项目耦合点）

- **`pixel-toolkit/layout.py`**：前缀映射表（player/npc/mob/bullet/fx/pickup/icon/base）为通用起步默认，按新工程资产清单修订 docstring 与映射表
- **`scene-previewer/scene.html`**：底部 SCENE 数据为最小示例占位（指向不存在的资产会显示加载失败），接入时替换为目标工程资产路径
- **`pixel-toolkit/generation/`**：生成脚本一律落部署后的 `tools/pixelart/generation/`；按 `generation/README.md` 的骨架与约定自建（调色板先入板、重跑=资产、一源双产出），输出路径按新工程调整
- **`templates/pixel-art-repro.yml`**：触发 paths 与 `assets/sprites/*/` 门禁循环按新工程目录调整

## 许可

- 代码与文档：**MIT**（见 `LICENSE`）
- `knowledge/像素法则.md` 是对 Saint11（Pedro Medeiros）公开教学的**方法论提炼转述**（口径见该文头部）——方法与规则本身不受版权保护，但请尊重原作者、引用时注明出处（[saint11.art](https://saint11.art)）；教程卡原图不随本仓分发
- 本仓不含任何具体游戏的美术资产、调色板 JSON 与正式 gen_* 脚本；使用第三方模板包产出的成品，其再分发边界以你的购买渠道条款为准

## 与源工程的关系

单向快照：2026-09-06 自 DeepTideSurvivors 抽离（对应源版本 commit `146da45`），抽离后已剥离全部源工程专属内容，本仓独立演进、不回写源工程；源工程已转纯本地存档（远端解除关联，完整历史以 git bundle 快照备份）。
