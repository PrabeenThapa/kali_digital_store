import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output mode: dramatically reduces Docker image size (500MB → ~150MB)
  // by only including the files needed to run the app in production.
  output: "standalone",

  // Allow the 127.0.0.1 / VPS host to load Next.js dev bundles.
  allowedDevOrigins: [
    "127.0.0.1",
    "localhost",
    "20.164.209.124",
    "kalidigitalstore.duckdns.org",
    "kalidigitalstore.page.gd",
  ],
};

export default nextConfig;
