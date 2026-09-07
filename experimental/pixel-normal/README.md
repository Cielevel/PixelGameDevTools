# pixel-normal — 像素法线实验室

> 实验功能：把**法线贴图 + 动态光照**引入 2D/像素画素材。目标形态为纯静态单 HTML（双击即用、离线、零构建零依赖）。当前处于**原型阶段**，独立演化；即便日后成熟独立成仓，亦为**私有库**——本工具链仅自用/自研发，不对外发布。

## 目标

1. **光照查看（路线 A）**：提供 diffuse 图（漫反射/固有色，即常说的"原色图"）+ normal map（法线图），实时查看与光照的交互——点光源跟随鼠标，光源高度/强度/环境光/高光可调，并实验"量化光照"模式以保持像素画质感。
2. **高度图转法线（路线 B）**：提供灰度高度图（Height Map），程序转换为法线图（Sobel 算子等），参数可调（强度/平滑/算子/边界/采样），边生成边预览，一键送入路线 A 查看效果。

> 术语：社区常说的"diffusion 图"实为 **diffuse map**（漫反射贴图 / albedo / 固有色图）。

## 可行性结论（2026-09-07 调研）

- 两条路线均可行，算法成熟且零引擎依赖：一个 WebGL2 片元着色器即可完成 2D 法线光照。
- 2D 精灵不需要 3D 那套 TBN/切线空间：平面精灵的法线直接按屏幕/观察空间使用（pixi-lights、Godot、Phaser 的实际做法一致）。
- 真正的难点不在实现而在**像素画美学**：连续光强渐变会破坏像素画的调色板质感。业界缓解手段是"量化"组合拳——光照响应分档、法线离散化（如 9 方向）、低分辨率渲染 + 光源对齐像素。**本实验的核心验证点即这套旋钮的可控性**。
- 像素画硬边 + 少色数下，纯 Sobel 的梯度集中在 1px 轮廓上、法线呈锯齿跳变；需要"alpha 距离场斜面（bevel）"生成或先平滑/上采样。列为 P2 实验项。

## 关键技术点

### 光照模型（2D 简化版）

```
N = normalize(normalTex.rgb * 2 - 1)          // 法线解码
L = normalize(vec3((lightXY - fragXY) * aspect, lightZ))  // 光向量：屏幕空间 + 高度分量
diffuse = max(dot(N, L), 0) * lightColor       // Lambert
spec    = pow(max(dot(N, H), 0), shininess)    // Blinn-Phong（可选）
out     = albedo * (ambient + diffuse) + spec
```

光源 Z（高度）决定光斑软硬；宽高比校正防止光斑拉成椭圆。

### 高度图 → 法线（Sobel）

```
Gx = [[-1,0,1],[-2,0,2],[-1,0,1]]    Gy = [[-1,-2,-1],[0,0,0],[1,2,1]]
n = normalize(-dX * strength, -dY * strength, 1.0)
rgb = n * 0.5 + 0.5                   // 平坦面 = (0.5, 0.5, 1.0) 淡紫
```

- strength 默认 ~2.5（Laigter / NormalMap-Online 默认值一致）；可选中心差分（更干净）/ Scharr（3,10,3 核，旋转对称更好）。
- 转换前小半径模糊可把硬边台阶梯度变为连续坡度（Laigter 默认 blur radius 6）。
- 边界：非平铺 clamp、平铺 wrap；像素画用最近邻采样（双线性会抹开 1px 轮廓）。
- 内部全程浮点：8bit 高度图在缓坡上易量化成台阶，16bit 更好。
- **绿通道约定**：OpenGL 风格 Y+（Godot/Unity/Blender），DirectX 风格 Y-（Unreal/3ds Max），二者只差 `g = 1 - g`——必须暴露反 Y 开关（Polycount 权威对照表）。
- sRGB 纪律：albedo 按 sRGB 解读，法线图必须按线性采样，不可混用。

### Alpha 距离场 bevel（P2）

```
mask   = alpha ≥ 128（两态，与着色器 discard 同阈值）
dist   = EDT(mask)            // 每个内部像素到最近外部像素的精确欧氏距离
height = 255 · profile(min(dist / b, 1))   // b=斜面宽；全距模式 b=max(dist)
profile: 线性 u / 缓坡 u²(3−2u) / 圆坡 √(1−(1−u)²)
```

- EDT 用 Felzenszwalb–Huttenlocher 两遍一维下包络（先列后行），**精确欧氏**且 O(n)——比 chamfer 3-4-5 的斜向近似更适合像素级 rim；瓶心距离实测 √257 与手算完全一致。
- 高度恒为满量程 0..255 跨 b 像素：默认强度 1.2 出「整体外倾的 rim 光」；全距 + 低强度（~0.1–0.3）出柔和圆顶——强度即坡度旋钮。
- 距离场只感知 alpha 轮廓：洞/凹陷自动出 rim，但内部花纹（眼睛等）法线平坦——内部起伏仍需高度图或外部 AI 管线。

### 像素画质感实验旋钮

- **光照量化**：N·L 强度分成 N 档，输出回落到有限色阶。
- **法线量化**：法线归入离散方向（如 9 方向，facet9 思路），同色块光照一致。
- **调色板光照（已实现）**：自动提取 diffuse 不透明区颜色（按频次取前 64），着色器把光照后的线性域颜色吸附到最近调色板色——输出恒在素材色集内，光照明暗变成"打色阶梯"；与光照量化可叠加（先分档后吸附）。
- **低分辨率渲染 + 光源对齐像素格**；衰减可切 toon 阶梯。

## MVP 计划

- **P0 光照查看器**：拖入 diffuse + normal → WebGL2 渲染；点光随鼠标；参数面板（光高/光强/环境光/高光/量化档位/反 Y）；内置程序生成的自制示例素材。
- **P1 高度图转法线（已完成 2026-09-07）**：页面内置转换器——算子 Sobel 3×3 / Scharr 3×3 / 中心差分（均归一化，强度跨算子可比）、强度（梯度倍率）、平滑（box blur×2，抑硬边锯齿）、边界 clamp/wrap、反相（黑=高）；实时预览 + 实时送入光照（可关，手动「送入 Normal 槽」强制送入）；示例素材已统一走此管线。
- **P2 alpha 距离场 bevel（已完成 2026-09-07）**：转换卡「源」新增 **Alpha 距离场（Diffuse 轮廓）**——无高度图的平面精灵从 alpha 轮廓自动出法线。参数：斜面宽（1～48px）/ 坡形（缓坡 smoothstep · 线性 45° · 圆坡四分弧）/ 全距（以图内最大内距为斜面宽，凸形≈圆顶）；洞与凹陷轮廓自动出 rim；反相在此模式下＝内凹效果；高度槽/药水瓶示例走此管线，其后仍复用 P1 全部算子旋钮。
- **P2 调色板感知光照（已完成 2026-09-07）**：表面响应区「调色板」开关——diffuse 载入即自动提取调色板（≤64 色），开启后光照输出在线性域吸附到最近调色板色（GLSL texelFetch 循环），输出恒在素材色集内；与量化档叠加生效。
- **P2 其余实验项**：GIF/帧序列批处理。

## 参考

- mattdesl ShaderLesson6（2D 法线光照经典教程，含像素画 WebGL demo）：<https://github.com/mattdesl/lwjgl-basics/wiki/ShaderLesson6>
- pixi-lights（点光 shader 参考实现）：<https://github.com/pixijs-userland/lights>
- Godot 2D 光照文档：<https://docs.godotengine.org/en/stable/tutorials/2d/2d_lights_and_shadows.html>
- Unity URP 2D 光照：<https://docs.unity3d.com/Manual/urp/Lights-2D-intro.html>
- Phaser Light2D 管线（`setPipeline('Light2D')`）：<https://github.com/phaserjs/phaser>
- Polycount Normal Map Technical Details（绿通道约定权威表）：<http://wiki.polycount.com/wiki/Normal_Map_Technical_Details>
- NormalMap-Online（Sobel/Scharr 着色器参考实现，MIT）：<https://github.com/cpetry/NormalMap-Online>
- GIMP normalmap 插件（卷积核/参数取证）：<https://github.com/RobertBeckebans/gimp-plugin-normalmap>
- Laigter（2D 法线生成，距离场 bevel 思路，GPL-3.0）：<https://github.com/azagaya/laigter>
- Materialize（材质生成，GPL-3.0）：<https://github.com/BoundingBoxSoftware/Materialize>
- facet9（像素画"量化法线"概念验证）：<https://github.com/RandyGaul/facet9>
- GodotPaletteLightingShader（调色板量化光照）：<https://github.com/Deab22/GodotPaletteLightingShader>

## 素材与生成管线（外部通路，2026-09-07 记录）

工具内置现状（2026-09-07 更新）：**轮廓级法线已可内置生成**——P2 Alpha 距离场 bevel 从 diffuse 轮廓直接出 rim/圆顶法线，零依赖、即改即看；**内部起伏（花纹/写实体积）仍需外部素材**。规划中的外部工作流：

1. **diffuse 来源（已就绪）**：已订阅 [pixellab.ai](https://www.pixellab.ai/)，可直接获得 **product-ready 的 pixel diffuse 资产**——作为路线 A 的 diffuse 输入。
2. **法线生成（计划中）**：用 **Gemini** 从 product-ready diffuse 生成 normal map（外部 AI 路线；同调研中 normal-forge 的"深度估计 → 法线"思路，免实现免依赖）。产物（图片/视频素材）喂路线 A 阅览。
3. **待确认**：pixellab.ai 自身能否直接产出 normal map 风格资产（未验证；若可行可省掉 Gemini 环节）。
4. **阅览（现状差距）**：查看器目前只收静态 diffuse + normal 双图；"按视频/图片素材批量阅览"需要视频/逐帧接入，归入 P2 批处理项。

分工口径：内置距离场 bevel＝**快速迭代的可选实验**（调参验证、rim 光原型）；正式生产的写实法线走外部 AI 管线。

## 状态

- 2026-09-07：可行性调研完成，方案定稿。
- 2026-09-07：**P0 光照查看器完成**（`pixel-normal.html`，纯静态单 HTML、双击即用）。已实现：diffuse + normal 双素材槽（拖入/点击）；WebGL2 实时点光（鼠标跟随、滚轮调光高）；参数面板——光高 Z / 光强 / 环境光 / 高光强 / 高光锐度 / 量化档（0=关～16 档）/ 反绿 Y（DirectX 约定）；三视图（光照合成 / diffuse / normal）；整数倍最近邻缩放；程序生成示例素材（史莱姆高度场 → Sobel → 法线，兼作路线 B 管线预演）。光照在线性域计算（albedo sRGB↔线性，法线线性采样）。已浏览器实测：光源四向跟随、量化分档、反 Y 翻转、外部 PNG 拖入、滚轮/缩放/清空重载。
- 2026-09-07：**P1 高度图→法线转换器完成**。第三素材槽 Height（彩色按亮度取灰）+ 转换卡（算子/强度/平滑/边界/反相）+ 96px 实时预览（含耗时）+「实时送入」开关（关闭后光照冻结，按钮强制送入）。实现要点：算子归一化（Sobel/8、Scharr/32、中心差分/2，强度=每像素高度梯度倍率）；可分离 box blur×2 ≈ 高斯；CPU Float32 全程精度；每次转换产出新画布快照。已实测（截图 + 像素级数值验证）：平滑把轮廓最大梯度跳变 87→6、反相使法线 G 通道翻转（255→0）、关闭实时送入后改参数不动槽位且按钮强制送入生效、合成 80×80 高度图 10.5ms 转换且平坦区法线 (128,128,255)、算子/边界切换无异常。
- 2026-09-07：**P2 Alpha 距离场 bevel 完成**。转换卡新增「源」（高度图亮度 / Alpha 距离场）+ 距离场参数行（斜面宽/坡形/全距，按源显隐）；新增「示例·药水瓶」平面精灵（无高度图，端到端演示一键出法线）；alpha 模式下 diffuse 换图自动重算。已浏览器实测（glm-5.3-flash 视觉评估 + 页内像素级数值断言）：药水瓶四向 rim 法线正确外倾（左 R=0 / 右 R=255 / 下 G=0，中心与外部平坦 (128,128,255)）；EDT 页内瓶心距离 16.031=√257 与手算一致（node 侧另过 5 用例含斜向 √8 精确性）；反相使 rim 法线整体翻转（左 R 0→253，内凹）；全距/坡形/斜面宽联动正确；切回无高度图的亮度源正确降级提示且已送入法线冻结；64×64 全管线 0.6–3.5ms。三张截图（药水瓶光照/史莱姆 rim 光照/法线大图）均过视觉评估：rim 过渡、最近邻缩放干净、顶部偏绿=OpenGL +Y 约定正确。
- 2026-09-07：**P2 调色板感知光照完成**。diffuse 载入自动提取调色板（不透明区去重按频次取前 64，GLSL 循环上限）；着色器末端、sRGB 回编前在线性域做最近色吸附；画布改 preserveDrawingBuffer 以支持像素级验证，纹理上传显式切活动单元（修掉依赖调用顺序的隐式状态）。已实测：史莱姆 6 色/药水瓶 8 色自动重提取；开启后整幅扫描 281/229 个采样不透明像素 **0 违例**（全部落在调色板 ±1 内）；中心像素读回 (88,177,76) 与 CPU 镜像推算逐字节一致（受光 hi 绿吸附回 base 绿），关闭开关同像素回到连续值 (119,178,101)；GLM 视觉评估确认输出呈分档纯色块、cel-shading 式打色、控件正常。
- 待做：P2 GIF/帧序列批处理（含按视频/图片素材批量阅览）。
- 2026-09-07：记录外部素材与生成管线规划——pixellab.ai（product-ready pixel diffuse，已订阅）→ Gemini 生成 normal map（计划）→ 查看器阅览；pixellab 能否直出 normal map 待确认；查看器暂只支持静态双图，视频阅览待扩展。
