import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// base "./" + single-file output: the desktop app loads index.html over file:// with no server
// and no module chunks to fetch.
export default defineConfig({
  base: "./",
  plugins: [react(), viteSingleFile()],
  clearScreen: false,
  build: { outDir: "dist", emptyOutDir: true },
  server: { port: 5173, strictPort: true },
});
