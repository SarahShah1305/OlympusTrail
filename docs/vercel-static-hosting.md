# Static hosting on Vercel

The existing FastAPI `app.frontend()` serves the built Vite output. [Vercel documents](https://vercel.com/changelog/fastapi-frontends-and-static-files-served-from-the-cdn) build-time CDN promotion for FastAPI frontends, but static files behind middleware stay on the function unless `tool.vercel.fastapi.static.cdn = true` is set. The cache middleware therefore intentionally preserves function-side headers; do not enable forced CDN promotion without independently configuring and testing equivalent CDN headers.

For a future CDN migration, configure static-path headers on Vercel and verify `/`, `/index.html`, `/assets/*`, `/layers/*`, and each API endpoint in a preview deployment. Keep API routes ahead of any frontend catch-all. No routing change is proposed without deployment verification.
