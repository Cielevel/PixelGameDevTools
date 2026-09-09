# tools/ — 离线脚本与前端口径对拍

主 CLI 之外的一次性/离线脚本。**不随 `pixcli` 部署到游戏工程**（部署只拷 `pixel-toolkit/` 的库与 `pixcli.py`）。

| 脚本 | 用途 |
|---|---|
| `stability_report.py` | **稳定性读数离线脚本**（方案 §7 固化）：对帧目录/glob 跑 §1 判据，打印或 `--json` 输出；超标或样本不足 exit 1（可接 CI）。与 `pixcli stability`、`video-studio.html` 的 `computeStability()` **三处同口径** |
| `parity_frontend.py` + `parity_frontend.js` | **前端 JS ↔ Python 口径对拍**（需 Node）：`.py` 是驱动与比对（合成确定性数据 + 结果对照），`.js` 是执行器（从两个 HTML 抽取函数真身 eval），对拍 8 项：稳定性判据、时间维滤波、结构检查、归板、sheet 元数据（video-studio / asset-inspector 各一）、缩格（含 alpha）、时间众数稳定 |

```bash
python3 tools/stability_report.py <帧目录> [--max-flip 5 --max-colors 3 --min-static 50] [--json]
python3 tools/parity_frontend.py          # 需 node 在 PATH；全部通过 exit 0
```

**为什么要对拍**：两个单文件 HTML 各自实现 OKLab / 网格检测 / 降采样 / 色度抠像 / 稳定性判据（保「双击即用」），口径只能靠人工同步——对拍脚本是这条约定的**执行手段**，改任一侧都跑一遍。
