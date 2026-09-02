/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output bundles a minimal server + only the node_modules
  // actually needed at runtime into .next/standalone - this is what
  // keeps the Docker runtime stage small instead of shipping the full
  // node_modules tree (dev dependencies, unused packages) into the image.
  output: "standalone",
};

export default nextConfig;
