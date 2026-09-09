# knowledge/standardization/ — AI 像素图标准化交接包（归档）

> **状态：归档**（2026-09-06 采集，仅供追溯）。**当前做法不在这里**——落地实现在 `pixel-toolkit/standardize.py` + `pixel-toolkit/pixcli.py standardize` 与 `asset-inspector/`（GUI），口径见 `pixel-toolkit/README.md`。
> 原目录 `ai-pixel-art-standardization-handoff/` 已于 2026-09-08 拆分：4 份文档进本目录，实验脚本与样本移至 `experimental/standardization-bench/`。

## 文件

| 文件 | 说明 |
|---|---|
| `brief-ai-pixel-art-standardization.md` | 交接简报：场景、痛点、事实与规则、候选工具、测试协议（交给其他 agent 做实测评估的输入） |
| `report-standardization-bench.md` | **对照实验实测报告**：三个候选工具 + 自有实现的网格还原/量化/工程化对比；结论「都能还原网格，差距在量化环节与工程化性质」，升级已落地 |
| `shelf-ai-pixel-art-standardization.md` | 外部知识库原件：JPEG 有损源 → 干净索引色像素画的流程/规则/工具综述 |
| `deepdive-marksverdhei-spritegrid.md` | 外部工具深挖：SpriteGrid（网格检测 + 鲁棒采样清洗器） |

## 与本仓其他部分的关系

- **落地实现**：`pixel-toolkit/standardize.py`（网格检测 + 单元鲁棒采样 + OKLab 量化）、`asset-inspector/asset-inspector.html`（交互版）
- **实验工装**：`experimental/standardization-bench/`（bench 驱动、动画闪烁测试、样本与真值、`results.json`）
- **样本溯源**：`samples/dog/picture/README.md`（边牧图走完整 standardize 流程的产物与 SHA256 清单）
- 文档中 `Shelf/…`、`ShelfGithub/…` 是个人知识库归档原件，不在本仓（见 `../路径与部署映射.md`）
