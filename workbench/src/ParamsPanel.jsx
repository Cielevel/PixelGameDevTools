// ParamsPanel —— 右侧选中节点的参数编辑器（按注册表声明逐参数生成控件）
import { registryRef } from "./registry.js";

function defaultFor(decl) {
  if (decl.default !== undefined && decl.default !== null) return structuredClone(decl.default);
  if (decl.type === "strlist") return [];
  if (decl.type === "size" || decl.type === "box") return null;
  return "";
}

function ParamInput({ decl, value, onChange }) {
  const base = decl.type.split(":")[0];
  if (base === "choice") {
    const opts = decl.type.split(":", 2)[1].split("|");
    return (
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {opts.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  }
  if (base === "bool") {
    return (
      <input
        type="checkbox"
        checked={!!value}
        onChange={(e) => onChange(e.target.checked)}
      />
    );
  }
  if (base === "color") {
    return (
      <div className="color-row">
        <input
          type="color"
          value={/^#[0-9a-fA-F]{6}$/.test(value ?? "") ? value : "#182b54"}
          onChange={(e) => onChange(e.target.value)}
        />
        <input
          type="text"
          value={value ?? ""}
          placeholder="#rrggbb"
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
    );
  }
  if (base === "size" || base === "box") {
    const arr = Array.isArray(value) ? value : [];
    const n = base === "size" ? 2 : 4;
    const labels = base === "size" ? ["宽", "高"] : ["x0", "y0", "x1", "y1"];
    return (
      <div className="tuple-row">
        {labels.map((lb, i) => (
          <label key={i}>
            {lb}
            <input
              type="number"
              value={arr[i] ?? ""}
              onChange={(e) => {
                const next = [...arr];
                while (next.length < n) next.push(0);
                next[i] = Number(e.target.value);
                onChange(next);
              }}
            />
          </label>
        ))}
      </div>
    );
  }
  if (base === "grid") {
    return (
      <input
        type="text"
        value={value ?? "auto"}
        placeholder='auto / 8 / [w,h]'
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  if (base === "int" || base === "float") {
    return (
      <input
        type="number"
        step={base === "float" ? "any" : "1"}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
      />
    );
  }
  return (
    <input type="text" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
  );
}

export default function ParamsPanel({ node, registry, onParam }) {
  if (!node) return <aside className="params"><h2>参数</h2><p className="hint">点选画布节点编辑参数</p></aside>;
  const reg = registryRef.current?.[node.data.op];
  const io = reg?.io || ["", ""];
  return (
    <aside className="params">
      <h2>{reg?.title || node.data.op}</h2>
      <p className="mono">{node.data.op}　·　端口 {io[0] || "-"} → {io[1]}</p>
      {!reg?.params?.length && <p className="hint">该节点无参数</p>}
      {(reg?.params || []).filter((d) => d.key !== "paths").map((d) => (
        <div className="param" key={d.key}>
          <label>
            <span className="param-key">
              {d.key}
              {d.required ? " *" : ""}
            </span>
            <span className="param-help">{d.help}</span>
          </label>
          <ParamInput
            decl={d}
            value={node.data.params?.[d.key] ?? defaultFor(d)}
            onChange={(v) => onParam(d.key, v)}
          />
        </div>
      ))}
      {node.data.op === "source.images" && (
        <p className="hint">输入文件在节点上选择（paths 由所选文件自动填充）</p>
      )}
    </aside>
  );
}
