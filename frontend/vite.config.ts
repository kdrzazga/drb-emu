import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendUrl = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": backendUrl,
      "/health": backendUrl,
    },
  },
  build: {
    chunkSizeWarningLimit: 6000,
  },
});
