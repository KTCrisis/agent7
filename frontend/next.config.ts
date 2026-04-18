import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    return [
      {
        source: "/api/mesh/:path*",
        destination: "http://localhost:9090/:path*",
      },
      {
        source: "/api/mem7/:path*",
        destination: "http://localhost:9070/:path*",
      },
    ];
  },
};

export default nextConfig;
