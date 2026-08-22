import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow the 127.0.0.1 host to load Next.js dev bundles.
  // Without this, Next.js 16 blocks cross-origin HMR/JS requests from 127.0.0.1,
  // which prevents React from hydrating — making all button clicks silently do nothing.
  allowedDevOrigins: ['127.0.0.1'],
};

export default nextConfig;
