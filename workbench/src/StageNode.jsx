// StageNode —— 画布节点：分类配色 + 参数摘要 + 删除；源节点带文件选择按钮
import { Handle, Position } from "@xyflow/react";
import { CATEGORY_META } from "./graph.js";
import { registryRef } from "./registry.js";
import { useNodeActions } from "./nodeActions.js";

function paramSummary(op, params) {
  const decls = registryRef.current?.[op]?.params || [];
  const parts = [];
  for (const d of decls) {
    const v = params?.[d.key];
    if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) continue;
    if (JSON.stringify(d.default) === JSON.stringify(v)) continue; // 只显示非默认值
    parts.push(`${d.key}=${Array.isArray(v) ? v.join("×") : v}`);
  }
  return parts.join("  ") || "（全默认参数）";
}

export default function StageNode({ id, data, selected }) {
  const actions = useNodeActions();
  const reg = registryRef.current?.[data.op];
  const cat = reg?.category || (data.isSource ? "source" : "transform");
  const meta = CATEGORY_META[cat];
  const isVideoSource = data.op === "source.video";
  return (
    <div
      className="stage-node"
      style={{
        borderColor: selected ? "#fff" : meta.color,
        boxShadow: selected ? `0 0 0 2px ${meta.color}` : "none",
      }}
    >
      {!data.isSource && <Handle type="target" position={Position.Top} />}
      <div className="stage-head" style={{ background: meta.color + "26" }}>
        <span className="stage-cat" style={{ color: meta.color }}>
          {meta.label}
        </span>
        <span className="stage-title">{reg?.title || data.op}</span>
        {!data.isSource && (
          <button
            className="stage-del"
            title="删除节点"
            onClick={() => actions?.onDelete(id)}
          >
            ×
          </button>
        )}
      </div>
      <div className="stage-opname">{data.op}</div>
      {isVideoSource && (
        <div className="stage-warn">需 ffmpeg——浏览器内不可用，可导出 JSON 交给 pixcli run</div>
      )}
      {data.op === "source.images" && (
        <label className="stage-files">
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            multiple
            hidden
            onChange={(e) => actions?.onPickFiles(e.target.files)}
          />
          选择图像 / 帧序列…
        </label>
      )}
      <div className="stage-summary">{paramSummary(data.op, data.params)}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

