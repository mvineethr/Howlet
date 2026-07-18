"""Smoke test: the dashboard HTML actually serves and contains the UI.

The JS itself only runs in a browser (and is exercised by live
verification each session), but this catches "the page is broken at the
template level" regressions - a missing critical element, a truncated
file, or the vendored chart library disappearing from the package.
"""

from pathlib import Path

from edgar13f.dashboard import create_app
from edgar13f.views import Services


def _app():
    # Services is never exercised: "/" reads only the HTML file.
    svc = Services.__new__(Services)
    return create_app("Test User test@example.com", services=svc)


def test_index_serves_the_terminal_html():
    client = _app().test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Critical UI anchors the JS boots against.
    for element_id in (
        'id="cmd"', 'id="tabbar"', 'id="dash-grid"', 'id="tape"',
        'id="screen-dash"', 'id="import-file"',
    ):
        assert element_id in html, f"missing {element_id}"
    # The page must never regress to loading chart code from a CDN.
    assert "/static/klinecharts.min.js" in html
    assert "unpkg.com" not in html and "cdn.jsdelivr" not in html


def test_vendored_klinecharts_ships_with_the_package():
    static = Path(__file__).parent.parent / "src" / "edgar13f" / "static"
    assert (static / "klinecharts.min.js").is_file()
    assert (static / "klinecharts.LICENSE").is_file()
