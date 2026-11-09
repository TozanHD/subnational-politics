import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Cloudflare Pages の既存設定（出力先 build/）をそのまま使えるよう outDir を合わせる
export default defineConfig({
  plugins: [react()],
  build: { outDir: 'build' },
});
