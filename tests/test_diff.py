"""Tests for quarter-over-quarter holdings diffing (pure logic, no HTTP)."""

from __future__ import annotations

from edgar.diff import diff_holdings
from edgar.models import Holding


def _holding(name, cusip, value, shares, share_type="SH", discretion="SOLE"):
    return Holding(
        name_of_issuer=name,
        cusip=cusip,
        value_usd=value,
        shares=shares,
        share_type=share_type,
        investment_discretion=discretion,
    )


def test_diff_holdings_classifies_new_sold_increased_decreased_unchanged():
    prior = [
        _holding("APPLE INC", "037833100", 50_000, 1_000),
        _holding("COCA COLA CO", "191216100", 25_000, 500),
        _holding("KRAFT HEINZ CO", "500754106", 10_000, 300),
        _holding("CHEVRON CORP", "166764100", 8_000, 100),
    ]
    current = [
        _holding("APPLE INC", "037833100", 60_000, 1_200),  # INCREASED
        _holding("COCA COLA CO", "191216100", 20_000, 400),  # DECREASED
        _holding("KRAFT HEINZ CO", "500754106", 10_500, 300),  # UNCHANGED (shares same)
        _holding("MOODYS CORP", "615369105", 5_000, 50),  # NEW
        # CHEVRON dropped entirely -> SOLD
    ]

    changes = {c.cusip: c for c in diff_holdings(prior, current)}

    assert changes["037833100"].status == "INCREASED"
    assert changes["037833100"].shares_change == 200
    assert changes["037833100"].value_change_usd == 10_000

    assert changes["191216100"].status == "DECREASED"
    assert changes["191216100"].shares_change == -100

    assert changes["500754106"].status == "UNCHANGED"
    assert changes["500754106"].shares_change == 0
    assert changes["500754106"].value_change_usd == 500  # value can drift with price

    assert changes["615369105"].status == "NEW"
    assert changes["615369105"].prior_shares == 0
    assert changes["615369105"].current_shares == 50

    assert changes["166764100"].status == "SOLD"
    assert changes["166764100"].current_shares == 0
    assert changes["166764100"].prior_shares == 100


def test_diff_holdings_aggregates_multiple_entries_per_cusip_within_a_filing():
    # Real filings (e.g. Berkshire's) report the same CUSIP across several
    # infoTable entries - e.g. split by voting authority. These must be
    # summed per filing before comparing across filings.
    prior = [
        _holding("APPLE INC", "037833100", 30_000, 600, discretion="SOLE"),
        _holding("APPLE INC", "037833100", 20_000, 400, discretion="SHARED"),
    ]
    current = [
        _holding("APPLE INC", "037833100", 35_000, 700, discretion="SOLE"),
        _holding("APPLE INC", "037833100", 25_000, 500, discretion="SHARED"),
    ]

    changes = diff_holdings(prior, current)

    assert len(changes) == 1
    change = changes[0]
    assert change.prior_shares == 1_000
    assert change.current_shares == 1_200
    assert change.prior_value_usd == 50_000
    assert change.current_value_usd == 60_000
    assert change.status == "INCREASED"
