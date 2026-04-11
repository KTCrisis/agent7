import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/mesh/:path*",
        destination: "http://localhost:9090/:path*",
      },
    ];
  },
};

export default nextConfig;
