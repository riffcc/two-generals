import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      // Don't fail if WASM module is not built yet
      external: id => id.includes('/pkg/'),
    },
  },
  server: {
    port: 3000,
    open: true,
    fs: {
      // Allow serving from pkg directory when WASM is built
      allow: ['..'],
    },
  },
  optimizeDeps: {
    // Exclude WASM module from optimization (it's loaded dynamically)
    exclude: ['two-generals-wasm'],
  },
  // Enable WASM import support
  resolve: {
    extensions: ['.js', '.ts', '.wasm'],
  },
  // Serve WASM files with correct MIME type
  assetsInclude: ['**/*.wasm'],
});
