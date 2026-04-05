/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    TINSEL_API_URL: process.env.TINSEL_API_URL || "http://localhost:8000",
  },
};

module.exports = nextConfig;
