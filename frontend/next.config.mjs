// CSP is production-only: `next dev`'s webpack HMR client needs a ws://
// connection and eval-based source maps that a strict policy would
// block, and getting that dev-only exception wrong is worse than just
// not shipping a CSP in dev, where it protects nothing anyway (no real
// users hit that server). The other headers below carry no such
// dev/prod tradeoff and apply everywhere.
//
// 'unsafe-inline' on script/style is deliberate even in production:
// Next.js App Router hydration relies on inline bootstrap scripts and
// framer-motion injects inline styles at runtime — without these the
// app breaks outright, not just cosmetically. `frame-ancestors 'none'`
// is the actual clickjacking control here (stronger than
// X-Frame-Options, which is also set below for older browsers that
// ignore CSP). connect-src includes NEXT_PUBLIC_API_BASE_URL so the
// browser can call the backend directly (claim create/analyze/retrieve
// all happen client-side).
const backendOrigin = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https:",
  `connect-src 'self' ${backendOrigin}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const baseHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async headers() {
    const headers = process.env.NODE_ENV === "production"
      ? [...baseHeaders, { key: "Content-Security-Policy", value: CSP }]
      : baseHeaders;
    return [{ source: "/:path*", headers }];
  },
};

export default nextConfig;
