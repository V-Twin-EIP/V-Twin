import type { NextConfig } from 'next'

// Static export served by `vtwin serve` from web/dist on the same loopback origin
// as /api/v1 (ADR 0001). No Node server is needed at runtime.
const nextConfig: NextConfig = {
  output: 'export',
  distDir: 'dist',
  images: { unoptimized: true },
  turbopack: {
    rules: {
      '*.css': {
        loaders: ['@tailwindcss/turbopack'],
        as: '*.css',
      },
    },
  },
}

export default nextConfig
