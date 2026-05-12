import type { NextConfig } from "next";

const basePath = (process.env.CORE_WEB_BASE_PATH || "").trim().replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(basePath ? { basePath } : {}),
};

export default nextConfig;
