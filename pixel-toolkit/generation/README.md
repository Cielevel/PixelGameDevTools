# generation/ —— 纯程序化生成素材方案

> **类别定位**：本包「纯程序化生成素材」的独立类别——**素材即程序**：每份正式资产都有一份可复现的生成脚本，重跑脚本 = 重造资产（像素级一致），不存在"手改后无源"的资产。工具库其余部分（`check.py` 门禁、`anim.py` 预览、`palette.py` 调色板、`layout.py` 目录约定）为本类别的共用基础设施。
> **规划占位**：后续将新增「**纯程序验证素材**」功能，作为与本类别并列的独立类别；现有验证手段（`pixcli check` 结构门禁、`pixcli diff` 零差异比对、`templates/pixel-art-repro.yml` 可复现 workflow）是其既有基础。本目录不预埋验证逻辑。

## 组成

| 文件 | 职责 |
| --- | --- |
| `canvas.py` | 绘制基元：`px / hline / vline / line / rect / ellipse / ellipse_outline / outline_in（闭合内描边）/ outline_out / mirror_left_to_right / shift / paste / replace_color`，逐像素、无抗锯齿，一切生成脚本的底层 |
| `style_kit.py` | **风格基准库**（源自 `slime_idle` 基准资产定案）：轮廓偏移法明暗带、穹顶剪影、高光团、眼神光等参数化惯例；新资产优先复用只改几何与配色参数；首个风格基准资产定案后，把明暗造型参数沉淀回此库 |
| `gen_*.py` | 各资产的生成脚本（可复现、可批量改色改参）；`gen_slime_idle.py` 为骨架范例 |

## 生成脚本约定

1. **落位与命名**：一律落本目录（部署后 `tools/pixelart/generation/`），命名 `gen_<资产名>.py`
2. **颜色先入板**：使用的颜色先写/读工程调色板（`assets/palettes/`），调色板缺失时由脚本先落盘再引用
3. **输出规格**：原生尺寸 RGBA PNG、alpha 两态（0/255）、禁止插值放大；序列帧命名 `<名称>_<两位帧号>.png`（00 起）+ `<名称>_sheet.png`
4. **一源双产出**（可选模式）：同一像素可双写正式档（经 `layout.py` 前缀映射落 `assets/sprites/<子目录>/`）与基准存档 `base/`，见 `gen_slime_idle.py`
5. **可复现验收**：重跑脚本必须与在盘资产像素级一致——手工验收 `pixcli diff <资产目录> <重跑目录>` 零差异；CI 用 `templates/pixel-art-repro.yml`（重跑全部 gen 脚本 → 逐像素 diff → 结构门禁）
6. **复用优先**：新脚本优先 import 本目录 `canvas` / `style_kit` 的基元与风格函数，不复制粘贴画法；技法依据引用《像素法则》条目

## 生成脚本骨架

```python
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                      # 本目录基元：canvas、style_kit
sys.path.insert(0, os.path.dirname(_HERE))     # 工具库根：anim、layout、palette

import style_kit                               # 风格基准库（明暗/剪影/眼神光惯例）
from canvas import Canvas
from palette import Palette

pal = Palette.load("assets/palettes/slime.json").roles
rows, y_top = style_kit.body_rows(15.5, 22, 14, 4, 8, ground_y=31)
c = Canvas(32, 32)
style_kit.shade_body(c, rows, y_top, 15.5, pal)      # 光源左上标准明暗
style_kit.highlight_blob(c, 15.5, y_top, 11.0, 14, pal)
c.outline_in(pal["outline"])                          # 闭合一 px 内描边
c.save("out.png")
```

完整范例（调色板先入板、一源双产出、sheet 拼装、10 帧 squash & stretch 无缝循环）：`gen_slime_idle.py`。
