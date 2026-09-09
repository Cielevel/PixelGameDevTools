// 把 npm pyodide 包的运行时文件拷进 public/pyodide/（gitignore，不入库）。
// - dev：vite 直接服务 public/；build：vite 把 public/ 一并拷进 dist/ → 同源自托管，
//   无 CDN 依赖（jsdelivr 慢/失效时实测会掐断 asm 动态导入，2026-09-09）
// - Pillow wheel 特殊：**不随 npm 包发布**（本机 node_modules 里那份是 Pyodide 运行时
//   从 CDN 下载的缓存，曾在 CI 全新安装下 ENOENT，2026-09-10）——按 pyodide-lock.json
//   的记录名，本地有则拷、没有则从锁定版本的官方 CDN 拉取（构建期联网，运行期仍零外联）
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, "../node_modules/pyodide");
const dst = path.resolve(here, "../public/pyodide");

const pkg = JSON.parse(readFileSync(path.join(src, "package.json"), "utf8"));
const version = pkg.version; // 与 node 烟测、浏览器运行时同版本
const lock = JSON.parse(readFileSync(path.join(src, "pyodide-lock.json"), "utf8"));
const pillowWheel = lock.packages.pillow.file_name;

const baseFiles = [
  "pyodide.mjs",
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
];

rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });

const copied = [];
for (const f of baseFiles) {
  const from = path.join(src, f);
  if (!existsSync(from)) throw new Error(`pyodide 包缺文件: ${f}`);
  cpSync(from, path.join(dst, f));
  copied.push(f);
}

const localWheel = path.join(src, pillowWheel);
if (existsSync(localWheel)) {
  cpSync(localWheel, path.join(dst, pillowWheel));
  copied.push(pillowWheel + "（包内）");
} else {
  const url = `https://cdn.jsdelivr.net/pyodide/v${version}/full/${pillowWheel}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`下载 Pillow wheel 失败 ${res.status}: ${url}`);
  writeFileSync(path.join(dst, pillowWheel), Buffer.from(await res.arrayBuffer()));
  copied.push(pillowWheel + "（CDN 拉取）");
}
console.log(`[copy-pyodide] pyodide v${version} → public/pyodide/（${copied.length} 个文件）`);
