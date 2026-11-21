"""Quarter-over-quarter holdings diffing.

Pure data transformation, no network calls - compares the parsed
information-table Holdings from two filings and reports what changed.
"""

from __future__ import annotations

from typing import Optional

from .models import Holding, HoldingChange

NEW = "NEW"
SOLD = "SOLD"
INCREASED = "INCREASED"
DECREASED = "DECREASED"
UNCHANGED = "UNCHANGED"

# Sort priority for CLI/report display: biggest news first.
STATUS_ORDER = {NEW: 0, SOLD: 1, INCREASED: 2, DECREASED: 3, UNCHANGED: 4}


def _aggregate_by_cusip(holdings: list[Holding]) -> dict[str, dict]:
    """Sum value/shares per CUSIP within a single filing.

    A filer can report the same security in several infoTable entries
    (different sub-accounts, voting authority splits, etc.), so this
    collapses each filing down to one row per CUSIP before comparing
    across filings.

    Option rows (putCall set) are EXCLUDED: a put is not a long
    position, and folding it into the stock's totals inflates the
    position, its weight, and consensus counts. Use
    `aggregate_options` for the option rows.
    """
    agg: dict[str, dict] = {}
    for h in holdings:
        if h.is_option:
            continue
        entry = agg.setdefault(
            h.cusip,
            {"name_of_issuer": h.name_of_issuer, "value_usd": 0, "shares": 0},
        )
        entry["value_usd"] += h.value_usd
        entry["shares"] += h.shares
    return agg


def aggregate_options(holdings: list[Holding]) -> dict[str, dict]:
    """Option rows per CUSIP: {cusip: {name_of_issuer, put_call,
    value_usd, shares, rows}} - the complement of `_aggregate_by_cusip`.

    Multiple option rows for one CUSIP (e.g. puts at different strikes)
    are summed for value/shares but keep the first put/call direction
    seen; mixed PUT+CALL rows for one CUSIP are rare and flagged by
    `mixed` so callers can split them out.
    """
    agg: dict[str, dict] = {}
    for h in holdings:
        if not h.is_option:
            continue
        entry = agg.setdefault(
            h.cusip,
            {
                "name_of_issuer": h.name_of_issuer,
                "put_call": h.put_call,
                "value_usd": 0,
                "shares": 0,
                "rows": 0,
                "mixed": False,
            },
        )
        if entry["put_call"] != h.put_call:
            entry["mixed"] = True
        entry["value_usd"] += h.value_usd
        entry["shares"] += h.shares
        entry["rows"] += 1
    return agg


def diff_holdings(
    prior: list[Holding],
    current: list[Holding],
    split_factors: dict[str, float] | None = None,
) -> list[HoldingChange]:
    """Compare two filings' holdings by CUSIP.

    Args:
        prior: holdings from the earlier filing.
        current: holdings from the later filing.
        split_factors: optional {cusip: factor} to multiply the prior
            share count by before comparing - e.g. a 4:1 split between
            the quarters means 100 prior shares are 400 split-adjusted
            shares, not a 300-share "buy". Changes whose prior shares
            were adjusted carry `split_adjusted=True`.

    Returns:
        One HoldingChange per CUSIP that appeared in either filing,
        unsorted. NEW = in current only, SOLD = in prior only,
        INCREASED/DECREASED = share count changed, UNCHANGED = identical
        share count (value can still shift with price).
    """
    prior_agg = _aggregate_by_cusip(prior)
    current_agg = _aggregate_by_cusip(current)
    split_factors = split_factors or {}

    changes = []
    for cusip in set(prior_agg) | set(current_agg):
        p = prior_agg.get(cusip)
        c = current_agg.get(cusip)

        prior_shares = p["shares"] if p else 0
        split_adjusted = False
        factor = split_factors.get(cusip)
        if p is not None and factor:
            prior_shares = int(round(prior_shares * factor))
            split_adjusted = True

        if p is None:
            status = NEW
        elif c is None:
            status = SOLD
        elif c["shares"] > prior_shares:
            status = INCREASED
        elif c["shares"] < prior_shares:
            status = DECREASED
        else:
            status = UNCHANGED

        changes.append(
            HoldingChange(
                cusip=cusip,
                name_of_issuer=(c or p)["name_of_issuer"],
                status=status,
                prior_value_usd=p["value_usd"] if p else 0,
                current_value_usd=c["value_usd"] if c else 0,
                prior_shares=prior_shares,
                current_shares=c["shares"] if c else 0,
                split_adjusted=split_adjusted,
            )
        )
    return changes
