// ResultsPanel —— 底部运行日志 + 产物区（PNG 预览 / GIF 预览 / 逐文件下载）
import { useMemo } from "react";

export default function ResultsPanel({ logs, files, running }) {
  const urls = useMemo(
    () => files.map((f) => ({ ...f, url: URL.createObjectURL(new Blob([f.bytes])) })),
    [files],
  );
  return (
    <section className="results">
      <div className="logs">
        <h2>运行日志{running ? " …" : ""}</h2>
        <pre>{logs.join("\n") || "（尚未运行）"}</pre>
      </div>
      <div className="artifacts">
        <h2>产物（{urls.length}）</h2>
        {!urls.length && <p className="hint">运行后这里显示导出文件</p>}
        <div className="art-list">
          {urls.map((f) => (
            <figure key={f.path} className="art-item">
              {/\.(png|gif)$/i.test(f.name) ? (
                <img
                  src={f.url}
                  alt={f.name}
                  className={f.name.endsWith(".gif") ? "pixelated" : "pixelated zoomable"}
                />
              ) : (
                <div className="art-file">{f.name}</div>
              )}
              <figcaption>
                <span className="art-name">{f.name}</span>
                <a href={f.url} download={f.name}>
                  下载
                </a>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
