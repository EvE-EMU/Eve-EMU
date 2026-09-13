import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  distDir: process.env.NEXT_BUILD_DIR || ".next",
  poweredByHeader: false,
  compress: true,
};

export default nextConfig;
