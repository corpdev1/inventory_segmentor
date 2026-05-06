import type { NextConfig } from "next";

/** Public URL on nginx in production (https://imperium.lh2.online/inventory_segmentor/). Dev uses "". */
const basePath = process.env.NODE_ENV === "production" ? "/inventory_segmentor" : "";

const nextConfig: NextConfig = {
  basePath,
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
};

export default nextConfig;
