import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Listen on all network interfaces (0.0.0.0)
    port: 5173,
    cors: true,
    open: false,
    // Proxy API + media to the backend so the browser only talks to ONE origin (5173).
    // This makes the app work from LAN devices without CORS/firewall/hostname issues.
    proxy: {
      "/api": {
        target: "http://localhost:5170",
        changeOrigin: true,
      },
      "/projects": {
        target: "http://localhost:5170",
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom'],
          'vendor-motion': ['framer-motion'],
          'vendor-icons': ['lucide-react'],
          'vendor-utils': ['axios', 'react-hot-toast']
        }
      }
    }
  }
});
