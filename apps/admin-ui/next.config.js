/** @type {import('next').NextConfig} */

// Origins allowed to iframe the /portal/embed page. cal.diy is the
// expected framer; we also allow 'self' for ad-hoc testing in admin-ui.
// In production, CAL_PUBLIC_BASE points at the deployed cal.diy.
const frameAncestors = [
  "'self'",
  process.env.CAL_PUBLIC_BASE || "http://localhost:3000",
  // Allow the deployed cal.diy host too so production Just Works after
  // a routine deploy without re-setting env. Harmless if unused.
  "https://glnk-booking.fly.dev",
]
  .filter(Boolean)
  .join(" ");

const nextConfig = {
  reactStrictMode: true,
  // Server-rendered + middleware — no static export here. Auth requires a
  // server runtime to read the HTTP-only session cookie before each request.
  async headers() {
    return [
      {
        // CSP frame-ancestors authorizes cal.diy (and ourselves) to embed
        // this route in an iframe. Replaces the older X-Frame-Options.
        // Scoped to /portal/embed so admin-ui's dashboard/login can't be
        // framed by anyone — defense in depth against clickjacking.
        source: "/portal/embed",
        headers: [
          {
            key: "Content-Security-Policy",
            value: `frame-ancestors ${frameAncestors}`,
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
