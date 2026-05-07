import type { NextConfig } from "next";

/**
 * Public URL (behind nginx) is typically served under a subpath like `/inventory_segmentor`.
 * In production, prefer an explicit env override to avoid basePath mismatches that return HTML
 * (and then the client crashes trying to parse JSON).
 */
const basePath =
  process.env.NEXT_PUBLIC_BASE_PATH?.trim() ||
  (process.env.NODE_ENV === "production" ? "/inventory_segmentor" : "");

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
