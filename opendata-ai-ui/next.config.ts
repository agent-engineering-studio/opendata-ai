import type { NextConfig } from "next";

// Static export for GitHub Pages — no server-side runtime in production.
// The frontend talks directly to the backend at `NEXT_PUBLIC_API_URL`.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  poweredByHeader: false,
  trailingSlash: true,
};

export default nextConfig;
