import { createContext, useContext } from "react";

// React Flow 自定义节点的动作回调（nodeTypes 组件不接收外部 props，经 Context 注入）
export const NodeActionsContext = createContext(null);
export const useNodeActions = () => useContext(NodeActionsContext);
