import pytest
from fastapi.testclient import TestClient

from papertrail.api.web import create_root_app
from papertrail.config import Settings


@pytest.fixture
def dist(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><div id=root></div>")
    (d / "assets" / "app-1a2b.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("do not serve")
    return d


def client(dist, tmp_path):
    s = Settings(
        _env_file=None,
        store_backend="memory",
        upload_dir=str(tmp_path / "up"),
        web_dist_dir=str(dist),
    )
    return TestClient(create_root_app(s))


def test_api_lives_under_api_and_app_at_root(dist, tmp_path):
    c = client(dist, tmp_path)
    assert c.get("/api/health").json()["llm_provider"] == "mock"
    assert c.get("/api/rulebook").status_code == 200
    home = c.get("/")
    assert "id=root" in home.text and home.headers["cache-control"] == "no-cache"
    assert home.headers["x-frame-options"] == "DENY"


def test_client_routes_fall_back_to_index_and_assets_are_cached(dist, tmp_path):
    c = client(dist, tmp_path)
    assert "id=root" in c.get("/checks/chk_123").text
    asset = c.get("/assets/app-1a2b.js")
    assert asset.text == "console.log(1)" and "immutable" in asset.headers["cache-control"]


def test_no_path_traversal_and_unknown_api_paths_404(dist, tmp_path):
    c = client(dist, tmp_path)
    assert "do not serve" not in c.get("/../secret.txt").text
    assert "do not serve" not in c.get("/%2e%2e/secret.txt").text
    assert c.get("/api/nope").status_code == 404


def test_missing_build_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match="npm run build"):
        client(tmp_path / "missing", tmp_path)


def test_without_web_dist_the_api_is_served_at_root(tmp_path):
    s = Settings(_env_file=None, store_backend="memory", upload_dir=str(tmp_path / "up"))
    assert TestClient(create_root_app(s)).get("/health").status_code == 200
