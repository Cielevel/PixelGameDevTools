# PixelGameDevTools —— 像素游戏工具/参考库（私有）

> **定位：纯净的像素游戏美术工具与参考库**——只含项目无关的工具代码、通用流程与参考资料，不与任何具体游戏工程的内容耦合。私有仓：个人使用、不公开。
> 2026-09-06 自 DeepTideSurvivors（深潮幸存者）工程抽离为独立仓库，抽离后已剥离全部源工程专属内容（基准档位/资产名/工程文档引用）。

## 构成

| 目录 | 内容 |
|---|---|
| `pixel-toolkit/` | pixcli 像素美术 CLI 与核心库（Python 3 + Pillow，唯一第三方依赖）。共用基础库：`palette`（调色板 JSON、量化归板、alpha 两态）/ `anim`（帧 IO、sprite sheet 拼切、GIF/自包含 HTML 播放器、洋葱皮检查图）/ `check`（程序化门禁：尺寸/alpha/色数/对齐/动画一致性/连通域）/ `layout`（sprites 子目录布局约定）；`generation/` 为**纯程序化生成素材方案**独立类别（`canvas` 逐像素绘制基元 / `style_kit` 明暗与造型风格基准库 / `gen_*.py` 生成脚本，按约定自建）——后续「纯程序验证素材」功能将与此类别并列；`README.md` 为完整命令文档 |
| `scene-previewer/` | 场景预览台（纯静态单 HTML，双击即用）：tilemap + sprite 摆位、分层帧动画（本体层+配件层同钟合成）播放、整数倍最近邻缩放、踩格线——素材「游戏内比例实感」的正式视检环境，避免放大看图的认知偏差；底部 SCENE 数据即接入点 |
| `asset-inspector/` | 素材处理与验收工具（纯静态单 HTML，双击即用，离线，Win/macOS）：接收图片 / GIF / 视频素材——尺寸档位合规检查（档位表可自定义、tile 整除、整数倍缩放适配）、颜色提取罗列与近似色合并（阈值可调）+ 最近邻缩格 + 保存 PNG、自动描黑边（附加/转换，非破坏层）+ 描边笔刷、GIF/视频逐帧检视、像素级取色、导出工程调色板 JSON（与 pixel-toolkit 调色板格式一致） |
| `agent-pipeline/` | ZCode 多 agent 像素美术流水线（8 个 agent + shared 公共基线）：artist/reviewer 效率版与全量版、loop-reviewer（循环动画专项）、imitator+reviewer（有源参考的模仿绘制）、quick（形象设计快稿）；`shared/` 收拢共同约定（像素资产约定/技法纪律/审查框架），**agent 定义只含各自差量，改基准只改 AGENTS.md 一处**；外加 pixcli skill（工具速查与门禁判读） |
| `asset-packs/` | 已购第三方模板资产包（只读参考，「借动作不借皮」的源库）：`top-down-asset-pack/`（俯视 64×64 格动作包，idle/walk/run/attack × 8 朝向）、`2d-pixel-art-character-template/`（48×48 侧视动作模板包）；规格与许可边界见包内 README |
| `templates/` | `pixel-art-repro.yml`：GitHub Actions 资产可复现 workflow（重跑全部 gen 脚本 → 与在盘资产逐像素 diff → pixcli 结构门禁）；`gitattributes`：PNG/GIF 等一律 binary 防换行归一化误伤；`gitignore-pixel-game`：本类工程的 .gitignore 起步模板 |
| `knowledge/` | 方法论与参考资料：《像素法则》（Saint11 教学方法提炼，**含版权口径说明**）、《参考图生成约束》（生图 AI → 像素转换管线）、《即梦生图-Mac自动化手册》（参考图机器通路）、`research/` 2 篇通用调研（像素画 agent 生态 / 轻量像素工具）；`saint11-tutorials/` 教程卡原图归档（80 张，随本仓 git 入库——**本仓私有不公开**，使用边界见其 README） |
| `experimental/` | 实验级功能孵化区（**原型阶段**）：主线工具链之外的实验，各子目录自包含、独立演化；**即便日后拆出独立成仓亦为私有库，本工具链仅自用/自研发，不对外发布**（当前 `pixel-normal/`——像素法线实验室：P0 光照查看器 + P1 高度图转法线已实现，P2 实验项待做） |

## 复用步骤（接入新游戏工程）

1. 拷贝工具链到新工程：
   - `pixel-toolkit/` → 新工程 `tools/pixelart/`
   - `agent-pipeline/agents/` → 新工程 `.zcode/agents/`；`agent-pipeline/shared/` → 新工程 `.zcode/agents/shared/`；`agent-pipeline/skills/pixcli/` → 新工程 `.zcode/skills/pixcli/`
   - 方法论文档 `knowledge/像素法则.md`、`参考图生成约束.md`、`即梦生图-Mac自动化手册.md` → 新工程 `docs/`（agent 定义按 `docs/` 路径引用）
2. 模板包按需取用：`asset-packs/` 所需包拷贝（或软链）到新工程 `assets/template/`，imitator 系 agent 从该路径取源
3. 按 `templates/` 落 `.gitattributes` / `.gitignore`；需要 CI 资产门禁时启用 `templates/pixel-art-repro.yml`
4. 在新工程 `AGENTS.md` 里定基准（tile 像素密度 / 尺寸档位 / 视角与朝向 / 帧数指引 / 调色板与目录 / 画面方向）——这是 shared 约定、`layout.py` 前缀映射、各 agent 审查单与 CI 门禁的**唯一基准输入；改基准只改 AGENTS.md 一处**
5. 首个风格基准资产定案后，把明暗造型参数沉淀进 `generation/style_kit.py`，后续资产全部复用

## 适配清单（项目耦合点）

- **`pixel-toolkit/layout.py`**：前缀映射表（player/npc/mob/bullet/fx/pickup/icon/base）为通用起步默认，按新工程资产清单修订 docstring 与映射表
- **`scene-previewer/scene.html`**：底部 SCENE 数据为最小示例占位（指向不存在的资产会显示加载失败），接入时替换为目标工程资产路径
- **`pixel-toolkit/generation/`**：生成脚本一律落部署后的 `tools/pixelart/generation/`；按 `generation/README.md` 的骨架与约定自建（调色板先入板、重跑=资产、一源双产出），输出路径按新工程调整
- **`templates/pixel-art-repro.yml`**：触发 paths 与 `assets/sprites/*/` 门禁循环按新工程目录调整
- **`asset-packs/`**：第三方购买资产，对外再分发边界以购买渠道条款为准

## 红线与许可

- 本仓为**私有参考库**：个人使用、不公开。`knowledge/saint11-tutorials/`（Saint11 教程卡原图，原站未标注开放许可）随仓入库的依据是私有学习用途；**转公开、推送公开远端或对外分发前，必须先移出该目录**——边界详见其 README
- `asset-packs/` 为用户购买所得，拥有使用权利；原包不得对外再发布，成品游戏分发的是基于它重绘的工程自产资产
- `knowledge/像素法则.md` 是对 Saint11（Pedro Medeiros）公开教学的方法论提炼转述（口径见该文头部）；本包不含任何具体游戏的美术资产、调色板 JSON 与正式 gen_* 脚本

## 与源工程的关系

单向快照：2026-09-06 自 DeepTideSurvivors 抽离（对应源版本 commit `146da45`），抽离后已剥离全部源工程专属内容，本仓独立演进、不回写源工程；源工程已转纯本地存档（远端解除关联，完整历史以 git bundle 快照备份）。
