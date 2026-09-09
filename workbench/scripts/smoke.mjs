// Pyodide 执行链烟测（node 环境，无浏览器）：验证「同一核心可在 Pyodide 宿主跑通」这条架构红线。
// 用法：cd workbench && npm run smoke
// 断言：① pixel-toolkit 源码在 Pyodide 内可 import ② 图像管线端到端出产物
//       ③ 产物与 node 侧无关的自一致（两次运行逐字节一致 = 确定性在 Pyodide 宿主同样成立）
import { readFileSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { loadPyodide } from "pyodide";

const here = path.dirname(fileURLToPath(import.meta.url));
const toolkit = path.resolve(here, "../../pixel-toolkit");

console.log("[smoke] 启动 Pyodide…");
const py = await loadPyodide();
await py.loadPackage("Pillow");

py.FS.mkdirTree("/toolkit/generation");
const files = [
  "anim.py", "atlas.py", "check.py", "palette.py", "pipeline.py",
  "stability.py", "standardize.py", "video.py", "generation/canvas.py",
];
for (const f of files) {
  py.FS.writeFile("/toolkit/" + f, readFileSync(path.join(toolkit, f), "utf8"), {
    encoding: "utf8",
  });
}

py.runPython(`
import sys
sys.path.insert(0, "/toolkit")
import json
import pipeline
from PIL import Image

# 合成输入：96x96、8px 逻辑格（与 pytest 用例同构）
im = Image.new("RGB", (96, 96), (249, 249, 249))
px = im.load()
cols = [(200, 40, 40), (40, 40, 60), (240, 200, 80)]
for cy in range(2, 10):
    for cx in range(2, 10):
        c = cols[(cx + cy) % 3]
        for yy in range(cy * 8, (cy + 1) * 8):
            for xx in range(cx * 8, (cx + 1) * 8):
                px[xx, yy] = c
im.save("/input_grid.png")

def _run():
    graph = {
        "version": 1,
        "name": "pyodide-smoke",
        "input": {"op": "source.images", "params": {"paths": ["/input_grid.png"]}},
        "stages": [
            {"op": "grid-sample", "params": {"grid": "auto"}},
            {"op": "quantize", "params": {"colors": 16}},
            {"op": "export-frames"},
            {"op": "export-sheet", "params": {"source-route": "sampled"}},
        ],
        "output": {"dir": "/out"},
    }
    rep = pipeline.run(graph)
    return rep

rep1 = _run()
import hashlib
def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
hashes1 = {p: _sha(p) for p in rep1["exports"]}

import shutil
for p in list(hashes1):
    shutil.copy(p, p + ".keep")

rep2 = _run()
hashes2 = {p: _sha(p) for p in rep2["exports"]}
kept = {p + ".keep": _sha(p + ".keep") for p in hashes1}

ok_frames = rep1["frames"] == 1
ok_size = Image.open("/out/input_grid_00.png").size == (12, 12)
ok_deterministic = sorted(hashes1.values()) == sorted(kept.values()) and \
    sorted(hashes2.values()) == sorted(kept.values())
ok_gates = rep1["ok"]

result = {"frames": rep1["frames"], "size_ok": ok_size,
          "deterministic": ok_deterministic, "ok": ok_gates and ok_frames and ok_size and ok_deterministic}
print("[smoke] " + json.dumps(result))
assert result["ok"], "Pyodide 宿主干路断言失败"
`);
console.log("[smoke] Pyodide 宿主执行链验证通过 ✓");
