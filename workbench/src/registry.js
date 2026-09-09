// 节点注册表单例：Pyodide 启动后由 opsRegistry() 填充（{ name → {title, category, params…} }）
export const registryRef = { current: null };

export function setRegistry(opsJson) {
  const reg = {};
  for (const op of opsJson.ops) reg[op.name] = op;
  registryRef.current = reg;
  return reg;
}
