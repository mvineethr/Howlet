"""Smoke test: the React app shell actually serves.

The JS itself only runs in a browser (and is exercised by live
verification each session), but this catches "the page is broken at the
template level" regressions - a missing critical element, a truncated
file, or the vendored chart library disappearing from the package.
"""

from pathlib import Path

from howlet.dashboard import create_app
from howlet.views import Services


def _app():
    # Services is never exercised: "/" reads only the built index.html.
    svc = Services.__new__(Services)
    return create_app("Test User test@example.com", services=svc)


def test_index_serves_the_react_app():
    resp = _app().test_client().get("/")
    assert resp.status_code == 200
    assert 'id="root"' in resp.get_data(as_text=True)


def test_vendored_klinecharts_ships_with_the_package():
    static = Path(__file__).parent.parent / "src" / "howlet" / "static"
    assert (static / "klinecharts.min.js").is_file()
    assert (static / "klinecharts.LICENSE").is_file()
