/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static-export build: outputs a fully prerendered site to ./out with no
  // server runtime. Required because the whole point of this app is to be
  // serveable when nothing else (bookings@glnkco.com, receiver, internal services) is up.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

module.exports = nextConfig;
