# workbench/ —— 像素管线节点工作台（浏览器版，节点系统 Phase 1）

> **版本 v0.1.0**（2026-09-09 首版：画布编辑配方 + 浏览器内执行 + 产物下载）

## 定位与架构

「**一核两宿主**」的浏览器半边：React Flow 画布编辑**管线配方 JSON**（Phase 0 定义的
`pipeline.py` version 1 线性 stage），执行交给 **Pyodide 加载的 pixel-toolkit 同一份源码**——
构建期经 Vite `?raw` 嵌入（`src/pipelineRuntime.js`），不存在第二份拷贝，与 `pixcli run`/CI
逐字节同产物。

- **权威执行器是 `pixel-toolkit/pipeline.py`**（CPython：CLI/CI/Agent）；本工作台是编辑器 + 宿主
- **处理全在本地浏览器**：素材不经过任何服务器（Pyodide 运行时与 Pillow wheel 均自托管于
  `dist/pyodide/`，加载后零外部请求）
- 节点面板/参数控件由 `pixcli ops` 同源注册表驱动（Pyodide 启动后经 `_ops_registry()` 读取）

## 使用

```bash
cd workbench
npm install
npm run dev        # 开发（自动拷 Pyodide 运行时到 public/pyodide/）
npm run build      # 构建 → dist/（自托管 Pyodide 随产物）
npm run preview    # 本地预览构建产物
npm run smoke      # node 烟测：Pyodide 执行链 + 确定性（无浏览器验证）
```

界面：左侧节点库（源/变换/导出/门禁 四类，点击追加到链尾）· 中央画布（节点可拖动排序，
`×` 删除并自动接线，点选节点）· 右侧参数面板（按注册表声明生成控件）· 底部运行日志与产物
（PNG/GIF 预览 + 逐文件下载）。「导出配方 JSON」得到的文件可直接 `pixcli run`（桌面/CI 复现）。

## 边界（v0.1）

- **`source.video` 浏览器内不可用**（需 ffmpeg）：画布上以警示标出；导出 JSON 交给
  `pixcli run` 执行
- 线性链编辑（DAG 分支是 schema 预留，未实现）；无内容寻址缓存（每次运行全量重算，
  Phase 2）
- 文件输入走 `source.images` 节点上的「选择图像」按钮（多选即帧序列）

## 部署（GitHub Pages）

`.github/workflows/deploy.yml`：push main → 构建 → Pages。`vite.config.js` 用相对 `base`，
项目站子路径可用。（GitHub 免费版私有 fork 的 Pages 不可用，需 Pro；公开仓无此限制。）

## 实测记录（2026-09-09）

- node 烟测（`npm run smoke`）：pipeline 在 Pyodide 内端到端跑通图像链（96→12 格还原 +
  量化 + sheet），两次运行 sha256 一致（确定性成立）
- 浏览器实测：自托管 Pyodide 启动就绪、17 节点注册表加载、默认链渲染、节点点选与参数面板
  均正常；期间发现并修复两处缺陷（节点分类未从注册表取值、op 名未显示）与一处构建问题
  （pyodide.asm 动态导入经 Vite 打包失效 → 改自托管，CDN 亦被实测不稳定）
