import type { NextConfig } from "next";

/** Public URL on nginx in production (https://imperium.lh2.online/inventory_segmentor/). Dev uses "". */
const basePath = process.env.NODE_ENV === "production" ? "/inventory_segmentor" : "";

const nextConfig: NextConfig = {
  basePath,
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
  // Jobs table polls /api/jobs every few seconds; skip dev spam in the terminal.
  logging: {
    incomingRequests: {
      ignore: [/\/api\/jobs/],
    },
  },
};

export default nextConfig;
