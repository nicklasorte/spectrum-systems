/** @type {import('next').NextConfig} */
const path = require('path');

// VERCEL DEPLOYMENT NOTE:
// Artifact files live at the monorepo root (../../artifacts/...) and are read at
// runtime by loadArtifact(). Next.js static file-tracing cannot follow dynamic
// path.join() calls, so we must explicitly include the artifacts directory via
// outputFileTracingIncludes, and set outputFileTracingRoot to the monorepo root
// so the resolved paths match what loadArtifact() computes at runtime.
//
// Required Vercel project setting: Root Directory = apps/dashboard-3ls
// Required Vercel env var:         REPO_ROOT = /var/task
//
// Deployment is fail-closed: build wiring generates TLS artifacts and must fail
// if artifacts/system_dependency_priority_report.json is missing.

const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  experimental: {
    outputFileTracingRoot: path.join(__dirname, '../..'),
    outputFileTracingIncludes: {
      '/api/**': ['../../artifacts/**/*', '../../artifacts/dashboard_seed/**/*'],
    },
  },
};

module.exports = nextConfig;
