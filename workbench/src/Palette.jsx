// Palette —— 左侧节点面板（按分类分组，点击追加到链尾）
import { CATEGORY_META } from "./graph.js";
import { registryRef } from "./registry.js";

export default function Palette({ onAdd, disabled }) {
  const reg = registryRef.current || {};
  const groups = ["source", "transform", "export", "gate"]
    .map((cat) => ({
      cat,
      ops: Object.values(reg).filter((o) => o.category === cat),
    }))
    .filter((g) => g.ops.length);

  return (
    <aside className="palette">
      <h2>节点</h2>
      {!groups.length && <p className="hint">Pyodide 启动后可用…</p>}
      {groups.map(({ cat, ops }) => (
        <section key={cat}>
          <h3 style={{ color: CATEGORY_META[cat].color }}>{CATEGORY_META[cat].label}</h3>
          {ops.map((o) => (
            <button
              key={o.name}
              className="pal-item"
              disabled={disabled}
              title={o.title}
              onClick={() => onAdd(o.name)}
            >
              <code>{o.name}</code>
              <span className="pal-title">{o.title}</span>
            </button>
          ))}
        </section>
      ))}
    </aside>
  );
}
