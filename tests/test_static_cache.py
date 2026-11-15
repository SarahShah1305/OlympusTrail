from fastapi.testclient import TestClient

from index import app


def test_static_cache_headers():
    with TestClient(app) as client:
        assert client.get("/").headers["cache-control"] == "no-cache"
        assert client.get("/index.html").headers["cache-control"] == "no-cache"
        assert client.get("/layers/layers.json").headers["cache-control"] == "public, max-age=86400, stale-while-revalidate=604800"
        asset = next((__import__("pathlib").Path("frontend/dist/assets")).glob("*.js"))
        assert client.get("/assets/" + asset.name).headers["cache-control"] == "public, max-age=31536000, immutable"
