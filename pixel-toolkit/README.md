# pixelart 美术创作工具

脚本化像素画工具集（Python 3 + Pillow，无其他依赖），供 pixel-artist 生成、自检、预览像素资产；
产出符合工作区 `AGENTS.md` 基准：RGBA PNG、alpha 两态（0/255）、原生尺寸、无插值、单图 ≤16 色。

## 跨平台运行（Windows / macOS）

工程经 GitHub 在两套 OS 间同步，运行差异只有解释器名与编码，工具代码本身零平台分支：

- **解释器**：macOS/Linux 用 `python3`，Windows 用 `python`。下文示例统一以 `python3` 书写，Windows 侧自行替换（`#!/usr/bin/env python3` shebang 仅 macOS 直接执行时生效）
- **依赖安装**：`python3 -m pip install Pillow`（两套 OS 相同，唯一第三方依赖）
- **控制台编码**：工具输出中文；Windows 下管道重定向若遇编码报错，设 `PYTHONUTF8=1`
- **临时目录**：示例中的 `/tmp` 在 macOS 直接可用；Windows Git Bash 会把 `/tmp` 参数自动转换为系统临时目录

## 组成

| 文件 / 目录 | 职责 |
| --- | --- |
| `generation/` | **纯程序化生成素材方案**（独立类别）：`canvas.py` 绘制基元 / `style_kit.py` 风格基准库 / `gen_*.py` 资产生成脚本（按约定自建）；类别总纲、脚本约定与骨架见其 `README.md`，后续「纯程序验证素材」功能将与此类别并列 |
| `palette.py` | 调色板 JSON 读写（`assets/palettes/`）、最近色映射（OKLab 感知色距）、`quantize` 归入色板、`enforce_alpha` 两态化、色条 PNG 导出 |
| `anim.py` | 序列帧 I/O、sprite sheet 拼合/切分、GIF 导出、自包含 HTML 播放器、放大逐帧检查图（可叠像素网格坐标）、洋葱皮静态检查图 |
| `check.py` | 程序化自检：尺寸 / 模式 / alpha 两态 / 色数 / 调色板 / 帧组脚底与水平中心对齐 / 动画一致性（死帧 P1、跳变与循环突断 P2）/ 孤立像素 / 连通域计数（默认信息，`--components-max` 升门禁）；帧组按文件名前缀自动聚合，整目录混检互不误报；另提供 `frame_stats` 动画统计（不设门禁） |
| `stability.py` | 时间稳定性判据（口径 = `../knowledge/像素视频-工具改进方案.md` §1）：核心静态格帧间变色率 + 单格平均色数；`--preset` 档位预设 |
| `standardize.py` | AI 像素图标准化：网格检测 → 逐格鲁棒采样 → OKLab 量化 → 去背景（`asset-inspector/` 交互版的 CLI 同源实现） |
| `atlas.py` | sprite sheet ↔ Aseprite JSON 生成与一致性门禁（矩形/trim/pivot/tags/`sourceRoute`；`--fidelity` 采样保真提示、`--palette-out` 随资产落调色板、`--format hash` 转 TexturePacker JSON Hash，契约 §1/§2/§3/§4.2） |
| `manifest.py` | **资产清单与审计**：扫描资产目录（递归）→ `manifest.json` + `manifest.md`（名称/目录/类型/尺寸/帧数/色数/来源路线/sheet+JSON 齐备），`--html` 出单文件看板；`audit` 复用 `check`/`atlas` 跑全量门禁汇总（P0/P1 exit 1） |
| `layout.py` | sprites 子目录布局约定：按资产名前缀映射子目录（`sprite_dir`），前缀表按工程清单修订 |
| `video.py` | AI 视频像素化管线：抽帧 → 抠像/裁剪 → 降采样 → 时间平滑（量化前中值 + 量化后众数稳定）→ 跨帧量化 → 描边 → 帧/GIF/HTML/sheet+JSON（`video-studio.html` 的后端同构实现） |
| `video-studio.html` | **视频像素化交互工作台**（纯静态单 HTML，双击即用、离线、零依赖）：① 多轨道时间轴裁剪（拖拽区块/边缘直观调整、轨道可重叠、播放头逐帧预览、每轨道独立播放/导出） ② 自定义采样帧率（12/24/30/60+custom） ③ 标准化参数（尺寸/等比/色数/时间维滤波（默认 0=关）/描边/幕色抠像/原生网格检测） ④ 可选后处理（色阶分配·区域众数 / 平涂中值 / 孤立像素清除 / 时间众数稳定；默认逐像素最近色 + 平涂/孤立关 + 时间稳定 3 帧众数） ⑤ 多导出方案（HTML 播放器 / GIF / Sprite Sheet + `sheet.json` / PNG 序列 / ZIP 打包，按选中轨道导出）。处理管线：幕色抠像＋边缘连通清除 →［原生网格开启时按源图原生像素网格逐格采样］→ 等比降采样 → 时间维滤波 → 跨帧共享 OKLab 量化（逐像素/区域众数）→［可选后处理］→ 描边；「原生网格」用两轴共峰定周期 + 跨帧圆均值定相位；处理完成后在像素团指示器旁显示稳定性读数（`稳定 9.6% \| 色 2.7`） |
| `pixcli.py` | 命令行入口 |
| `pipeline.py` | **管线配方执行器（节点系统 Phase 0，2026-09-09）**：`pipeline.json`（version 1，线性 stage 列表）→ `pixcli run` 确定性执行。节点注册表 17 个——源 2（video/images）· 变换 9（chroma-key/crop/resize/grid-sample/remove-bg/temporal-median/quantize/temporal-mode/outline）· 导出 4（frames/gif/html/sheet）· **门禁 2 是一等节点**（gate-check/gate-stability，不通过 exit 1）。阶段直调既有模块（**只编排不重写算法**，与 video-std/standardize 逐像素零差异）；`pixcli ops [--json]` 节点自省（供 Agent/未来浏览器工作台读）。结构示例见 `examples/` 与本文「管线配方」节 |
| `tests/` | pytest 回归（`python3 -m pytest pixel-toolkit/tests/ -q`）：注册表/参数强转/配方校验/端到端执行/确定性重跑/门禁拦截/**双 parity**（管线 vs video-std、管线 vs standardize，逐像素一致是红线） |
| `examples/` | 管线配方示例：`ai-video.pipeline.json`（视频四件套链）、`image-standardize.pipeline.json`（网格还原图像链） |
| `tools/` | 离线脚本与前端 JS↔Python 口径对拍（`stability_report.py` / `parity_frontend.py|js`）；**不随 `pixcli` 部署**，见其 `README.md` |
| `CHANGELOG.md` | 完成项与实测记录（原名 `TODO.md`，2026-09-08 改名）；当前版本 `v0.5.0`（版本表见根 `README.md`） |

## 常用命令

```bash
# 自检（输入可以是文件列表或目录；帧组按文件名前缀自动聚合，整目录混检各资产互不干扰；
# exit 1 = 有 P0/P1）。帧组查：帧尺寸 / 脚底与水平中心对齐 / 动画一致性
python3 tools/pixelart/pixcli.py check assets/sprites/<资产>/<名称>_idle_0*.png \
    --size 32x32 --palette assets/palettes/<调色板名>.json

# 整目录混检（不设 --size/--palette 时做结构检查：模式/alpha/色数/孤立像素/帧组/动画）
python3 tools/pixelart/pixcli.py check assets/sprites/base/

# 附加 sheet ↔ JSON 一致性（目录内 *_sheet.png 自动配对；缺 JSON 记 P1，并入 check 的 exit code）
python3 tools/pixelart/pixcli.py check --atlas assets/sprites/base/

# 碎影/群落类资产的连通域门禁（不透明 4 连通域数 > N 报 P1；域数始终显示在 [图] 行）
python3 tools/pixelart/pixcli.py check assets/sprites/bullet/ebullet_shard_0*.png --components-max 4

# 动画统计（相邻/循环帧间 diff 率、面积序列；信息用不设门禁，供判断运动弧线与体积守恒）
python3 tools/pixelart/pixcli.py anim assets/sprites/mob/mob_witch_idle_0*.png

# 洋葱皮静态检查图：红=上一帧 蓝=下一帧 首尾回绕，查运动弧线/循环衔接/锚点抖动
python3 tools/pixelart/pixcli.py onion assets/sprites/mob/mob_witch_idle_0*.png -o /tmp/onion.png

# 帧序列 → 横向 sprite sheet（工作区约定：帧宽 = 原生宽，命名 <名称>_sheet.png）
python3 tools/pixelart/pixcli.py sheet assets/sprites/<资产>/<名称>_idle_0*.png -o assets/sprites/<资产>/<名称>_idle_sheet.png

# 一键预览：GIF + HTML 播放器 + 放大逐帧检查图（输出到 previews/，交付用户查看）
python3 tools/pixelart/pixcli.py preview assets/sprites/<资产>/<名称>_idle_0*.png --out previews --name <名称>_idle --fps 10

# 放大逐帧检查图 + 像素网格（--grid：每源像素 1 线、每 8px 亮线并标坐标，审查引用坐标用）
python3 tools/pixelart/pixcli.py contact assets/sprites/<资产>/<名称>_idle_04.png -o /tmp/f04.png --grid --scale 8

# sheet 切回单帧
python3 tools/pixelart/pixcli.py unsheet assets/sprites/<资产>/<名称>_idle_sheet.png --size 32x32 -o /tmp/frames

# 任意图归入工程调色板 + alpha 两态化（外部参考/模仿导入的结构性保色；OKLab 感知色距最近色）
python3 tools/pixelart/pixcli.py quantize some.png --palette assets/palettes/<调色板名>.json -o out.png

# AI 像素图标准化：自动检测网格 → 每格众数采样 → OKLab 量化 16 色 → 自动去背景
# （JPEG 源先网格还原后量化；多输入自动共享网格与色板，输出 <原名>_std.png）
python3 tools/pixelart/pixcli.py standardize flow_export.jpg -o out_dir/
python3 tools/pixelart/pixcli.py standardize f0.jpg f1.jpg f2.jpg -o out_dir/ --colors 16
python3 tools/pixelart/pixcli.py standardize f0.jpg -o out.png --grid 32 --sampling median --colors 0

# AI 像素视频标准化：抽帧 → 抠像/裁剪 → 缩到 64×64 → 背景透明 → 时间维滤波（可选，量化前）→ 跨帧 16 色量化 → 时间众数稳定（默认 3，量化后）→ 描边
# → 帧/GIF/HTML/sheet(+"sheet.json")。AI 动态视频无稳定网格，默认降采样；需 ffmpeg
python3 tools/pixelart/pixcli.py video-std ai_video.mp4 -o out_dir/ --size 64x64 --outline '#182b54'
python3 tools/pixelart/pixcli.py video-std ai_video.mp4 -o out_dir/ --fps 12 --crop fixed --box 466,148,746,554
# 时间平滑默认开（--stabilize 3 时间众数稳定，量化后执行）：压静止区域帧间变色（闪烁）；
# --temporal N 是量化前中值（默认 0=关，拖影更大）；复现旧素材/对比请显式关掉稳定
python3 tools/pixelart/pixcli.py video-std ai_video.mp4 -o out_dir/ --size 64x64 --stabilize 0
python3 tools/pixelart/pixcli.py video-std ai_video.mp4 -o out_dir/ --size 64x64 --temporal 9 --no-sheet

# 稳定性门禁（方案 §1 判据）：核心静态格帧间变色率 + 单格平均色数；超标/样本不足 exit 1
# 读数形如「稳定 9.6% | 色 2.67」——调参从「感觉」变「看数」
python3 tools/pixelart/pixcli.py stability out_dir/
python3 tools/pixelart/pixcli.py stability out_dir/ --max-flip 5 --max-colors 3 --json
python3 tools/pixelart/stability_report.py out_dir/     # 同上，离线独立脚本（tools/ 下）

# sheet ↔ 元数据一致性门禁（契约 §4.2）：矩形越界/重叠、trim、pivot、tags；--frames 加逐像素比对
python3 tools/pixelart/pixcli.py atlas out_dir/ai_video_sheet.png out_dir/ai_video_sheet.json --frames out_dir/
# --fidelity 查采样保真（疑似整数倍放大稿，P2 提示）；--palette-out 随资产落调色板（.gpl = GIMP，其他 = 本仓 JSON）
python3 tools/pixelart/pixcli.py atlas out_dir/ai_video_sheet.png out_dir/ai_video_sheet.json --palette-out out_dir/ai_video.gpl
# Web 适配层：Aseprite JSON → TexturePacker JSON Hash（门禁通过才写，契约 §3）
python3 tools/pixelart/pixcli.py atlas out_dir/ai_video_sheet.png out_dir/ai_video_sheet.json --format hash -o out_dir/ai_video_hash.json

# 资产清单：扫描文件/目录（递归）→ manifest.json + manifest.md；--html 出单文件看板（离线可开）
# 只读盘点不设门禁；输出无时间戳，重跑逐字节一致（可进 CI diff）
python3 tools/pixelart/pixcli.py manifest assets/sprites -o previews --html previews/dashboard.html

# 全量审计：逐资产 check（帧组/动画含在内）+ atlas 一致性 + sheet/JSON 齐备 → P0/P1 exit 1
# 交付前 / CI 的「全工程一眼看全」入口；--atlas-frames 加逐帧逐像素比对（慢）
python3 tools/pixelart/pixcli.py audit assets/sprites --size 32x32 --palette assets/palettes/<调色板名>.json

# 像素级比对：文件↔文件 或 目录↔目录；一致 exit 0，差异报数量/bbox/首几处坐标（重构零差异验证）
python3 tools/pixelart/pixcli.py diff assets/sprites/mob /tmp/regen_mob

# 调色板色条 / 从图像提取调色板
python3 tools/pixelart/pixcli.py swatch assets/palettes/<调色板名>.json
python3 tools/pixelart/pixcli.py from-image some.png -o assets/palettes/new.json --max-colors 16

# nearest 放大（仅供检查，正式资产不做放大）
python3 tools/pixelart/pixcli.py scale assets/sprites/base/foo.png -o /tmp/foo_x8.png --factor 8

# 管线配方：一份 JSON 描述「源 → 变换 → 导出 → 门禁」全链（确定性执行，门禁不通过 exit 1）
python3 tools/pixelart/pixcli.py run tools/pixelart/examples/ai-video.pipeline.json
python3 tools/pixelart/pixcli.py run graph.json --dry-run -o out/xxx/   # 只校验+打印计划；-o 覆盖输出目录
python3 tools/pixelart/pixcli.py ops --json                            # 节点注册表自省（Agent/工作台读）
```

## 管线配方（pipeline JSON，节点系统 Phase 0）

一份 JSON = 一条可复现的处理链（可入 git、可进 CI diff、Agent 可直接生成）：
`input`（源节点）→ `stages`（线性阶段列表）→ `output.dir`（导出目录）。
阶段语义与 `video-std` / `standardize` **同源分解、逐像素零差异**（tests 双 parity 守住）；
schema 预留 DAG 演进（`id`/`from` 字段已定义，version 1 暂不支持分支）。

```json
{
  "version": 1,
  "name": "AI 视频 → 64x64 四件套",
  "input":  { "op": "source.video", "params": { "path": "in.mp4", "fps": 12 } },
  "stages": [
    { "op": "chroma-key",    "params": { "mode": "auto" } },
    { "op": "crop",          "params": { "mode": "auto" } },
    { "op": "resize",        "params": { "size": [64, 64] } },
    { "op": "quantize",      "params": { "colors": 16 } },
    { "op": "temporal-mode", "params": { "window": 3 } },
    { "op": "outline",       "params": { "color": "#182b54" } },
    { "op": "export-frames" },
    { "op": "export-sheet",  "params": { "source-route": "sampled" } },
    { "op": "gate-check",    "params": { "size": [64, 64] } }
  ],
  "output": { "dir": "out/xxx/" }
}
```

要点：
- **门禁内联**：`gate-check`（需先 `export-frames`）与 `gate-stability` 与 `pixcli check` / `stability` 同口径，任一不通过整条配方 exit 1——「配方通过」即可交付；sampled 路线记得按 skill 口径加 `no-frames`/`no-anim`（帧组对齐/动画一致性对采样素材不作否决，见上方示例）
- **确定性**：同输入同配方 → 产物逐字节一致（无时间戳）；报告首行含配方 sha256（Phase 1 内容寻址缓存预留）
- **阶段顺序自由**但有既定语义（如 `quantize` 后接 `outline` 会自动预留 1 色配额，与 video-std 同口径）；错误配方静态校验直接 exit 2 并逐条列出问题

## 生成脚本

生成脚本（`gen_*.py`）一律落 `generation/` 目录——脚本落位、颜色先入板、一源双产出、可复现验收（重跑零差异）等约定与代码骨架，见 [`generation/README.md`](generation/README.md)。

## 约定

- alpha 只允许 0/255；工具输出天然两态，`check` 拦截违规（P0）
- 按目录取帧时自动排除 `*_sheet.png`；显式传入的文件不做过滤——`check` 已按前缀自动分组、sheet 自成一组不影响帧组，但 `anim`/`sheet`/`preview` 等按序取帧的命令仍建议用 `_0*` 通配，避免把 sheet 当帧
- 颜色先入调色板再使用；画稿可用 `quantize` 归入色板
- 最近色映射（`quantize`、`standardize --palette`）自 2026-09-06 起用 OKLab 感知色距（交接包流水线 Step 3 规则），个别处于两色之间的像素归归宿可能与旧 RGB 欧氏结果不同
- 外部 AI/JPEG 像素图进门先走 `standardize`（网格还原 → 鲁棒采样 → 量化），顺序不可反：先压格子后减颜色
- **资产来源路线**：`authored`（手绘/重绘）与 `sampled`（采样像素风格——本工具链 `standardize` / `video-std` / `asset-inspector` 的产物）的规格差异与门禁分流见 `../agent-pipeline/shared/像素资产约定.md`「资产来源路线」：sampled 的色数**按归板后计**，脚底对齐 / 描边闭合 / 明暗阶次不强制，验收看 `pixcli stability` 读数 + `pixcli atlas` 一致性（`check` 的手绘门禁不作否决）
- 「闪不闪」有量化判据（2026-09-08 加入，方案见 `../knowledge/像素视频-工具改进方案.md`）：核心静态格帧间变色率 + 单格平均色数，`pixcli stability` 门禁（暂定 ≤5% / ≤3.0，静态格 <50 报样本不足）；时间平滑默认由**时间众数稳定**（`video-std --stabilize 3` / 页面「后处理·时间稳定」，量化后取窗口众数、平局保留当前帧）承担——实测残影 1 帧 1.66% / 2 帧 0.00%、稳定 24.4%；`--temporal N`（量化前中值，默认 0）仍可用但拖影更大。**读数警告**：稳定性读数奖励时间冻结，须与拖影一起看。判据只管静止格——运动必然改变颜色，全局 diff 率（`anim`）定位不到闪烁
- sheet 交付随附 `_sheet.json`（Aseprite JSON Hash，契约 §2/§4.2）：`video-std` / `video-studio.html` 导出即产出，`pixcli atlas` 校验一致性；`trimmed` 必须 false，pivot 唯一写 `meta.pivot`
- 动画一致性检查（2026-09-03 加入，源自 aseprite-mcp 系「帧 diff/动画一致性校验」调研）：死帧（相邻帧像素全同）为 P1 门禁；跳变、循环首尾突断为 P2 提示；面积/体积守恒不自动判级，用 `anim` 看数据由审查解读——FX 类动画面积剧变属正常；确需关闭用 `check --no-anim`
- 连通域检查（2026-09-03 加入，源自 U8「主体 1 + 碎影 N、碎影不与主体粘连」审查沉淀）：域数默认只作信息（`[图]` 行 `域N`）；`--components-max N` 升为 P1 门禁，域数骤减即碎影与主体粘连；悬浮晶体/独立弹体等合法多域资产不要设此门禁
- `previews/` 只放交付给用户的预览（GIF/HTML/检查图）；自检用的放大图导出到**系统临时目录**，不留在工作区
- sprite sheet 命名 `<名称>_sheet.png`，序列帧命名 `<名称>_<两位帧号>.png`（从 00 起）
- `pixcli manifest` / `audit` 的资产分组与色数口径**复用 `check`**：末尾 `_NN` 一律视作帧号（单图 `xxx_64.png` 会归入 `xxx` 组——既有分组约定如此，非 manifest 独有）；清单不含时间戳，重跑逐字节一致
