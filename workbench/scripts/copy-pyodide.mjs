// 把 npm pyodide 包的运行时文件拷进 public/pyodide/（gitignore，不入库）。
// - dev：vite 直接服务 public/；build：vite 把 public/ 一并拷进 dist/ → 同源自托管，
//   无 CDN 依赖（jsdelivr 慢/失效时实测会掐断 asm 动态导入，2026-09-09）
// - Pillow wheel 一并拷入：loadPackage("Pillow") 本地解析，全程零外部请求
import { cpSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, "../node_modules/pyodide");
const dst = path.resolve(here, "../public/pyodide");

const keep = [
  "pyodide.mjs",
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
  "pillow-12.2.0-cp314-cp314-pyemscripten_2026_0_wasm32.whl",
];

rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });
for (const f of keep) cpSync(path.join(src, f), path.join(dst, f));
console.log(`[copy-pyodide] ${keep.length} 个文件 → public/pyodide/（自托管运行时）`);
