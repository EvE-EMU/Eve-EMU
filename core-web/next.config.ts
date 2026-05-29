import type { NextConfig } from "next";

const basePath = (process.env.CORE_WEB_BASE_PATH || "").trim().replace(/\/$/, "");
const authUrl = (
  process.env.NEXT_PUBLIC_AUTH_URL || "https://auth.eve-emu.com"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  ...(basePath ? { basePath } : {}),
  async redirects() {
    return [
      {
        source: "/dashboard",
        destination: `${authUrl}/dashboard/`,
        permanent: false,
      },
      {
        source: "/dashboard/:path*",
        destination: `${authUrl}/dashboard/:path*`,
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
