/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  env: {
    NEXT_PUBLIC_ARTIFACT_API_URL: process.env.ARTIFACT_API_URL || 'http://localhost:3001',
    NEXT_PUBLIC_WS_URL: process.env.WS_URL || 'ws://localhost:3001',
  },

  headers: async () => [
    {
      source: '/:path*',
      headers: [
        {
          key: 'X-Content-Type-Options',
          value: 'nosniff',
        },
        {
          key: 'X-Frame-Options',
          value: 'DENY',
        },
        {
          key: 'X-XSS-Protection',
          value: '1; mode=block',
        },
      ],
    },
  ],

  rewrites: async () => ({
    beforeFiles: [
      {
        source: '/api/:path*',
        destination: `${process.env.ARTIFACT_API_URL || 'http://localhost:3001'}/api/:path*`,
      },
    ],
  }),

  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.example.com',
      },
    ],
  },
};

module.exports = nextConfig;
