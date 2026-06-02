import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// TAURI_DEV_HOST é definido pelo Tauri em targets mobile; no desktop é undefined
const host = process.env.TAURI_DEV_HOST

export default defineConfig({
  plugins: [react()],

  // Tauri exige que o Vite não limpe o terminal (ele próprio gerencia o output)
  clearScreen: false,

  server: {
    port: 5173,
    // Porta fixa — o Tauri aponta para ela no tauri.conf.json
    strictPort: true,
    host: host || false,
    hmr: host ? { protocol: 'ws', host, port: 5173 } : undefined,
    watch: {
      // Ignora o src-tauri para não recarregar o Vite com mudanças de Rust
      ignored: ['**/src-tauri/**'],
    },
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },

  // Previne que o Vite tente criar um worker para o Tauri
  envPrefix: ['VITE_', 'TAURI_ENV_*'],
})
