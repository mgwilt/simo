import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: "../.artifacts/breeze-performance/preview-site",
    emptyOutDir: false,
    rollupOptions: { input: "preview.html" },
  },
});
