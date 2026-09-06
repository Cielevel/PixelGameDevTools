# dog — 边牧像素资产（AI 生成稿 → 64×64 标准化流水线溯源）

> 本目录记录 `asset-test` 首例：AI 生成边牧图 → 网格还原 + OKLab 量化 + 描边的完整流程。
> 时间：2026-09-06。工具：本仓 `pixel-toolkit/`（pixcli）。

## 文件清单（按流程顺序）

| 文件 | 尺寸 | 说明 | SHA256（完整） |
|------|------|------|----------------|
| `dog_border_collie_src_1536.png` | 1536×1536 RGB | **源**：即梦 AI 生成原稿（`jimeng-2026-09-06-4102-严格64*64像素风格…png`，从 ~/Downloads 复制） | `406d1a2755fe76ce46066948e1daf4f14204096df3d973c84dab75d63c37d889` |
| `dog_border_collie_phase_aligned_1528x1534.png` | 1528×1534 RGB | **相位对齐**：源图裁剪左上 (8,2) px，使 24px 网格相位归零 | `3f31beef2dc12cf5c7daab430738265b648f44d4855bc8ccad82c3ef1e0acbe4` |
| `dog_border_collie_grid_63.png` | 63×63 RGBA | **网格还原**：`standardize --grid 24`（众数采样）+ OKLab k=16 量化 + 背景转透明 | `0dd5f57606b5675218bd81bdf980a6fe9baca0fac57a81f4a7bf673d3efa4a0b` |
| `dog_border_collie_std_64.png` | 64×64 RGBA | **补尺寸**：63×63 → 64×64（右侧/底部补 1px 透明） | `3725a9533ded01b2204c0d73644fcf522bc836ebf284ad8a1fbbcf880a84792a` |
| `dog_border_collie_final_64.png` | 64×64 RGBA | **最终交付**：OKLab 量化到 15 色后 `outline_in(#182b54)` 1px 闭合深色描边（工程规范：≤16 色含描边） | `c4eba89283e8af9310e265a627685624e2f6d95cc485a2a47b9dd24eaec69188` |

## 管线参数（可复现）

```bash
# ① 源 → 相位对齐裁剪（网格相位 (8,2)，crop 左上角使其归零）
python3 -c "from PIL import Image; im=Image.open('dog_border_collie_src_1536.png').convert('RGB'); im.crop((8,2,1536,1536)).save('dog_border_collie_phase_aligned_1528x1534.png')"

# ② 网格还原 + OKLab 量化（手动 grid=24，因为 auto 检测置信度仅 0.63，图非规则网格）
python3 pixel-toolkit/pixcli.py standardize -o dog_border_collie_grid_63.png \
    --grid 24 --colors 16 dog_border_collie_phase_aligned_1528x1534.png

# ③ 63×63 → 64×64（补 1px 透明，内容四周本就留白）
# ④ OKLab 量化到 15 色 + 1px 内描边（Canvas.outline_in，#182b54 深蓝黑）
```

## 关键决策记录

1. **网格**：源图为 AI 生图（1536×1536），非规则网格放大 → `--grid 24` 手动指定
   （1536/24=64；auto 检测 15x31@8,9 conf 0.63 不可信）。相位偏移 (8,2) 需 crop 对齐。
2. **色数**：源 2710 色（背景灰白渐变 249~255 占 82%）→ OKLab k=16 量化收敛 16 色；
   最终版为确保"≤16 色含描边"，先量化到 15 色再描边 = 16 色。
3. **描边**：工程硬规格 `agent-pipeline/shared/像素资产约定.md` — 外轮廓 1px 深色描边且闭合；
   本例采 `#182b54`（深蓝黑，非纯黑；**注**：该值源自原 demo 遗留脚本，后续资产应使用
   工程调色板 `roles.outline` 而非套用此例）；`outline_in` 内描边保剪影。验证：8-连通单闭合环、
   alpha 边界 122px 全覆盖、零漏洞。
4. **验收**：`pixcli check --size 64x64 --max-colors 16 asset-test/dog/dog_border_collie_final_64.png`
   → P0×0 P1×0 P2×0 通过。

## 备注

- 源图 `image-test-harness.png`（192×192，14 色测试图）为同构图降采样测试样本，
  本次未入目录（非流程产物）。
- 流程可复现：所有步骤均确定性（OKLab k-means 确定性、median/mode 采样确定性）。
