/* 前端口径对拍 · JS 侧执行器（由 parity_frontend.py 调用）
 *
 * 用法：node parity_frontend.js <repo_root> <work_dir>
 * 输入（work_dir 下）：input.json（尺寸/帧数/调色板）、stab_frames.bin、struct_<名>.raw
 * 输出（work_dir 下）：js_out.json、temporal_js.bin、pal_<名>_js.bin
 *
 * 做法：从两个单文件 HTML 里**抽取函数真身**（大括号配对扫描）后 eval——保证测的是页面里真正跑的那份代码，
 * 而不是复制来的副本。
 */
const fs = require('fs');
const path = require('path');

const REPO = process.argv[2] || '.';
const WORK = process.argv[3] || '/tmp/parity';
const VS = fs.readFileSync(path.join(REPO, 'pixel-toolkit/video-studio.html'), 'utf8');
const AI = fs.readFileSync(path.join(REPO, 'asset-inspector/asset-inspector.html'), 'utf8');

function extractFn(html, name) {
  const i0 = html.indexOf('function ' + name + '(');
  if (i0 < 0) throw new Error('未找到函数: ' + name);
  const i = html.slice(Math.max(0, i0 - 6), i0) === 'async ' ? i0 - 6 : i0;
  let depth = 0, k = html.indexOf('{', i), started = false;
  for (; k < html.length; k++) {
    const ch = html[k];
    if (ch === '{') { depth++; started = true; }
    else if (ch === '}') { depth--; if (started && depth === 0) break; }
  }
  return html.slice(i, k + 1);
}
function extractConst(html, name) {
  const m = new RegExp('const ' + name + ' = [^\\n]+;').exec(html);
  if (!m) throw new Error('未找到常量: ' + name);
  return m[0];
}
function load(html, consts, fns) {
  for (const c of consts) eval(extractConst(html, c).replace(/^const /, 'globalThis.'));
  // eval 内的函数声明只在该 eval 作用域可见 → 显式挂到 globalThis
  for (const f of fns) eval('globalThis.' + f + ' = ' + extractFn(html, f));
}
function loadAs(html, name, asName) {
  eval('globalThis.' + asName + ' = ' + extractFn(html, name));
}

// 桩：页面里的运行期依赖
let jobToken = 0;
function setStatus() {}
const yieldUI = () => Promise.resolve();
function $(id) { return { value: '12' }; }   // 仅 sheetMeta 读 fps

load(VS, [], ['computeStability', 'temporalMedianFrames', 'temporalStabilize']);
loadAs(VS, 'sheetMeta', 'vsSheetMeta');
load(AI, ['NEIGH4', 'oklabDist2'], ['hex6', 'rgbToOklab', 'parsePaletteJson',
                                    'mapToPaletteImageData', 'bboxOf', 'structureOf',
                                    'frameGroupIssues', 'downscaleImageData']);
loadAs(AI, 'sheetMeta', 'aiSheetMeta');

const input = JSON.parse(fs.readFileSync(path.join(WORK, 'input.json'), 'utf8'));
const out = {};

// 1) 稳定性判据：合成帧（stab_frames.bin：n 帧连续 RGBA）
{
  const { w, h, n } = input.stab;
  const raw = fs.readFileSync(path.join(WORK, 'stab_frames.bin'));
  const frames = [];
  for (let i = 0; i < n; i++) {
    frames.push({ width: w, height: h,
      data: new Uint8ClampedArray(raw.buffer, raw.byteOffset + i * w * h * 4, w * h * 4) });
  }
  out.stability = computeStability(frames);

  // 2) 时间维滤波（异步）：输出逐字节比对
  temporalMedianFrames(frames, input.temporalW, undefined).then(async (outs) => {
    fs.writeFileSync(path.join(WORK, 'temporal_js.bin'),
      Buffer.concat(outs.map(f => Buffer.from(f.data.buffer, f.data.byteOffset, f.data.length))));

    // 3) 结构检查 + 4) 归板 + 5) sheet 元数据
    const pal = parsePaletteJson(JSON.stringify({ name: input.palette.name, colors: input.palette.colors }));
    const structOut = {};
    const sheetFrames = [];
    for (const item of input.struct) {
      const buf = fs.readFileSync(path.join(WORK, 'struct_' + item.name + '.raw'));
      const id = { width: item.w, height: item.h, data: new Uint8ClampedArray(buf.buffer, buf.byteOffset, buf.length) };
      const s = structureOf(id);
      structOut[item.name] = { bbox: s.bbox, compSizes: s.compSizes, strays: s.strays, strayTotal: s.strayTotal };
      // 归板：先 alpha 两态化（≥128→255）再映射，对齐 inspector 链路
      const d2 = new Uint8ClampedArray(id.data);
      for (let i = 0; i < d2.length; i += 4) d2[i + 3] = d2[i + 3] >= 128 ? 255 : 0;
      const mapped = mapToPaletteImageData({ width: item.w, height: item.h, data: d2 }, pal.colors);
      fs.writeFileSync(path.join(WORK, 'pal_' + item.name + '_js.bin'),
        Buffer.from(mapped.data.buffer, mapped.data.byteOffset, mapped.data.length));
      sheetFrames.push({ width: item.w, height: item.h, data: id.data });
    }
    out.struct = structOut;
    out.paletteName = pal.name;
    out.paletteColors = pal.colors.length;
    out.sheetMeta = vsSheetMeta(sheetFrames, sheetFrames.length, 1, 'track1_sheet.png', 'track1');
    out.sheetMetaAI = aiSheetMeta(sheetFrames, sheetFrames.length, 1, 'ai_sheet.png', 'anim', 'authored');
    out.groupIssues = frameGroupIssues(sheetFrames.map((f, i) => ({ name: 'f' + i, id: f })));

    // 6) 缩格（含 alpha 语义）：对 grid 图跑 1/4 众数缩格
    const gitem = input.struct.find(x => x.name === 'grid');
    const gbuf = fs.readFileSync(path.join(WORK, 'struct_grid.raw'));
    const gid = { width: gitem.w, height: gitem.h,
                  data: new Uint8ClampedArray(gbuf.buffer, gbuf.byteOffset, gbuf.length) };
    const dout = downscaleImageData(gid, 4, 'mode', 0, 0);
    fs.writeFileSync(path.join(WORK, 'down_js.bin'),
      Buffer.from(dout.data.buffer, dout.data.byteOffset, dout.data.length));
    out.downscale = { w: dout.width, h: dout.height };

    // 7) 时间众数稳定（量化后）：JS temporalStabilize ↔ Python temporal_mode_frames
    const stabOut = await temporalStabilize(frames, 3, jobToken);
    fs.writeFileSync(path.join(WORK, 'stabmode_js.bin'),
      Buffer.concat(stabOut.map(f => Buffer.from(f.data.buffer, f.data.byteOffset, f.data.length))));
    fs.writeFileSync(path.join(WORK, 'js_out.json'), JSON.stringify(out));
    console.log('JS 侧完成');
  }).catch(e => { console.error('JS 侧失败: ' + e.message); process.exit(1); });
}
