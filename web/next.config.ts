import type { NextConfig } from "next";

/** Served at https://imperium.lh2.online/inventory_segmentor/ (nginx → localhost:3004) */
const basePath = "/inventory_segmentor";

const nextConfig: NextConfig = {
  basePath,
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
};

export default nextConfig;
