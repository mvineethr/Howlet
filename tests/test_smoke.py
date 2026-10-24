"""Smoke test: the React app shell actually serves.

The JS itself only runs in a browser (and is exercised by live
verification each session), but this catches "the page is broken at the
template level" regressions - a missing critical element, a truncated
file.
"""

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
