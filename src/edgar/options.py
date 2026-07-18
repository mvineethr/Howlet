"""Options chains via Yahoo's (crumb-authed, unofficial) options endpoint.

Same reliability tier as `events.py`: this can stop working if Yahoo
changes its auth wall again, so every function degrades to `None`/empty
rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from .yahoo_auth import YahooAuthSession

OPTIONS_URL = "https://query1.finance.yahoo.com/v7/finance/options/{symbol}"


@dataclass
class OptionContract:
    contract_symbol: str
    strike: float
    last_price: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    volume: Optional[int]
    open_interest: Optional[int]
    implied_volatility: Optional[float]
    in_the_money: bool


@dataclass
class OptionChain:
    symbol: str
    underlying_price: Optional[float]
    expiration_dates: list[str]  # ISO dates, all available expirations
    selected_expiration: Optional[str]
    calls: list[OptionContract]
    puts: list[OptionContract]


class OptionsClient:
    def __init__(self, auth: Optional[YahooAuthSession] = None):
        self.auth = auth or YahooAuthSession()

    def get_option_chain(
        self, symbol: str, expiration: Optional[str] = None
    ) -> Optional[OptionChain]:
        """Calls/puts for one expiration (nearest, if unspecified).

        `expiration` is an ISO date string (e.g. "2026-08-21"); pass one
        of the dates from a prior call's `expiration_dates` to page
        through the chain.
        """
        params = {}
        if expiration:
            try:
                params["date"] = int(
                    datetime.combine(
                        date.fromisoformat(expiration), datetime.min.time(),
                        tzinfo=timezone.utc,
                    ).timestamp()
                )
            except ValueError:
                return None

        resp = self.auth.get(OPTIONS_URL.format(symbol=symbol), params=params)
        if resp is None:
            return None
        try:
            result = resp.json()["optionChain"]["result"][0]
        except (KeyError, IndexError, ValueError, TypeError):
            return None
        return _parse_option_chain(symbol, result)


def _parse_contract(raw: dict) -> OptionContract:
    return OptionContract(
        contract_symbol=raw.get("contractSymbol", ""),
        strike=float(raw.get("strike", 0.0)),
        last_price=raw.get("lastPrice"),
        bid=raw.get("bid"),
        ask=raw.get("ask"),
        volume=raw.get("volume"),
        open_interest=raw.get("openInterest"),
        implied_volatility=raw.get("impliedVolatility"),
        in_the_money=bool(raw.get("inTheMoney", False)),
    )


def _parse_option_chain(symbol: str, result: dict) -> OptionChain:
    exp_dates = [
        datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        for ts in result.get("expirationDates", [])
    ]
    options = (result.get("options") or [{}])[0]
    selected = None
    if options.get("expirationDate"):
        selected = datetime.fromtimestamp(
            options["expirationDate"], tz=timezone.utc
        ).date().isoformat()

    quote = result.get("quote") or {}
    return OptionChain(
        symbol=symbol.upper(),
        underlying_price=quote.get("regularMarketPrice"),
        expiration_dates=exp_dates,
        selected_expiration=selected,
        calls=[_parse_contract(c) for c in options.get("calls", [])],
        puts=[_parse_contract(p) for p in options.get("puts", [])],
    )
