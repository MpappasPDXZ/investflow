/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['investflowadls.blob.core.windows.net', 'investflowadls.dfs.core.windows.net'],
  },
}

module.exports = nextConfig

