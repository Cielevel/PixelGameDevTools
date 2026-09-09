// pipelineRuntime —— Pyodide 宿主：加载 pixel-toolkit 同一份源码并执行管线配方。
//
// 架构口径（节点系统 Phase 1）：
// - 浏览器工作台只是「编辑器 + 宿主」，pipeline.py 是权威执行器（与 pixcli/CI 同代码）；
//   源码经 Vite ?raw 在构建期嵌入（单一来源，不存在第二份拷贝）
// - 端口约定：输入文件写入 Pyodide FS /input/，导出落在 /out/，回读为 Uint8Array
// - source.video 需要 ffmpeg，浏览器内不可用（画布上以「桌面版」标记提示）
//
// Pyodide 加载方式：自托管（public/pyodide/，由 scripts/copy-pyodide.mjs 从 npm 包拷出，
// 构建期进 dist/）。同源加载避免 CDN 波动（jsdelivr 慢时 asm 动态导入会被掐断，实测 2026-09-09），
// 且 Pillow wheel 一并自托管——全程零外部请求。
async function loadPyodideSelfHosted() {
  const indexURL = new URL("pyodide/", document.baseURI).href;
  const mod = await import(/* @vite-ignore */ indexURL + "pyodide.mjs");
  return mod.loadPyodide({ indexURL });
}

import animSrc from "../../pixel-toolkit/anim.py?raw";
import atlasSrc from "../../pixel-toolkit/atlas.py?raw";
import canvasSrc from "../../pixel-toolkit/generation/canvas.py?raw";
import checkSrc from "../../pixel-toolkit/check.py?raw";
import paletteSrc from "../../pixel-toolkit/palette.py?raw";
import pipelineSrc from "../../pixel-toolkit/pipeline.py?raw";
import stabilitySrc from "../../pixel-toolkit/stability.py?raw";
import standardizeSrc from "../../pixel-toolkit/standardize.py?raw";
import videoSrc from "../../pixel-toolkit/video.py?raw";

const TOOLKIT_FILES = {
  "anim.py": animSrc,
  "atlas.py": atlasSrc,
  "generation/canvas.py": canvasSrc,
  "check.py": checkSrc,
  "palette.py": paletteSrc,
  "pipeline.py": pipelineSrc,
  "stability.py": stabilitySrc,
  "standardize.py": standardizeSrc,
  "video.py": videoSrc,
};

let py = null;
let bootPromise = null;

async function loadPyodideFromCDN() {
  const mod = await import(/* @vite-ignore */ PYODIDE_CDN + "pyodide.mjs");
  return mod.loadPyodide({ indexURL: PYODIDE_CDN });
}

export async function boot(onStage = () => {}) {
  if (py) return py;
  if (!bootPromise) {
    bootPromise = (async () => {
      onStage("加载 Pyodide 运行时…");
      py = await loadPyodideSelfHosted();
      onStage("加载 Pillow…");
      await py.loadPackage("Pillow");
      onStage("载入 pixel-toolkit 核心…");
      py.FS.mkdirTree("/toolkit");
      for (const [name, src] of Object.entries(TOOLKIT_FILES)) {
        const path = "/toolkit/" + name;
        py.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
        py.FS.writeFile(path, src, { encoding: "utf8" });
      }
      py.runPython(`
import sys
sys.path.insert(0, "/toolkit")
import json as _json
import pipeline as _pipeline


def _run_graph(graph_json, log_fn):
    graph = _json.loads(graph_json)
    try:
        rep = _pipeline.run(graph, log=lambda m: log_fn(m))
        return _json.dumps({
            "ok": rep["ok"],
            "frames": rep.get("frames"),
            "exports": rep.get("exports", []),
            "gates": [[n, ok] for n, ok, _ in rep.get("gates", [])],
        })
    except _pipeline.PipelineError as e:
        return _json.dumps({"ok": False, "error": str(e), "exports": [], "gates": []})


def _ops_registry():
    return _json.dumps(
        {"version": _pipeline.SCHEMA_VERSION,
         "ops": [{k: v for k, v in d.items() if k != "fn"}
                 for d in _pipeline.OPS.values()]},
        ensure_ascii=False)
`);
      onStage("就绪");
      return py;
    })();
  }
  return bootPromise;
}

export function opsRegistry() {
  return JSON.parse(py.runPython("_ops_registry()"));
}

/** 写入用户选中的输入文件 → FS /input/<name>；返回 FS 路径 */
export async function putInputFiles(fileList) {
  py.FS.mkdirTree("/input");
  const paths = [];
  for (const f of fileList) {
    const buf = new Uint8Array(await f.arrayBuffer());
    py.FS.writeFile("/input/" + f.name, buf);
    paths.push("/input/" + f.name);
  }
  return paths;
}

/** 执行配方。files 用于 source.images 的 /input/ 路径桥接。返回 {report, files:[{name,bytes}]} */
export async function runGraph(graph, onLog = () => {}) {
  if (!py) throw new Error("Pyodide 未就绪");
  py.FS.mkdirTree("/out");
  const runPy = py.runPython("_run_graph");
  const raw = runPy(JSON.stringify(graph), (msg) => onLog(String(msg)));
  const report = JSON.parse(raw);
  runPy.destroy?.();
  const files = [];
  const seen = new Set();
  for (const p of report.exports) {
    if (seen.has(p)) continue;
    seen.add(p);
    try {
      const bytes = py.FS.readFile(p); // Uint8Array
      files.push({ name: p.split("/").pop(), path: p, bytes });
    } catch {
      // 导出路径读取失败（如 gate 中间产物）不阻断结果回读
    }
  }
  return { report, files };
}

export function resetOutDir() {
  if (!py) return;
  try {
    py.FS.unlink("/out");
  } catch {}
  py.FS.mkdirTree("/out");
}
