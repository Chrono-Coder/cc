import type { NextConfig } from "next";

// `cc web` builds + runs this in place via `next start`, so no `output:
// standalone` — on Next 16 + Node 26 the standalone server.js exits immediately
// (and `next start` refuses to serve when standalone is set).
const nextConfig: NextConfig = {};

export default nextConfig;
