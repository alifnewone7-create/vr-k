/** @type {import('next').NextConfig} */
const nextConfig = {
  // Preview environment runs the dev server behind an external proxy host, so
  // the browser Origin differs from x-forwarded-host. Allowlist both so HMR and
  // Server Actions work. Harmless in production.
  allowedDevOrigins: [
    "auto-km.preview.emergentagent.com",
    "auto-km.cluster-5.preview.emergentcf.cloud",
    "auto-kn-frontend.preview.emergentagent.com",
    "auto-kn-frontend.cluster-5.preview.emergentcf.cloud",
    "autovr-portal.preview.emergentagent.com",
    "autovr-portal.cluster-5.preview.emergentcf.cloud",
    "*.preview.emergentagent.com",
    "*.preview.emergentcf.cloud",
    "*.cluster-5.preview.emergentagent.com",
    "*.cluster-5.preview.emergentcf.cloud",
    "*.emergentagent.com",
    "*.emergentcf.cloud",
  ],
  experimental: {
    serverActions: {
      allowedOrigins: [
        "auto-km.preview.emergentagent.com",
        "auto-km.cluster-5.preview.emergentcf.cloud",
        "auto-kn-frontend.preview.emergentagent.com",
        "auto-kn-frontend.cluster-5.preview.emergentcf.cloud",
        "autovr-portal.preview.emergentagent.com",
        "autovr-portal.cluster-5.preview.emergentcf.cloud",
        "*.preview.emergentagent.com",
        "*.preview.emergentcf.cloud",
        "*.cluster-5.preview.emergentagent.com",
        "*.cluster-5.preview.emergentcf.cloud",
        "*.emergentagent.com",
        "*.emergentcf.cloud",
        "localhost:3000",
      ],
    },
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // Ensure the scripts/*.sql migration files are bundled into the serverless
  // output so lib/db.ts can read + auto-apply them at runtime on Vercel.
  outputFileTracingIncludes: {
    "/**": ["./scripts/**/*.sql"],
  },
}

export default nextConfig
