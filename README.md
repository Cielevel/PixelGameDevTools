# PixelGameDevTools —— 像素游戏美术生产工具链（可复用资产包）

> 2026-09-06 自 DeepTideSurvivors（深潮幸存者）工程抽离，落位为源工程同级目录的**独立复用资产仓库**；对应源版本 commit `146da45`（抽离时快照另存于源仓 git 历史 `61ed497` 的 `reusable/` 路径，可溯）。
> 只含**项目无关**的代码、工具与方法论文档；**不含任何美术资产、调色板、gen_* 生成脚本与第三方模板**（这些留在源工程本地仓库存档）。
> 文件内容与源工程保持一致未做删改，项目耦合点统一收在下方「适配清单」。

## 构成

| 目录 | 内容 | 来源 |
|---|---|---|
| `pixel-toolkit/` | pixcli 像素美术 CLI 与核心库（Python 3 + Pillow，唯一第三方依赖）：`canvas`（逐像素绘制基元，无抗锯齿）/ `palette`（调色板 JSON、量化归板、alpha 两态）/ `anim`（帧 IO、sprite sheet 拼切、GIF/自包含 HTML 播放器、洋葱皮检查图）/ `check`（程序化门禁：尺寸/alpha/色数/对齐/动画一致性/连通域）/ `layout`（sprites 子目录布局约定）/ `style_kit`（明暗与造型风格基准库）；`README.md` 为完整命令文档；`examples/gen_slime_idle.py` 为风格基准资产的完整生成脚本范例 | `tools/pixelart/` |
| `scene-previewer/` | 场景预览台（纯静态单 HTML，双击即用）：tilemap + sprite 摆位、分层帧动画（本体层+配件层同钟合成）播放、整数倍最近邻缩放、踩格线——素材「游戏内比例实感」的正式视检环境，避免放大看图的认知偏差 | `tools/scene/scene.html` |
| `agent-pipeline/` | ZCode 多 agent 像素美术流水线定义（8 个 agent）：artist/reviewer 效率版与全量版、loop-reviewer（循环动画专项）、imitator+reviewer（有源参考的模仿绘制）、quick（形象设计快稿）；外加 pixcli skill（工具速查与门禁判读） | `.zcode/agents/`、`.zcode/skills/pixcli/` |
| `templates/` | `pixel-art-repro.yml`：GitHub Actions 资产可复现 workflow（重跑全部 gen 脚本 → 与在盘资产逐像素 diff → pixcli 结构门禁）；`gitattributes`：PNG/GIF 等一律 binary 防换行归一化误伤；`gitignore-pixel-game`：本类工程的 .gitignore 起步模板 | 源工程同名文件 |
| `knowledge/` | 方法论与调研沉淀：`像素法则.md`（Saint11 教学方法提炼，**含版权口径说明**）、`参考图生成约束.md`、`即梦生图-Mac自动化手册.md`、`research/` 3 篇调研总结（像素画 agent 生态 / 工程分析与工作流 / 轻量像素工具） | `docs/` |

## 复用步骤（新工程）

1. 拷贝本目录到新工程（整个目录自包含，可整取或按需取子目录）：
   - `pixel-toolkit/` → 新工程 `tools/pixelart/`
   - `agent-pipeline/agents/` → 新工程 `.zcode/agents/`；`agent-pipeline/skills/pixcli/` → 新工程 `.zcode/skills/pixcli/`
2. 按 `templates/` 落 `.gitattributes` / `.gitignore`；需要 CI 资产门禁时启用 `templates/pixel-art-repro.yml`
3. 在新工程 `AGENTS.md` 里定基准（tile 像素密度 / 资产尺寸档位 / 视角与朝向 / 动画帧数指引）——这是 `layout.py` 子目录映射、各 agent 审查单与 CI 门禁的共同输入
4. 过一遍下方「适配清单」，替换项目耦合点
5. 首个风格基准资产（建议从 slime 类软体圆物起步）定案后，把明暗造型参数沉淀进 `style_kit.py`，后续资产全部复用

## 适配清单（项目耦合点）

- **路径约定**：工具链与文档默认相对仓库根运行，涉及 `tools/pixelart/`、`assets/sprites/`、`assets/palettes/`、`previews/`；路径变更需同步 `pixel-toolkit/README.md`、`agent-pipeline/skills/pixcli/SKILL.md`、`templates/pixel-art-repro.yml`
- **`pixel-toolkit/layout.py`**：子目录划分（player/npc/mob/bullet/fx/pickup/icon/base）与名称前缀映射源自源工程 `docs/美术清单.md` 的章节结构；新工程清单结构不同则改其 docstring 与映射表
- **措辞**：`SKILL.md` 及部分 agent 定义（pixel-quick 最多）含少量「深潮幸存者」字样与源工程目录引用（各文件 ≤5 处），全局替换即可
- **`scene-previewer/scene.html`**：页面标题与底部 SCENE 数据（tileset/sprite 摆位、`../../assets/...` 相对路径）为源工程数据；播放器本体（整数倍缩放/踩格线/分层帧合成时钟）直接可用，「新增素材只改本文件底部 SCENE 数据」
- **`templates/pixel-art-repro.yml`**：触发 paths 与 `assets/sprites/*/` 门禁循环按新工程目录调整
- **`pixel-toolkit/examples/gen_slime_idle.py`**：输出路径写死源工程 `assets/sprites/mob/`、`assets/palettes/`；只作生成脚本骨架范例（一源双产出、调色板先入板、重跑=资产），不直接运行
- **`agent-pipeline/agents/`**：内嵌的尺寸档位（64 玩家 / 32 小怪等）与帧数指引是源工程基准；新工程基准不同须修订——源工程实践：**改基准须同步全部 8 个 agent 定义**，保持与 AGENTS.md 一致

## 红线与许可

- 本包**不含**美术资产、调色板 JSON、gen_* 生成脚本、第三方模板与参考图——均留在源工程本地仓库存档，不随本包分发
- 外部内容义务**不随本包转移**：源工程美术含 Penusbmic「cutest hero」忠实复刻系（署名义务随资产走，资产未入本包）；`knowledge/像素法则.md` 是对 Saint11（Pedro Medeiros）公开教学的方法论提炼转述，其版权口径见该文头部——教程卡原图归档**不在本包**，转载本包不需附带授权但该文头部声明应保留
- `knowledge/` 其余文档为调研与方法沉淀，无外部内容嵌入

## 与源工程的关系

单向快照：源工程 DeepTideSurvivors 已转纯本地存档（远端解除关联，完整历史以 git bundle 快照备份，美术资产/gen 脚本/docs 全部原地保留）；本仓库位于其同级目录、自此独立版本演进，不再回写源工程。
