"""The browser UI is static files served by the API. These check that it is
wired up and speaks to the real routes, not how it behaves in a browser."""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_the_root_redirects_to_the_ui(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"


def test_the_ui_without_a_trailing_slash_redirects(client):
    response = client.get("/ui", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].endswith("/ui/")


def test_the_page_is_served(client):
    response = client.get("/ui/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<title>Legal Review Agent</title>" in response.text


@pytest.mark.parametrize("asset, content_type", [("app.js", "javascript"), ("styles.css", "text/css")])
def test_the_assets_are_served(client, asset, content_type):
    response = client.get(f"/ui/{asset}")

    assert response.status_code == 200
    assert content_type in response.headers["content-type"]


def test_the_page_loads_its_assets_by_absolute_path(client):
    """Relative paths would break when the page is opened as /ui instead of /ui/."""
    page = client.get("/ui/").text

    assert 'src="/ui/app.js"' in page
    assert 'href="/ui/styles.css"' in page


def test_the_script_drives_the_real_routes(client):
    """Guards against the page drifting from the endpoints it calls."""
    script = client.get("/ui/app.js").text
    paths = app.openapi()["paths"]

    assert "/legal" in paths and 'api("/legal"' in script
    assert "/legal/{task_id}" in paths and "api(`/legal/${encodeURIComponent(taskId)}`)" in script
    assert "/legal/{task_id}/respond" in paths and "/respond`" in script
    assert "/health" in paths and 'api("/health")' in script


def test_the_script_never_uses_inner_html(client):
    """Model output is rendered as text; innerHTML would let it inject markup."""
    assert "innerHTML" not in client.get("/ui/app.js").text


def test_the_ui_stays_out_of_the_api_schema(client):
    paths = app.openapi()["paths"]

    assert "/" not in paths
    assert not any(path.startswith("/ui") for path in paths)
