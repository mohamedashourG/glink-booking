/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Server-rendered + middleware — no static export here. Auth requires a
  // server runtime to read the HTTP-only session cookie before each request.
};

module.exports = nextConfig;
