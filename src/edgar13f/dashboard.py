"""Bloomberg-terminal-style web dashboard for edgar13f.

Serves a single-page dark terminal UI (see `dashboard.html`) backed by a
small JSON API. All data assembly lives in `views.py` (shared with the
`edgar13f mcp` AI tool server); this module is just Flask wiring.

Everything stays free/keyless:

  - SEC EDGAR:      13F holdings, Q/Q changes, XBRL fundamentals
  - OpenFIGI:       CUSIP -> ticker mapping (keyless tier, disk-cached)
  - Yahoo Finance:  quotes, charts, world markets tape
  - RSS feeds:      Yahoo Finance / CNBC / MarketWatch / SEC news

Run via `edgar13f dashboard` or:
    from edgar13f.dashboard import run_dashboard
    run_dashboard(user_agent="Jane Doe jane@example.com")
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import requests
from flask import Flask, Response, jsonify, request

from . import views
from .views import Services

# Kept as aliases so existing imports/tests keep working.
DashboardServices = Services
TAPE_SYMBOLS = views.TAPE_SYMBOLS

_HTML_PATH = Path(__file__).parent / "dashboard.html"


def create_app(
    user_agent: str,
    cache_dir: Optional[Path] = None,
    services: Optional[Services] = None,
) -> Flask:
    """Build the Flask app. `services` is injectable for tests."""
    app = Flask(__name__)
    svc = services or Services(user_agent, cache_dir=cache_dir)

    @app.errorhandler(requests.RequestException)
    def upstream_error(exc):
        # Covers HTTPError, ConnectionError, Timeout, ... - the frontend
        # must always get JSON, never Flask's HTML error page.
        return jsonify({"error": f"Upstream request failed: {exc}"}), 502

    @app.errorhandler(LookupError)
    def not_found(exc):
        return jsonify({"error": str(exc)}), 404

    @app.get("/")
    def index() -> Response:
        return Response(_HTML_PATH.read_text(encoding="utf-8"), mimetype="text/html")

    @app.get("/api/managers")
    def managers():
        return jsonify(views.managers_view())

    @app.get("/api/tape")
    def tape():
        return jsonify(views.tape_view(svc))

    @app.get("/api/portfolio/<identifier>")
    def portfolio(identifier: str):
        top = int(request.args.get("top", 25))
        return jsonify(views.portfolio_view(svc, identifier, top=top))

    @app.get("/api/diff/<identifier>")
    def diff(identifier: str):
        return jsonify(views.diff_view(svc, identifier))

    @app.get("/api/consensus")
    def consensus():
        min_managers = int(request.args.get("min", 2))
        limit = int(request.args.get("limit", 20))
        return jsonify(views.consensus_view(svc, min_managers=min_managers, limit=limit))

    @app.get("/api/holders/<symbol>")
    def holders(symbol: str):
        return jsonify(views.holders_view(svc, symbol))

    @app.get("/api/position-history/<identifier>/<query>")
    def position_history(identifier: str, query: str):
        quarters = int(request.args.get("quarters", 8))
        return jsonify(
            views.position_history_view(svc, identifier, query, quarters=quarters)
        )

    @app.get("/api/insiders/<symbol>")
    def insiders(symbol: str):
        filings = int(request.args.get("filings", 15))
        return jsonify(views.insiders_view(svc, symbol, filings=filings))

    @app.get("/api/fulltext")
    def fulltext():
        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({"error": "q parameter required"}), 400
        forms_arg = request.args.get("forms", "").strip()
        forms = [f for f in forms_arg.split(",") if f] if forms_arg else None
        limit = int(request.args.get("limit", 20))
        return jsonify(views.fulltext_search_view(svc, query, forms=forms, limit=limit))

    @app.get("/api/filings/<symbol>")
    def company_filings(symbol: str):
        form = request.args.get("form") or None
        limit = int(request.args.get("limit", 20))
        return jsonify(views.company_filings_view(svc, symbol, form=form, limit=limit))

    @app.get("/api/fund/<symbol>")
    def fund(symbol: str):
        top = int(request.args.get("top", 50))
        return jsonify(views.fund_view(svc, symbol, top=top))

    @app.get("/api/fx")
    def fx_matrix():
        currencies_arg = request.args.get("currencies", "").strip()
        currencies = (
            [c for c in currencies_arg.split(",") if c] if currencies_arg else None
        )
        return jsonify(views.fx_matrix_view(currencies=currencies))

    @app.get("/api/filing-alerts")
    def filing_alerts():
        return jsonify(views.latest_filings_view(svc))

    @app.get("/api/insider-buys")
    def insider_buys():
        symbols = [s for s in request.args.get("symbols", "").split(",") if s][:25]
        filings = int(request.args.get("filings", 8))
        return jsonify(
            views.insider_buys_view(svc, symbols, filings_per_symbol=filings)
        )

    @app.get("/api/security/<symbol>")
    def security(symbol: str):
        range_ = request.args.get("range", "6mo")
        return jsonify(views.security_view(svc, symbol, range_=range_))

    @app.get("/api/facts/<symbol>")
    def facts(symbol: str):
        years = int(request.args.get("years", 5))
        return jsonify(views.facts_view(svc, symbol, years=years))

    @app.get("/api/quotes")
    def quotes():
        symbols = [s for s in request.args.get("symbols", "").split(",") if s][:30]
        return jsonify(views.quotes_view(svc, symbols))

    @app.get("/api/markets")
    def markets():
        return jsonify(views.markets_view(svc))

    @app.get("/api/crypto")
    def crypto():
        limit = int(request.args.get("limit", 50))
        return jsonify(views.crypto_view(svc, limit=limit))

    @app.get("/api/regulatory")
    def regulatory():
        limit = int(request.args.get("limit", 20))
        return jsonify(views.regulatory_view(limit=limit))

    @app.get("/api/news")
    def news():
        limit = int(request.args.get("limit", 30))
        symbols_arg = request.args.get("symbols", "").strip()
        symbols = [s for s in symbols_arg.split(",") if s] if symbols_arg else None
        return jsonify(views.news_view(svc, symbols=symbols, limit=limit))

    @app.get("/api/events/<symbol>")
    def events(symbol: str):
        return jsonify(views.events_view(svc, symbol))

    @app.get("/api/fed-events")
    def fed_events():
        limit = int(request.args.get("limit", 20))
        return jsonify(views.fed_events_view(limit=limit))

    @app.get("/api/macro")
    def macro():
        return jsonify(views.macro_view())

    @app.get("/api/screener")
    def screener():
        universe_arg = request.args.get("universe", "").strip()
        universe = [s for s in universe_arg.split(",") if s] if universe_arg else None
        filters = {}
        for field in (
            "pe_ratio", "market_cap", "revenue_growth_pct", "net_margin_pct",
        ):
            lo = request.args.get(f"{field}_min")
            hi = request.args.get(f"{field}_max")
            if lo is not None or hi is not None:
                filters[field] = (
                    float(lo) if lo is not None else None,
                    float(hi) if hi is not None else None,
                )
        return jsonify(views.screener_view(svc, universe=universe, filters=filters or None))

    @app.get("/api/options/<symbol>")
    def options(symbol: str):
        expiration = request.args.get("expiration")
        return jsonify(views.options_view(svc, symbol, expiration=expiration))

    @app.post("/api/risk")
    def risk():
        body = request.get_json(force=True, silent=True) or {}
        holdings = body.get("holdings", [])
        range_ = body.get("range", "1y")
        return jsonify(views.risk_view(svc, holdings, range_=range_))

    return app


def run_dashboard(
    user_agent: str,
    host: str = "127.0.0.1",
    port: int = 8813,
    cache_dir: Optional[Path] = None,
) -> None:  # pragma: no cover - thin wrapper around app.run
    app = create_app(user_agent, cache_dir=cache_dir)
    app.run(host=host, port=port, threaded=True)
