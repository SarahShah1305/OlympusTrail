# Static hosting on Vercel

The existing FastAPI `app.frontend()` serves the built Vite output. [Vercel documents](https://vercel.com/changelog/fastapi-frontends-and-static-files-served-from-the-cdn) build-time CDN promotion for FastAPI frontends, but static files behind middleware stay on the function unless `tool.vercel.fastapi.static.cdn = true` is set. The cache middleware therefore intentionally preserves function-side headers; do not enable forced CDN promotion without independently configuring and testing equivalent CDN headers.

For a future CDN migration, configure static-path headers on Vercel and verify `/`, `/index.html`, `/assets/*`, `/layers/*`, and each API endpoint in a preview deployment. Keep API routes ahead of any frontend catch-all. No routing change is proposed without deployment verification.

## Candidate preview configuration (not applied)

The current FastAPI adapter can promote `app.frontend()` itself. Keep the existing `index.py` entrypoint, `buildCommand`, and `functions` configuration. Do not switch the project to Vite-only `outputDirectory` hosting or add a catch-all rewrite: that is a different build pipeline and has not been verified here.

In a preview only, merge this into `pyproject.toml` to opt the public frontend into the adapter's documented CDN promotion despite the cache middleware:

```toml
[tool.vercel.fastapi.static]
cdn = true
```

Merge the following `headers` into the existing `vercel.json` so the CDN has the same policy as the local middleware:

```json
{
  "headers": [
    { "source": "/assets/(.*)", "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }] },
    { "source": "/layers/(.*)", "headers": [{ "key": "Cache-Control", "value": "public, max-age=86400, stale-while-revalidate=604800" }] },
    { "source": "/", "headers": [{ "key": "Cache-Control", "value": "no-cache" }] },
    { "source": "/index.html", "headers": [{ "key": "Cache-Control", "value": "no-cache" }] }
  ]
}
```

The `/assets/` policy assumes Vite's hashed output only. Keep `exclude` unset so static sources stay available to the Python app as a fallback. Confirm API paths (`/sites`, `/route`, `/ask`, `/health`, `/data-status`, `/shelters`, `/terrain`, `/briefing-data`) still reach FastAPI, SPA fallback works, and repeat asset requests no longer invoke the Python function. This is a documented candidate, not a tested Vercel deployment.
