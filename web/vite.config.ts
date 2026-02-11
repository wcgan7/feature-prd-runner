import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react') || id.includes('node_modules/scheduler')) return 'framework'
          if (id.includes('node_modules/@mui')) return 'mui'
          if (id.includes('node_modules/@xyflow')) return 'graph'
          if (id.includes('/src/components/KanbanBoard/')) return 'kanban'
          if (id.includes('/src/components/AgentCard/')) return 'agents'
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
      },
    },
  },
})
