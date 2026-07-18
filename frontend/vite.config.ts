import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const adkApiTarget = (env.ADK_API_PROXY_TARGET || 'http://127.0.0.1:8000').replace(
    /\/$/,
    '',
  );
  const bookingApiTarget = (
    env.BOOKING_API_PROXY_TARGET || 'http://127.0.0.1:8002'
  ).replace(/\/$/, '');

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/booking-api': {
          target: bookingApiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/booking-api/, ''),
        },
        '/adk-api': {
          target: adkApiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/adk-api/, ''),
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyRequest) => {
              proxyRequest.setHeader('origin', adkApiTarget);
            });
          },
        },
      },
    },
  };
});
