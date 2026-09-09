import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base 用相对路径：GitHub Pages 项目站（/<repo>/）与本地 dev/preview 都能用
export default defineConfig({
  base: "./",
  plugins: [react()],
  optimizeDeps: { exclude: ["pyodide"] },
  build: { chunkSizeWarningLimit: 12000 },
});
