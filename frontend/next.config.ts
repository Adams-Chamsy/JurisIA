import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // ── Sécurité ────────────────────────────────────────────────────────────────
  headers: async () => [
    {
      source: '/(.*)',
      headers: [
        { key: 'X-DNS-Prefetch-Control',    value: 'on' },
        { key: 'X-Frame-Options',           value: 'DENY' },
        { key: 'X-Content-Type-Options',    value: 'nosniff' },
        { key: 'Referrer-Policy',           value: 'strict-origin-when-cross-origin' },
        { key: 'Permissions-Policy',        value: 'camera=(), microphone=(), geolocation=()' },
      ],
    },
  ],

  // ── Images ───────────────────────────────────────────────────────────────────
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'avatars.githubusercontent.com' },
      { protocol: 'https', hostname: 'lh3.googleusercontent.com' },
    ],
    formats: ['image/avif', 'image/webp'],
  },

  // ── Redirects ────────────────────────────────────────────────────────────────
  redirects: async () => [
    { source: '/', destination: '/dashboard', permanent: false },
  ],

  // ── Optimisations ────────────────────────────────────────────────────────────
  compress: true,
  poweredByHeader: false,

  // ── Typescript & ESLint ──────────────────────────────────────────────────────
  typescript:  { ignoreBuildErrors: false },
  eslint:      { ignoreDuringBuilds: false },

  // ── Variables d'environnement exposées au client ─────────────────────────────
  env: {
    NEXT_PUBLIC_APP_VERSION: process.env.npm_package_version || '1.0.0',
  },

  // ── Webpack : optimisation des bundles ───────────────────────────────────────
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      '@': require('path').resolve(__dirname, 'src'),
    };
    return config;
  },
};

export default nextConfig;
