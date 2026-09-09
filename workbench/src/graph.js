// graph —— 画布 ↔ 配方 JSON 的互转与默认图。
// 画布模型即配方模型（线性链）：source 节点 + stage 节点按序连线；
// React Flow 的 node.data.params 即 stage.params。

export const CATEGORY_META = {
  source: { label: "源", color: "#5b8def" },
  transform: { label: "变换", color: "#3faa6b" },
  export: { label: "导出", color: "#c78a2d" },
  gate: { label: "门禁", color: "#c9564a" },
};

export function defaultGraph() {
  return {
    version: 1,
    name: "图像标准化（网格还原 + 16 色）",
    input: { op: "source.images", params: { paths: [], fps: 10 } },
    stages: [
      { op: "grid-sample", params: { grid: "auto", sampling: "mode", bg: "auto" } },
      { op: "quantize", params: { colors: 16 } },
      { op: "export-frames" },
      { op: "export-sheet", params: { "source-route": "sampled" } },
    ],
    output: { dir: "/out" },
  };
}

/** 配方 JSON → React Flow nodes/edges（纵向线性布局） */
export function graphToFlow(graph) {
  const nodes = [];
  const edges = [];
  const seq = [
    { id: "input", op: graph.input.op, params: graph.input.params || {}, category: "source" },
    ...(graph.stages || []).map((st, i) => ({
      id: "s" + i, op: st.op, params: st.params || {}, category: null,
    })),
  ];
  seq.forEach((s, i) => {
    nodes.push({
      id: s.id,
      type: "stage",
      position: { x: 360, y: 40 + i * 150 },
      data: { op: s.op, params: s.params, isSource: i === 0, index: i },
      draggable: true,
    });
    if (i > 0) {
      edges.push({
        id: seq[i - 1].id + "-" + s.id,
        source: seq[i - 1].id,
        target: s.id,
        type: "smoothstep",
      });
    }
  });
  return { nodes, edges };
}

/** React Flow nodes → 配方 JSON（按 y 坐标排序恢复线性顺序） */
export function flowToGraph(nodes, graphName = "(未命名)") {
  const sorted = [...nodes].sort((a, b) => a.position.y - b.position.y);
  const source = sorted.find((n) => n.data.isSource) || sorted[0];
  const stages = sorted
    .filter((n) => n !== source)
    .map((n) => {
      const st = { op: n.data.op };
      const params = cleanParams(n.data.params);
      if (params && Object.keys(params).length) st.params = params;
      return st;
    });
  return {
    version: 1,
    name: graphName,
    input: { op: source.data.op, params: cleanParams(source.data.params) || {} },
    stages,
    output: { dir: "/out" },
  };
}

/** 去掉 undefined / 空字符串等无效参数（保持配方干净） */
function cleanParams(params) {
  const out = {};
  for (const [k, v] of Object.entries(params || {})) {
    if (v === undefined || v === "" || v === null) continue;
    if (Array.isArray(v) && v.length === 0) continue;
    out[k] = v;
  }
  return out;
}
