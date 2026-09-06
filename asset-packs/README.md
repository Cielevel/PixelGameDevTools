# asset-packs —— 第三方模板资产包（用户购买所得）

> 2026-09-06 自 DeepTideSurvivors `assets/template/` 整体迁入。**来源：用户购买**（top-down 包 2026-09-05 购入），用户声明拥有使用权利；两包内均未随附许可文件，对外再分发的边界以购买渠道条款为准。

## 构成

| 包 | 规格 | 状态 |
|---|---|---|
| `top-down-asset-pack/` | 俯视 topdown 人形动作包，RGBA PNG（另附透明底版与 `.ase`/`.aseprite` 源），动作组 idle / walk / run / attack × 8 朝向。完整 sheet 实测：idle 768×512（64×64 格 ×12 帧）、walk 与 run 512×512（64×64 格 ×8 帧）、attack 672×768（96×96 格 ×7 帧，帧内含白色挥砍 FX）；**每行一个朝向一个完整序列**，行序 NW/W/SW/S/SE/E/NE/N，行首朝向标签画在白底版上（透明底版无标签，模仿取源用透明版） | 玩家动作主源（2026-09-05 定案，工程取 N/S/W/E 四向） |
| `2d-pixel-art-character-template/` | 48×48 侧视人形动作模板包（Walk/Run/Idle/Attack 等数十组动作，PNG sheet + Aseprite 源） | 备用参考（2026-09-05 topdown 定案后从主源降级） |

## 用法（模仿模式接线）

imitator 系 agent（`agent-pipeline/agents/pixel-imitator*.md`）按目标工程的 `assets/template/<包名>/` 路径取源——使用时把所需包拷贝（或软链）到目标工程该路径。原则「借动作不借皮」：包给姿态/节奏/帧数，工程给造型/调色板/锚点；视角或尺寸冲突时工程约定优先。

## 边界

- 包内容为**只读参考**：不写入、不参与构建产物；成品游戏分发的是基于它重绘的工程自产资产，不是本包原件。
- 原包不得对外再发布，除非购买渠道条款明确允许。
