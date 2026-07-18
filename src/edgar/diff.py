"""Quarter-over-quarter holdings diffing.

Pure data transformation, no network calls - compares the parsed
information-table Holdings from two filings and reports what changed.
"""

from __future__ import annotations

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
    """
    agg: dict[str, dict] = {}
    for h in holdings:
        entry = agg.setdefault(
            h.cusip,
            {"name_of_issuer": h.name_of_issuer, "value_usd": 0, "shares": 0},
        )
        entry["value_usd"] += h.value_usd
        entry["shares"] += h.shares
    return agg


def diff_holdings(prior: list[Holding], current: list[Holding]) -> list[HoldingChange]:
    """Compare two filings' holdings by CUSIP.

    Args:
        prior: holdings from the earlier filing.
        current: holdings from the later filing.

    Returns:
        One HoldingChange per CUSIP that appeared in either filing,
        unsorted. NEW = in current only, SOLD = in prior only,
        INCREASED/DECREASED = share count changed, UNCHANGED = identical
        share count (value can still shift with price).
    """
    prior_agg = _aggregate_by_cusip(prior)
    current_agg = _aggregate_by_cusip(current)

    changes = []
    for cusip in set(prior_agg) | set(current_agg):
        p = prior_agg.get(cusip)
        c = current_agg.get(cusip)

        if p is None:
            status = NEW
        elif c is None:
            status = SOLD
        elif c["shares"] > p["shares"]:
            status = INCREASED
        elif c["shares"] < p["shares"]:
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
                prior_shares=p["shares"] if p else 0,
                current_shares=c["shares"] if c else 0,
            )
        )
    return changes
