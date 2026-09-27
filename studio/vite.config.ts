import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = process.env.ARCHCANVAS_API_URL ?? "http://127.0.0.1:4310";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": apiTarget,
    },
  },
  build: {
    outDir: "../src/archcanvas_studio/static",
    emptyOutDir: true,
    assetsDir: "assets",
  },
});
