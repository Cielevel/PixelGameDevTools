import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";

import Palette from "./Palette.jsx";
import ParamsPanel from "./ParamsPanel.jsx";
import ResultsPanel from "./ResultsPanel.jsx";
import StageNode from "./StageNode.jsx";
import { defaultGraph, graphToFlow, flowToGraph, CATEGORY_META } from "./graph.js";
import { boot, opsRegistry, putInputFiles, runGraph, resetOutDir } from "./pipelineRuntime.js";
import { registryRef, setRegistry } from "./registry.js";
import { NodeActionsContext } from "./nodeActions.js";

const nodeTypes = { stage: StageNode };

export default function App() {
  const initial = useMemo(() => graphToFlow(defaultGraph()), []);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [selectedId, setSelectedId] = useState(null);
  const [bootState, setBootState] = useState("booting");
  const [bootLog, setBootLog] = useState("启动中…");
  const [logs, setLogs] = useState([]);
  const [files, setFiles] = useState([]);
  const [running, setRunning] = useState(false);
  const [graphName, setGraphName] = useState(defaultGraph().name);
  const [, setRegVersion] = useState(0); // 注册表就绪后触发重渲染
  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const fileInputRef = useRef(null);

  useEffect(() => {
    boot((msg) => setBootLog(msg))
      .then(() => {
        setRegistry(opsRegistry());
        setRegVersion((v) => v + 1);
        setBootState("ready");
      })
      .catch((e) => {
        setBootLog("启动失败：" + e);
        setBootState("error");
      });
  }, []);

  const log = useCallback((msg) => setLogs((ls) => [...ls, msg]), []);

  const onAdd = useCallback(
    (op) => {
      const ns = nodesRef.current;
      const maxY = ns.length ? Math.max(...ns.map((n) => n.position.y)) : 0;
      const prev = ns.length ? [...ns].sort((a, b) => a.position.y - b.position.y).pop() : null;
      const id = "s" + Math.random().toString(36).slice(2, 8);
      setNodes([
        ...ns,
        {
          id,
          type: "stage",
          position: { x: 360, y: maxY + 150 },
          data: { op, params: {}, isSource: false },
        },
      ]);
      if (prev) {
        setEdges((es) => [
          ...es,
          { id: prev.id + "-" + id, source: prev.id, target: id, type: "smoothstep" },
        ]);
      }
    },
    [setNodes, setEdges],
  );

  const onDeleteNode = useCallback(
    (id) => {
      setNodes((ns) => ns.filter((n) => n.id !== id));
      setEdges((es) => {
        const inEdge = es.find((e) => e.target === id);
        const outEdge = es.find((e) => e.source === id);
        let next = es.filter((e) => e.source !== id && e.target !== id);
        if (inEdge && outEdge) {
          next = [
            ...next,
            {
              id: inEdge.source + "-" + outEdge.target,
              source: inEdge.source,
              target: outEdge.target,
              type: "smoothstep",
            },
          ];
        }
        return next;
      });
      setSelectedId((cur) => (cur === id ? null : cur));
    },
    [setNodes, setEdges],
  );

  const onPickFiles = useCallback(
    async (fileList) => {
      if (!fileList?.length) return;
      try {
        const paths = await putInputFiles(fileList);
        setNodes((ns) =>
          ns.map((n) =>
            n.data.isSource
              ? { ...n, data: { ...n.data, params: { ...n.data.params, paths } } }
              : n,
          ),
        );
        log(`输入 ${paths.length} 个文件 → ${paths[0]}${paths.length > 1 ? " …" : ""}`);
      } catch (e) {
        log("输入文件写入失败：" + e);
      }
    },
    [setNodes, log],
  );

  const onParam = useCallback(
    (key, value) => {
      setNodes((ns) =>
        ns.map((n) =>
          n.id === selectedId
            ? { ...n, data: { ...n.data, params: { ...n.data.params, [key]: value } } }
            : n,
        ),
      );
    },
    [setNodes, selectedId],
  );

  const onRun = useCallback(async () => {
    if (bootState !== "ready" || running) return;
    // 输入未就绪的友好提示（先于后端校验，直接告诉用户去哪点）
    const src = nodesRef.current.find((n) => n.data.isSource);
    if (src?.data.op === "source.images" && !src.data.params?.paths?.length) {
      setLogs(["✗ 还没有输入图像——点上方「📁 选择输入图像」按钮，或画布源节点上的「选择图像 / 帧序列…」"]);
      return;
    }
    setRunning(true);
    setLogs([]);
    setFiles([]);
    resetOutDir();
    const graph = flowToGraph(nodesRef.current, graphName);
    try {
      const { report, files: out } = await runGraph(graph, log);
      if (report.error) log("✗ " + report.error);
      const okGates = report.gates.filter(([, ok]) => ok).length;
      log(
        `[汇总] 门禁 ${okGates}/${report.gates.length} 通过 → ` +
          (report.ok ? "通过" : "不通过"),
      );
      setFiles(out);
    } catch (e) {
      log("✗ 执行失败：" + e);
    } finally {
      setRunning(false);
    }
  }, [bootState, running, graphName, log]);

  const exportJson = useCallback(() => {
    const graph = flowToGraph(nodesRef.current, graphName);
    graph.output = { dir: "out/" }; // 交给 pixcli run 时用仓库相对目录
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(graph, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "pipeline.json";
    a.click();
    URL.revokeObjectURL(url);
  }, [graphName]);

  const importJson = useCallback(
    async (file) => {
      try {
        const graph = JSON.parse(await file.text());
        if (graph.version !== 1) throw new Error("只支持 version 1");
        setGraphName(graph.name || "(未命名)");
        const flow = graphToFlow(graph);
        setNodes(flow.nodes);
        setEdges(flow.edges);
        log("已载入配方：" + (graph.name || file.name));
      } catch (e) {
        log("✗ 载入失败：" + e);
      }
    },
    [setNodes, setEdges, log],
  );

  const reset = useCallback(() => {
    const g = defaultGraph();
    setGraphName(g.name);
    const flow = graphToFlow(g);
    setNodes(flow.nodes);
    setEdges(flow.edges);
    setLogs([]);
    setFiles([]);
  }, [setNodes, setEdges]);

  const selectedNode = nodes.find((n) => n.id === selectedId) || null;
  const nInputs = (() => {
    const src = nodes.find((n) => n.data.isSource);
    return src?.data.params?.paths?.length || 0;
  })();

  return (
    <div className="app">
      <header>
        <h1>
          像素管线工作台
          <span className="sub">配方与 pixcli run 同核心 · 处理全在本地浏览器，素材不上传</span>
        </h1>
        <div className="toolbar">
          <span className={"chip " + bootState}>
            {bootState === "ready" ? "Pyodide 就绪" : bootLog}
          </span>
          <label className={"pick-btn" + (nInputs ? " has-files" : "")}>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              multiple
              hidden
              onChange={(e) => onPickFiles(e.target.files)}
            />
            {nInputs ? `📁 输入图像 ×${nInputs}` : "📁 选择输入图像"}
          </label>
          <button className="primary" disabled={bootState !== "ready" || running} onClick={onRun}>
            {running ? "运行中…" : "▶ 运行"}
          </button>
          <button onClick={exportJson}>导出配方 JSON</button>
          <button onClick={() => fileInputRef.current?.click()}>载入配方 JSON</button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json"
            hidden
            onChange={(e) => e.target.files[0] && importJson(e.target.files[0])}
          />
          <button onClick={reset}>重置默认图</button>
        </div>
      </header>
      <main>
        <Palette onAdd={onAdd} disabled={bootState !== "ready"} />
        <div className="canvas">
          <NodeActionsContext.Provider value={{ onDelete: onDeleteNode, onPickFiles }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={(_, n) => setSelectedId(n.id)}
              onPaneClick={() => setSelectedId(null)}
              fitView
            >
              <Background color="#2a2f3a" gap={18} />
              <MiniMap pannable zoomable nodeColor={categoryColor} />
              <Controls />
            </ReactFlow>
          </NodeActionsContext.Provider>
        </div>
        <ParamsPanel node={selectedNode} onParam={onParam} />
      </main>
      <ResultsPanel logs={logs} files={files} running={running} />
    </div>
  );
}

function categoryColor(node) {
  const op = node.data?.op;
  const cat = registryRef.current?.[op]?.category;
  return CATEGORY_META[cat || "transform"].color;
}
