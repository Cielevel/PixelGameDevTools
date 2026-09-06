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
| `generation/` | **纯程序化生成素材方案**（独立类别）：`canvas.py` 绘制基元 / `style_kit.py` 风格基准库 / `gen_*.py` 资产生成脚本（`gen_slime_idle.py` 骨架范例）；类别总纲、脚本约定与骨架见其 `README.md`，后续「纯程序验证素材」功能将与此类别并列 |
| `palette.py` | 调色板 JSON 读写（`assets/palettes/`）、最近色映射（OKLab 感知色距）、`quantize` 归入色板、`enforce_alpha` 两态化、色条 PNG 导出 |
| `standardize.py` | AI 像素图标准化：亮度梯度自相关检测逻辑网格（含相位）→ 单元内鲁棒采样（众数分桶+mean-shift / 逐通道中位数）→ OKLab 加权 k-means 量化 / 映射工程色板 → 四角背景检测（边界连通清除）；多输入自动共享网格与色板（防闪烁）。源自 `ai-pixel-art-standardization-handoff/` 交接包升级建议，实测报告见其 `report-standardization-bench.md` |
| `anim.py` | 序列帧 I/O、sprite sheet 拼合/切分、GIF 导出、自包含 HTML 播放器、放大逐帧检查图（可叠像素网格坐标）、洋葱皮静态检查图 |
| `check.py` | 程序化自检：尺寸 / 模式 / alpha 两态 / 色数 / 调色板 / 帧组脚底与水平中心对齐 / 动画一致性（死帧 P1、跳变与循环突断 P2）/ 孤立像素 / 连通域计数（默认信息，`--components-max` 升门禁）；帧组按文件名前缀自动聚合，整目录混检互不误报；另提供 `frame_stats` 动画统计（不设门禁） |
| `layout.py` | sprites 子目录布局约定：按资产名前缀映射子目录（`sprite_dir`），前缀表按工程清单修订 |
| `pixcli.py` | 命令行入口 |

## 常用命令

```bash
# 自检（输入可以是文件列表或目录；帧组按文件名前缀自动聚合，整目录混检各资产互不干扰；
# exit 1 = 有 P0/P1）。帧组查：帧尺寸 / 脚底与水平中心对齐 / 动画一致性
python3 tools/pixelart/pixcli.py check assets/sprites/base/slime_idle_0*.png \
    --size 32x32 --palette assets/palettes/slime.json

# 整目录混检（不设 --size/--palette 时做结构检查：模式/alpha/色数/孤立像素/帧组/动画）
python3 tools/pixelart/pixcli.py check assets/sprites/base/

# 碎影/群落类资产的连通域门禁（不透明 4 连通域数 > N 报 P1；域数始终显示在 [图] 行）
python3 tools/pixelart/pixcli.py check assets/sprites/bullet/ebullet_shard_0*.png --components-max 4

# 动画统计（相邻/循环帧间 diff 率、面积序列；信息用不设门禁，供判断运动弧线与体积守恒）
python3 tools/pixelart/pixcli.py anim assets/sprites/mob/mob_witch_idle_0*.png

# 洋葱皮静态检查图：红=上一帧 蓝=下一帧 首尾回绕，查运动弧线/循环衔接/锚点抖动
python3 tools/pixelart/pixcli.py onion assets/sprites/mob/mob_witch_idle_0*.png -o /tmp/onion.png

# 帧序列 → 横向 sprite sheet（工作区约定：帧宽 = 原生宽，命名 <名称>_sheet.png）
python3 tools/pixelart/pixcli.py sheet assets/sprites/base/slime_idle_0*.png -o assets/sprites/base/slime_idle_sheet.png

# 一键预览：GIF + HTML 播放器 + 放大逐帧检查图（输出到 previews/，交付用户查看）
python3 tools/pixelart/pixcli.py preview assets/sprites/base/slime_idle_0*.png --out previews --name slime_idle --fps 10

# 放大逐帧检查图 + 像素网格（--grid：每源像素 1 线、每 8px 亮线并标坐标，审查引用坐标用）
python3 tools/pixelart/pixcli.py contact assets/sprites/mob/mob_slime_idle_04.png -o /tmp/f04.png --grid --scale 8

# sheet 切回单帧
python3 tools/pixelart/pixcli.py unsheet assets/sprites/base/slime_idle_sheet.png --size 32x32 -o /tmp/frames

# 任意图归入工程调色板 + alpha 两态化（外部参考/模仿导入的结构性保色；OKLab 感知色距最近色）
python3 tools/pixelart/pixcli.py quantize some.png --palette assets/palettes/slime.json -o out.png

# AI 像素图标准化：自动检测网格 → 每格众数采样 → OKLab 量化 16 色 → 自动去背景
# （JPEG 源先网格还原后量化；多输入自动共享网格与色板，输出 <原名>_std.png）
python3 tools/pixelart/pixcli.py standardize flow_export.jpg -o out_dir/
python3 tools/pixelart/pixcli.py standardize f0.jpg f1.jpg f2.jpg -o out_dir/ --colors 16
python3 tools/pixelart/pixcli.py standardize f0.jpg -o out.png --grid 32 --sampling median --colors 0

# 像素级比对：文件↔文件 或 目录↔目录；一致 exit 0，差异报数量/bbox/首几处坐标（重构零差异验证）
python3 tools/pixelart/pixcli.py diff assets/sprites/mob /tmp/regen_mob

# 调色板色条 / 从图像提取调色板
python3 tools/pixelart/pixcli.py swatch assets/palettes/slime.json
python3 tools/pixelart/pixcli.py from-image some.png -o assets/palettes/new.json --max-colors 16

# nearest 放大（仅供检查，正式资产不做放大）
python3 tools/pixelart/pixcli.py scale assets/sprites/base/foo.png -o /tmp/foo_x8.png --factor 8
```

## 生成脚本

生成脚本（`gen_*.py`）一律落 `generation/` 目录——脚本落位、颜色先入板、一源双产出、可复现验收（重跑零差异）等约定与代码骨架，见 [`generation/README.md`](generation/README.md)。

## 约定

- alpha 只允许 0/255；工具输出天然两态，`check` 拦截违规（P0）
- 按目录取帧时自动排除 `*_sheet.png`；显式传入的文件不做过滤——`check` 已按前缀自动分组、sheet 自成一组不影响帧组，但 `anim`/`sheet`/`preview` 等按序取帧的命令仍建议用 `_0*` 通配，避免把 sheet 当帧
- 颜色先入调色板再使用；画稿可用 `quantize` 归入色板
- 最近色映射（`quantize`、`standardize --palette`）自 2026-09-06 起用 OKLab 感知色距（交接包流水线 Step 3 规则），个别处于两色之间的像素归归宿可能与旧 RGB 欧氏结果不同
- 外部 AI/JPEG 像素图进门先走 `standardize`（网格还原 → 鲁棒采样 → 量化），顺序不可反：先压格子后减颜色
- 动画一致性检查（2026-09-03 加入，源自 aseprite-mcp 系「帧 diff/动画一致性校验」调研）：死帧（相邻帧像素全同）为 P1 门禁；跳变、循环首尾突断为 P2 提示；面积/体积守恒不自动判级，用 `anim` 看数据由审查解读——FX 类动画面积剧变属正常；确需关闭用 `check --no-anim`
- 连通域检查（2026-09-03 加入，源自 U8「主体 1 + 碎影 N、碎影不与主体粘连」审查沉淀）：域数默认只作信息（`[图]` 行 `域N`）；`--components-max N` 升为 P1 门禁，域数骤减即碎影与主体粘连；悬浮晶体/独立弹体等合法多域资产不要设此门禁
- `previews/` 只放交付给用户的预览（GIF/HTML/检查图）；自检用的放大图导出到**系统临时目录**，不留在工作区
- sprite sheet 命名 `<名称>_sheet.png`，序列帧命名 `<名称>_<两位帧号>.png`（从 00 起）
