# templates/ — 接入新工程时套用的模板

| 文件 | 落位 | 用途 |
|---|---|---|
| `gitattributes` | 工程根 `.gitattributes` | 资产一律 binary（含大写 `.GIF`），防换行归一化误伤 |
| `gitignore-pixel-game` | 工程根 `.gitignore` | 本类工程 `.gitignore` 起步模板 |
| `pixel-art-repro.yml` | `.github/workflows/pixel-art-repro.yml` | 资产可复现 CI：重跑全部 `gen_*` 脚本 → 与在盘资产**解码后逐像素**比对 → `pixcli audit` 全量门禁（逐资产 check + atlas 一致性 + sheet/JSON 齐备） |

## 用法

按根 `README.md`「复用步骤」第 3 步落位。注意：

- `pixel-art-repro.yml` 的触发 `paths` 与门禁循环按新工程目录调整（见根 README「适配清单」）
- 比对必须**解码后逐像素**进行：PNG 编码字节随 Pillow 版本/平台漂移，`git diff` 会误报
