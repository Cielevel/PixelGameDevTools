# AI 像素图标准化 · 对照实验实测报告

> 执行：2026-09-06 · 依据同目录 `brief-ai-pixel-art-standardization.md` 第 5 节测试协议 + 第 4 节升级建议
> 结论先行：**三个候选工具与升级后的自有工具都能还原网格；真正拉开差距的是量化环节与工程化性质**。
> 升级已落地：`pixel-toolkit/pixcli.py standardize`（CLI）与 `asset-inspector`（GUI），实测全指标达标。

## 1. 测试工装与样本

样本由仓库自有生成器 `gen_slime_idle.py` 产出 32×32 干净真值（8 色调色板，alpha 两态），
NEAREST 放大 32 倍到 1024×1024、白底合成后存 JPEG q85（模拟 Google Flow 结构性 JPEG 输出）：

| 样本 | 内容 | 源唯一色 | 真值唯一色 |
|---|---|---|---|
| `lab/samples/sampleA_f0.jpg` | 良性：纯 JPEG 噪声 | 131 | 7 |
| `lab/samples/sampleB_f2_hard.jpg` | 困难：+高斯模糊 0.6（模拟 AA/mixels） | 946 | 8 |
| `lab/samples/anim/f{0,2,3,6}.jpg` | 动画 4 帧（跨帧共享网格/色板测试） | ~131 | 7-9 |

（交接包记录的真实 Flow 参考图为 6832–7099 色；合成样本噪声较温和，但污染机理一致。）

**指标口径**：容差命中 = 对真值逐像素 |ΔRGB| ≤4（JPEG ±1-3 色移下「精确相等」无意义，
实测所有工具精确命中都只有 ~12%）；色板外 = 输出色不在真值 8 色板内的像素占比；
残留 = 真值透明像素在输出中仍不透明的占比；幂等 = 对工具自身输出重跑一次零差异。

参赛工具：baseline（复刻 asset-inspector 旧链路：先验 1/32 最近邻缩格 + RGB 阈值 30 众数归并）、
SpriteGrid（git main，PyPI 0.2.0 无动画）、proper-pixel-art（ppa）、Pixel Art Fixer（pixelfixer Python 实现）、
**standardize（本次升级的自有工具，auto 网格 + 众数采样 + OKLab 量化）**。

## 2. 单图对照结果

### 样本 A（良性）

| 工具 | 输出尺寸 | 色数 | 容差命中 | 色板外 | 背景残留 | 幂等 | 耗时 |
|---|---|---|---|---|---|---|---|
| baseline（旧链路，先验格距） | 32×32 | 7 | 100% | 0% | 100% | ✓ | 0.02s |
| spritegrid | 32×32 | 7 | 100% | 0% | 100% | ✓ | 1.8s |
| spritegrid `-q 5` | 32×32 | 7 | 100% | 0% | 100% | ✗ | 1.3s |
| spritegrid `-q 4` | 32×32 | 7 | **10.7%** | **89.3%** | 100% | ✓ | 1.3s |
| ppa | 32×32 | 7 | 100% | 0% | 100% | ✗ | 1.4s |
| ppa `-c 8` | 32×32 | 7 | **50.8%** | **49.2%** | 100% | ✗ | 0.31s |
| ppa `-c 16` | 32×32 | 7 | **52.0%** | **48.0%** | 100% | ✗ | 0.32s |
| ppa `-c 32` | 32×32 | 7 | 100% | 0% | 100% | ✗ | 0.32s |
| pixfix | **64×64** | 7 | 100% | 0% | 100% | ✗ | 0.7s |
| **standardize** | 32×32 | 7 | **100%** | 0% | **0%** | **✓** | 1.1s |

### 样本 B（困难：模糊 + JPEG）

| 工具 | 输出尺寸 | 色数 | 容差命中 | 色板外 | 背景残留 | 幂等 | 耗时 |
|---|---|---|---|---|---|---|---|
| baseline（旧链路） | 32×32 | 7 | 100% | 0% | 100% | ✓ | 0.02s |
| baseline 仅缩格（无合并） | 32×32 | **23** | 100% | 0% | 100% | ✓ | 0.02s |
| spritegrid | 32×32 | **22** | 100% | 0% | 100% | ✗ | 1.3s |
| spritegrid `-q 5` | 32×32 | 8 | 100% | 0% | 100% | ✗ | 1.3s |
| spritegrid `-q 4` | 32×32 | 9 | **10.0%** | **90.0%** | 100% | ✗ | 1.3s |
| ppa | 32×32 | 9 | 100% | 0% | 100% | ✗ | 1.5s |
| ppa `-c 8` / `-c 16` | 32×32 | 7 | **1.2%** | **98.8%** | 100% | ✗ | 0.31s |
| ppa `-c 32` | 32×32 | 7 | **24.2%** | **75.8%** | 100% | ✗ | 0.31s |
| pixfix | **64×64** | **27** | 100% | 0% | 100% | ✗ | 0.7s |
| **standardize** | 32×32 | 12 | **100%** | 0% | **0%** | **✓** | 1.1s |

完整数据见 `lab/results.json`。

## 3. 关键发现

1. **网格还原是基本盘，各家都能做对**：规整样本上自动检测全部恢复 32×32（standardize 置信度
   0.61-0.86）。但 **pixfix 把 32×32 网格误检成 64×64（step 16）且置信度标 high**——输出不是
   「真分辨率」，均匀格下无害、复杂素材下会降质。
2. **JPEG 色移不可逆，只有量化能收敛**：网格还原后所有工具（含正确的）精确命中仅 ~12%，
   JPEG 的 ±1-3 逐通道色移只能靠量化映射回干净色板。「肉眼十几色 vs 工具上千色」的正确解法
   是交接包主张的顺序：**先网格还原（鲁棒采样吸收噪声）→ 后量化**。
3. **量化是双刃剑（本次最重要的实测发现）**：`ppa -c 8/16` 的 RGB k-means 色板漂移严重——
   B 样本容差命中跌到 **1.2%**（色数对了但颜色全错）；`spritegrid -q 4` 位深截断同样灾难
   （色板外 90%）。**naive 定色数量化会悄悄毁图**，必须用感知色距（OKLab）+ 好的初始化/代表色策略。
4. **背景处理是候选工具的集体空白**：所有候选 100% 保留白底；standardize 四角检测 + 边界连通
   清除做到 0% 残留（且不挖洞——主体内的白色高光保留）。
5. **幂等性**：standardize 设计上幂等（对自身输出重跑零差异，含量化环节）；spritegrid 部分场景
   幂等；ppa/pixfix 全部不幂等（重复处理会继续改图）——做流水线环节时这是实质风险。
6. **动画（0% 闪烁，但有一个反例教训）**：规整样本上逐帧独立处理与共享网格管线都 0% 闪烁。
   过程中实测到两个「共享色板」铁证：① 测试工装构造输入 GIF 时逐帧自适应量化，眼睛色跨帧漂移
   +22G，**输入色板漂移会原样传导过 spritegrid 的共享网格管线**（它共享网格不纠色板）；
   ② standardize 的多帧模式对全部帧采样结果**合并聚类出一份共享色板**再各自映射，
   从机制上杜绝跨帧色漂（交接包 Step 5）。
7. **依赖与性能**：standardize 纯 Pillow 零额外依赖（约 1.1s/张 1024²，macOS M 系）；
   三个候选均需 numpy+scipy（spritegrid/pixfix 另加 opencv），环境体积百 MB 级。
8. **众数采样的隐藏坑（Node 单测发现）**：朴素「格内众数」在均匀随机噪声下会在平局间摇摆、
   退化到近随机采样。修法（两端同步实现）：先按 8 级/通道**分桶投票**吸收 ±3 噪声，
   胜桶内再做一次 **±5 mean-shift** 重收被桶窗口截断的尾部——合成测试精确还原 0%→73.7%，
   真实 JPEG 样本无回归（100% 容差命中）。

## 4. 升级落地（均已实测验证）

- **CLI：`pixel-toolkit/standardize.py` + `pixcli standardize`**（纯 Pillow、全程确定性、可过
  `pixcli diff` 零差异）：自动网格检测（梯度自相关 + 相位，失败时报错提示 `--grid` 手动指定）→
  单元鲁棒采样（`--sampling mode|median`）→ OKLab 加权 k-means 量化（`--colors N`，默认 16，
  0 关闭）或映射工程色板（`--palette`）→ 四角背景检测（`--bg auto|keep|#hex`）；
  多输入自动共享网格与共享色板（防闪烁），输出 `<原名>_std.png`，直过 `pixcli check` 门禁。
- **palette.py**：`Palette.nearest` / `quantize` 最近色映射升级为 **OKLab 感知色距**
  （交接包 Step 3 规则；`quantize` 另加唯一色映射缓存提速）。
- **GUI：asset-inspector.html**（与 CLI 算法同源，纯 JS 零依赖）：
  ③ 处理链固定为 **缩格（采样方式：众数[默认]/中位数/最近邻）→ 去背景 → 合并（RGB|OKLab）→
  量化色数（8/16/32/64）**；新增「检测网格」按钮（自相关检测自动填缩格，动态补 1/N 档）；
  保存命名追加采样与量化后缀。浏览器 GUI 冒烟：同一 JPEG 检出 32×32（置信度 0.61，与 CLI 一致），
  131→7 色、透明底、边缘干净。

## 5. 建议（对下一轮工作）

- 对外采购/外包素材进门链路固定为：`standardize`（或 asset-inspector 同链路）→ `pixcli check`。
- 真实 Flow 样本（6832 色级）上的回归值得补测：合成样本噪声偏温和，报告结论中网格检测置信度
  门限（0.35）与合并/量化参数在真实样本上可能需微调。
- `pixel-toolkit/anim.py` 的 GIF 导出建议核查是否全帧共享色板（本次实验实证逐帧量化会闪烁）。

## 6. 复现

```bash
# ① standardize / 样本制作 / baseline：任意 Python 3.9+，只需 Pillow
python3 pixel-toolkit/pixcli.py standardize <flow导出.jpg> -o out_dir/ --colors 16
python3 pixel-toolkit/pixcli.py standardize f0.jpg f1.jpg f2.jpg -o out_dir/   # 多帧共享网格+色板

# ② 候选工具对照：需 Python 3.12+（spritegrid 要求），建议 uv 独立 venv
uv venv --python 3.12 .venv
VIRTUAL_ENV=.venv uv pip install spritegrid proper-pixel-art Pillow numpy
git clone --depth 1 https://github.com/Retro-Diffusion/pixel-art-fixer /tmp/pixel-art-fixer
VIRTUAL_ENV=.venv uv pip install -e /tmp/pixel-art-fixer/python

# ③ 工装（lab/ 内；make_samples 依赖本仓库 pixel-toolkit）
cd lab && python3 make_samples.py && python3 bench.py && python3 bench_anim.py
```
