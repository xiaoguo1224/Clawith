import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 3008,
        host: '0.0.0.0',
        proxy: {
            '/api': {
                target: 'http://localhost:8008',
                changeOrigin: true,
            },
            '/ws': {
                target: 'ws://localhost:8008',
                ws: true,
            },
        },
    },
})
