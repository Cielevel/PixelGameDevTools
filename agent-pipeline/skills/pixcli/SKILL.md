---
name: pixcli
description: 像素美术工具链（pixcli）速查与门禁判读。凡涉及像素资产的检查/验收、序列帧动画复核、sprite sheet 拼切、调色板量化归板、像素级 diff 零差异验证、预览导出，或接线消费 assets/sprites 资产时使用——即使用户没有明说"pixcli"。
---

# pixcli 像素美术工具链速查

`tools/pixelart/pixcli.py` 是工作区像素资产的唯一 CLI（Python 3 + Pillow，无其他依赖），仓库根目录直接运行，无需安装：

```bash
python tools/pixelart/pixcli.py <子命令> ...
```

**跨平台**：解释器名二选一——macOS/Linux 用 `python3`，Windows 用 `python`；依赖安装 `python3 -m pip install Pillow`；示例临时目录 `/tmp` 在 Windows Git Bash 下自动转换为系统临时目录；Windows 管道重定向若遇中文编码报错，设 `PYTHONUTF8=1`。

本 skill 只管「怎么跑工具、怎么判读结果」。资产基准（尺寸档位/命名/目录）以工作区 `AGENTS.md` 为准；完整参数文档在 `tools/pixelart/README.md`。制作与审查走 pixel-artist / pixel-reviewer 派发；**主代理自查、派发后复核、接线时验证**用这里。

## 门禁与判读（先读这节）

- **交付门禁只有一条**：`pixcli check ...` exit 0。exit 1 = 存在 P0/P1 必须修；P2 只是提示不拦截。
- check 查：尺寸（`--size WxH`）、RGBA 模式、alpha 两态（0/255）、唯一色数 ≤16（`--max-colors`）、色板合规（`--palette assets/palettes/<名>.json`）、帧组脚底与水平中心对齐、动画一致性、孤立像素、连通域计数（`[图]` 行 `域N`）。
- **帧组自动聚合**：按文件名 stem 前缀分组（`<名称>_idle_00..07` → 一组，`_sheet` 自成一组），**整目录混检各资产互不误报**；`[帧组 <名>]` 行出帧组级问题。关掉帧组检查仍用 `--no-frames --no-anim`。
- **动画一致性**（多帧组自动启用）：
  - 死帧（相邻帧像素完全相同）→ P1 门禁：动画没动或重复导出。
  - 帧间跳变 / 循环首尾突断 → P2 提示：先目视再定性，不自动成立。
  - 面积/体积变化**不自动判级**：FX 类动画（爆发、扩散、雷击）面积剧变与高帧间 diff 属正常——用 `anim` 看数据再解读，不要按循环动画标准误杀。
- **连通域**：域数默认只作信息；`--components-max N` 升级为 P1 门禁，用于「主体 1 + 碎影 N、碎影不与主体粘连」类资产——域数骤减即碎影与主体粘连。悬浮晶体、独立弹体等合法多域资产不要设此门禁。
- `anim` 是纯统计命令，永远 exit 0，只出数据不下结论。

## 常用命令

```bash
# 门禁自检（显式通配或整目录皆可，帧组自动分组；exit 0 才可交付）
python tools/pixelart/pixcli.py check assets/sprites/<资产>/<名称>_idle_0*.png --size 32x32 --palette assets/palettes/<调色板名>.json
python tools/pixelart/pixcli.py check assets/sprites/base/

# 动画统计：相邻/循环帧间 diff 率 + 面积序列（判断运动量级、循环衔接、体积守恒）
python tools/pixelart/pixcli.py anim assets/sprites/mob/mob_witch_idle_0*.png

# 洋葱皮检查图：红=上一帧 蓝=下一帧 首尾回绕（看运动弧线/锚点抖动；产物落系统临时目录）
python tools/pixelart/pixcli.py onion assets/sprites/mob/mob_witch_idle_0*.png -o /tmp/onion.png

# 放大逐帧检查图 + 像素网格（--grid：每 8px 亮线并标坐标，报告问题引用精确像素坐标用）
python tools/pixelart/pixcli.py contact assets/sprites/<资产>/<名称>_idle_04.png -o /tmp/f04.png --grid --scale 8

# 一键预览三件套（GIF + HTML 播放器 + 检查图；这是唯一放 previews/ 的输出）
python tools/pixelart/pixcli.py preview assets/sprites/<资产>/<名称>_idle_0*.png --out previews --name <名称>_idle --fps 10

# 帧组 ↔ sprite sheet（约定：横向、帧宽=原生宽、命名 <名称>_sheet.png）
python tools/pixelart/pixcli.py sheet assets/sprites/<资产>/<名称>_idle_0*.png -o assets/sprites/<资产>/<名称>_idle_sheet.png
python tools/pixelart/pixcli.py unsheet assets/sprites/<资产>/<名称>_idle_sheet.png --size 32x32 -o /tmp/frames

# 任意图归入工程调色板 + alpha 两态化（外部参考/模仿导入的结构性保色；多输入时 -o 为目录）
python tools/pixelart/pixcli.py quantize src.png --palette assets/palettes/<调色板名>.json -o out.png

# 像素级比对：一致 exit 0，差异报数量/bbox/坐标（重构或改参后"零像素差异"的验收方式）
python tools/pixelart/pixcli.py diff assets/sprites/mob /tmp/regen_mob
python tools/pixelart/pixcli.py diff a.png b.png
```

## 三个坑

1. **通配列帧仍用 `<资产名>_0*.png`，不要 `<资产名>_*.png`**——check 已按前缀自动分组、sheet 不会污染帧组，但 `anim`/`sheet`/`preview` 这类命令按传入顺序取帧，不分组，混入 sheet 仍会把 256px 宽的大图当一帧。
2. **自检产物不落工作区**：放大图、onion、grid 一律导出系统临时目录；只有交付用户看的预览才放 `previews/`。
3. **正式资产禁止插值放大**：`scale` 命令仅供检查出图；渲染端由引擎 nearest + 整数缩放，不烘进资产。

## 更多

- 完整参数与生成脚本骨架：`tools/pixelart/README.md`
- 风格基准库（明暗/剪影/眼神光惯例）：`tools/pixelart/generation/style_kit.py`；各资产生成脚本 `tools/pixelart/generation/gen_*.py`
- 资产目录前缀映射：`tools/pixelart/layout.py`（按工作区清单修订）
