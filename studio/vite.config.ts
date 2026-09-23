import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/archcanvas_studio/static",
    emptyOutDir: true,
    assetsDir: "assets",
  },
});
