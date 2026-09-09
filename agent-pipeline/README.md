# agent-pipeline/ — 多 agent 像素美术流水线

> **组成**：`agents/` 8 个 agent 定义（**只含各自差量**）+ `shared/` 共同基线 + `skills/pixcli/` 工具 skill。
> **部署**：`agents/` → `.zcode/agents/`、`shared/` → `.zcode/agents/shared/`、`skills/pixcli/` → `.zcode/skills/pixcli/`（完整映射见 `../knowledge/路径与部署映射.md`）。

## shared/ — 改基准只改这里（+ 工作区 `AGENTS.md`）

| 文件 | 管什么 |
|---|---|
| `像素资产约定.md` | 「画什么」：通用硬规格 + **资产来源路线（authored / sampled）分流** |
| `技法纪律.md` | 画法纪律（适用 **authored** 路线） |
| `审查框架.md` | 审查单与判据（**按来源路线分流**）+ 检查手段 + 输出格式 |
| `跨引擎交付契约.md` | 「怎么交出去」：交付四件套、Aseprite JSON 元数据、Unity/Godot/Web 落地、门禁缺口 |

## agents/

| agent | 用途 |
|---|---|
| `pixel-artist.md` / `pixel-artist-full.md` | 手绘资产：效率版 / 全量版 |
| `pixel-reviewer.md` / `pixel-reviewer-full.md` | 审查：效率版 / 全量版 |
| `pixel-imitator.md` + `pixel-imitator-reviewer.md` | 有源参考的模仿绘制 + 专项审查 |
| `pixel-loop-reviewer.md` | 循环动画时序专项审查 |
| `pixel-quick.md` | 形象设计快稿 |

## skills/pixcli/

`SKILL.md`：pixcli 速查与**门禁判读**（含按路线分流、stability/atlas 判读）。主代理自查、派发后复核、接线时验证都走它。

## 改基准的规矩

项目基准（画布档位 / 朝向集 / 动作清单 / 调色板与目录）写在工作区 `AGENTS.md`，是**唯一事实源**；agent 定义、`layout.py` 前缀表、CI 门禁均以其为准——**改基准只改 `AGENTS.md` 一处**，不动 agent 文件。
