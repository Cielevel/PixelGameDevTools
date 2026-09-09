# standardization-bench/ — AI 像素图标准化对照实验（历史存档）

> **状态：历史存档**（2026-09-06 一次性实验，2026-09-08 自交接包 `lab/` 迁入）。**不要再当作现行工具**：脚本是当时的一次性工装，结论已写进 `knowledge/standardization/report-standardization-bench.md`，落地实现是 `pixel-toolkit/standardize.py` 与 `asset-inspector/`。

## 内容

| 文件 | 说明 |
|---|---|
| `bench.py` | 对照实验驱动：baseline（复刻当时 inspector 链路）、SpriteGrid、proper-pixel-art、Pixel Art Fixer、本工程 `standardize`（经 `bench_std`） |
| `bench_anim.py` | 动画 4 帧（JPEG）逐帧处理 + 跨帧共享网格/色板，测静态像素闪烁率 |
| `bench_std.py` | 本工程 `standardize` 的适配器（`run` 不量化 / `run_c16` 量化 16 色） |
| `make_samples.py` | 样本制作——**已失效**：依赖的 `gen_slime_idle.py` 已从仓库删除，仅作方法存档 |
| `results.json` | 当时各工具的实测指标 |
| `samples/` | 样本与真值：`sampleA_f0.jpg`（良性 JPEG）、`sampleB_f2_hard.jpg`（模糊+JPEG 困难）、`anim/f{0,2,3,6}.jpg` + `gt/` 真值 + `anim.gif` |

## 运行提示（如确需重跑）

- 脚本以**系统临时目录** `pas-lab` 为工作区（`LAB = tempfile.gettempdir()/pas-lab`）：先把 `samples/` 拷到 `pas-lab/samples`，且外部工具（spritegrid / ppa / pixfix）需在 `pas-lab/.venv` 里自备
- `bench_std.py` 的 `sys.path` 原为硬编码绝对路径（旧仓位置 `ProjectZCode/…`，早已失效），2026-09-08 整理时改为相对本仓 `pixel-toolkit/`
- 依赖 Pillow；`make_samples.py` 不可运行（见上）
