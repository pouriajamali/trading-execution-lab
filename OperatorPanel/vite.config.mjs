import { defineConfig } from 'vite';

export default defineConfig({
  base: '/panel/',
  build: { outDir: '../ExecutionLab.Api/wwwroot/panel', emptyOutDir: true }
});
