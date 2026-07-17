"""MCP (Model Context Protocol) server exposing the terminal to any AI.

Run with `edgar13f mcp` (stdio transport). Any MCP-capable client -
Claude Code, Claude Desktop, or anything else that speaks MCP - can then
call the same data views the web dashboard renders: 13F portfolios, Q/Q
changes, smart-money consensus, holders, quotes, charts, fundamentals,
and news. All free/keyless, same rate-limit etiquette as the CLI.

Claude Code setup:
    claude mcp add edgar13f -e EDGAR_USER_AGENT="Jane Doe jane@example.com" \
        -- edgar13f mcp

Claude Desktop config (claude_desktop_config.json):
    {"mcpServers": {"edgar13f": {
        "command": "edgar13f", "args": ["mcp"],
        "env": {"EDGAR_USER_AGENT": "Jane Doe jane@example.com"}}}}

Requires the optional dependency: pip install "edgar13f[mcp]"
"""

from __future__ import annotations

from typing import Optional

from . import views
from .views import Services


def build_server(user_agent: str):
    """Create the FastMCP server with every tool registered."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised via CLI message
        raise ImportError(
            "The MCP server needs the 'mcp' package. Install it with:\n"
            '    pip install "edgar13f[mcp]"'
        ) from exc

    svc = Services(user_agent)
    server = FastMCP(
        "edgar13f",
        instructions=(
            "Free SEC EDGAR 13F + market data terminal. 13F filings report "
            "institutional managers' long US equity positions quarterly with "
            "up to a ~45 day lag - never treat holdings as real-time. Values "
            "are whole US dollars. Quotes come from a free Yahoo endpoint "
            "and may be delayed. Nothing here is investment advice."
        ),
    )

    @server.tool()
    def search_manager(name: str) -> list[dict]:
        """Search SEC EDGAR for institutional managers/funds by name.
        Returns candidate CIKs to disambiguate (EDGAR names are messy)."""
        with svc.edgar_lock:
            return svc.edgar.search_company_cik(name)

    @server.tool()
    def list_managers() -> list[dict]:
        """The built-in famous-investor presets (label + CIK) usable as
        `identifier` in the other 13F tools."""
        return views.managers_view()

    @server.tool()
    def get_portfolio(identifier: str, top: int = 25) -> dict:
        """A manager's latest 13F portfolio, aggregated by CUSIP, with
        tickers, live prices, and portfolio weights. `identifier` is a
        CIK or preset label (e.g. 'buffett'). First call for a manager is
        slow (keyless ticker-mapping rate limits); cached afterwards."""
        return views.portfolio_view(svc, identifier, top=top)

    @server.tool()
    def get_portfolio_changes(identifier: str) -> dict:
        """What a manager bought/sold between their two most recent 13F
        filings: NEW / SOLD / INCREASED / DECREASED per security."""
        return views.diff_view(svc, identifier)

    @server.tool()
    def get_consensus(min_managers: int = 2, limit: int = 20) -> dict:
        """Which stocks multiple tracked famous managers hold right now,
        with per-manager conviction weights."""
        return views.consensus_view(svc, min_managers=min_managers, limit=limit)

    @server.tool()
    def get_holders(symbol: str) -> dict:
        """Which tracked famous managers hold a given ticker (Bloomberg
        HDS-style), with shares, value, and portfolio weight."""
        return views.holders_view(svc, symbol)

    @server.tool()
    def get_position_history(identifier: str, query: str, quarters: int = 8) -> dict:
        """One manager's stake in one security across N quarters of 13F
        filings (chronological): shares, reported value, and portfolio
        weight per quarter - e.g. how Buffett's AAPL position evolved.
        `query` is a ticker, CUSIP, or issuer-name substring."""
        return views.position_history_view(svc, identifier, query, quarters=quarters)

    @server.tool()
    def get_insider_transactions(symbol: str, filings: int = 15) -> dict:
        """Form 4 insider trades for a company: who bought/sold, when, at
        what price, and their role. Codes P (open-market purchase) and S
        (open-market sale) are the signal; A/M/F/G are mostly grants,
        vesting, and tax withholding. `filings` = recent Form 4s to scan."""
        return views.insiders_view(svc, symbol, filings=filings)

    @server.tool()
    def get_quote(symbols: list[str]) -> list[dict]:
        """Quotes for stock/index/futures/crypto/FX symbols (Yahoo
        conventions: AAPL, BRK-B, ^GSPC, CL=F, BTC-USD, EURUSD=X)."""
        return views.quotes_view(svc, symbols)

    @server.tool()
    def get_price_history(symbol: str, range: str = "6mo") -> dict:
        """Full quote detail plus close-price history for charting, and
        technical studies (SMA20/50, EMA12/26, RSI14, MACD, Bollinger
        Bands, opening-range breakout) computed over that history.
        Ranges: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max."""
        return views.security_view(svc, symbol, range_=range)

    @server.tool()
    def get_fundamentals(symbol: str, years: int = 5) -> dict:
        """Annual headline financials (revenue, net income, diluted EPS,
        assets, liabilities, equity, operating cash flow) from SEC XBRL
        company facts - audited 10-K data, whole USD."""
        return views.facts_view(svc, symbol, years=years)

    @server.tool()
    def get_news(symbols: Optional[list[str]] = None, limit: int = 20) -> list[dict]:
        """Headlines from free feeds (Yahoo Finance, CNBC, MarketWatch,
        SEC press releases). Pass symbols for company-specific news."""
        return views.news_view(svc, symbols=symbols, limit=limit)

    @server.tool()
    def get_world_markets() -> list[dict]:
        """World markets snapshot: global equity indices, FX, commodities,
        rates, crypto - grouped by region/asset class."""
        return views.markets_view(svc)

    @server.tool()
    def get_crypto_markets(limit: int = 50) -> dict:
        """Top cryptocurrencies by market cap: price, 24h change, market
        cap, volume (CoinGecko keyless tier, Coinpaprika fallback -
        `source` says which one answered; rows empty if both are down)."""
        return views.crypto_view(svc, limit=limit)

    @server.tool()
    def get_sec_rulemaking(limit: int = 20) -> list[dict]:
        """Newest SEC rules, proposed rules, and notices from the
        Federal Register (the US government's official daily journal) -
        exchange rule changes, ETF approvals, market-structure rules."""
        return views.regulatory_view(limit=limit)

    @server.tool()
    def get_corporate_events(symbol: str) -> dict:
        """Next earnings date, analyst buy/hold/sell recommendation mix
        (Yahoo, unofficial - degrades to null if unavailable), and recent
        SEC DEF 14A shareholder-meeting proxy filings (reliable, EDGAR)."""
        return views.events_view(svc, symbol)

    @server.tool()
    def get_fed_calendar(limit: int = 20) -> list[dict]:
        """Recent FOMC statements and Fed officials' speeches, straight
        from the Federal Reserve's own official RSS feeds."""
        return views.fed_events_view(limit=limit)

    @server.tool()
    def get_macro_snapshot() -> dict:
        """Treasury par yield curve (always available) plus BLS headline
        series (CPI, unemployment rate, nonfarm payrolls - free, keyless).
        Set the FRED_API_KEY env var for deeper macro coverage; without
        it, `fred_available` is false and only Treasury/BLS are used."""
        return views.macro_view()

    @server.tool()
    def screen_securities(
        universe: Optional[list[str]] = None,
        pe_max: Optional[float] = None,
        pe_min: Optional[float] = None,
        market_cap_min: Optional[float] = None,
        revenue_growth_min_pct: Optional[float] = None,
        net_margin_min_pct: Optional[float] = None,
    ) -> dict:
        """Screen a ticker universe (default: a curated large-cap list
        across sectors) by P/E, market cap, revenue growth, and net
        margin - all computed from SEC XBRL fundamentals + free quotes."""
        filters: dict[str, tuple[Optional[float], Optional[float]]] = {}
        if pe_min is not None or pe_max is not None:
            filters["pe_ratio"] = (pe_min, pe_max)
        if market_cap_min is not None:
            filters["market_cap"] = (market_cap_min, None)
        if revenue_growth_min_pct is not None:
            filters["revenue_growth_pct"] = (revenue_growth_min_pct, None)
        if net_margin_min_pct is not None:
            filters["net_margin_pct"] = (net_margin_min_pct, None)
        return views.screener_view(svc, universe=universe, filters=filters or None)

    @server.tool()
    def get_options_chain(symbol: str, expiration: Optional[str] = None) -> dict:
        """Calls/puts for one expiration (nearest, if unspecified) -
        strikes, bid/ask, volume, open interest, implied vol. Unofficial
        Yahoo endpoint; raises if unavailable for this symbol right now."""
        return views.options_view(svc, symbol, expiration=expiration)

    @server.tool()
    def analyze_portfolio_risk(holdings: list[dict], range: str = "1y") -> dict:
        """Volatility, max drawdown, and Sharpe ratio for a personal
        portfolio (NOT a 13F manager - see get_portfolio for that).
        `holdings` is [{"symbol": "AAPL", "shares": 10}, ...]."""
        return views.risk_view(svc, holdings, range_=range)

    return server


def run_mcp_server(user_agent: str) -> None:  # pragma: no cover - stdio loop
    build_server(user_agent).run()
