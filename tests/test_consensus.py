"""Tests for the multi-manager consensus logic (pure, no network)."""

from __future__ import annotations

from howlet.consensus import ManagerPortfolio, build_consensus_rows


def _portfolio(label: str, positions: dict[str, tuple[str, int]]) -> ManagerPortfolio:
    return ManagerPortfolio(
        label=label,
        cik="0000000001",
        period_of_report="2026-03-31",
        positions={
            cusip: {"name_of_issuer": name, "value_usd": value, "shares": 1}
            for cusip, (name, value) in positions.items()
        },
    )


def test_consensus_counts_managers_and_sorts_by_agreement():
    a = _portfolio("alpha", {
        "AAA": ("APPLE INC", 800),
        "BBB": ("BANK CO", 200),
    })
    b = _portfolio("beta", {
        "AAA": ("APPLE INC", 300),
        "CCC": ("CHIP CORP", 700),
    })
    c = _portfolio("gamma", {
        "AAA": ("APPLE INC", 100),
    })

    rows = build_consensus_rows([a, b, c], min_managers=2)
    assert len(rows) == 1  # only AAA is held by >= 2 managers
    row = rows[0]
    assert row.cusip == "AAA"
    assert row.manager_count == 3
    assert row.managers == ["alpha", "beta", "gamma"]
    assert row.total_value_usd == 1200

    # Weight = position / that manager's total portfolio.
    assert round(row.weights_pct["alpha"], 1) == 80.0
    assert round(row.weights_pct["beta"], 1) == 30.0
    assert round(row.weights_pct["gamma"], 1) == 100.0


def test_consensus_min_managers_one_returns_everything_ranked():
    a = _portfolio("alpha", {"AAA": ("APPLE INC", 500), "BBB": ("BANK CO", 500)})
    b = _portfolio("beta", {"BBB": ("BANK CO", 1000)})

    rows = build_consensus_rows([a, b], min_managers=1)
    assert [r.cusip for r in rows][:1] == ["BBB"]  # held by 2 > held by 1
    assert {r.cusip for r in rows} == {"AAA", "BBB"}


def test_consensus_handles_empty_portfolio_without_dividing_by_zero():
    empty = _portfolio("empty", {})
    a = _portfolio("alpha", {"AAA": ("APPLE INC", 500)})
    rows = build_consensus_rows([empty, a], min_managers=1)
    assert len(rows) == 1


# --- Phase 2: one broken manager must not kill consensus (B5) ---

def test_fetch_latest_portfolios_skips_failing_manager():
    from datetime import date

    from howlet.consensus import fetch_latest_portfolios
    from howlet.models import FilingSummary, Holding

    def filing(cik):
        return FilingSummary(
            cik=cik,
            accession_number="0000000000-26-000001",
            filing_date=date(2026, 5, 15),
            period_of_report=date(2026, 3, 31),
            primary_doc="primary.xml",
        )

    class StubClient:
        def list_13f_filings(self, cik, limit=1):
            if cik == "0001234567":
                raise ConnectionError("SEC hiccup")
            return [filing(cik)]

        def get_information_table(self, filing):
            return [
                Holding(
                    name_of_issuer="APPLE INC",
                    cusip="037833100",
                    value_usd=1000,
                    shares=5,
                    share_type="SH",
                    investment_discretion="SOLE",
                )
            ]

    portfolios = fetch_latest_portfolios(
        StubClient(),
        {"good": "0001067983", "bad": "0001234567", "alsogood": "0001067984"},
        cache=None,
    )
    assert [p.label for p in portfolios] == ["good", "alsogood"]
    assert portfolios[0].total_value_usd == 1000


def test_fetch_latest_portfolios_skips_manager_whose_holdings_fetch_fails():
    from datetime import date

    from howlet.consensus import fetch_latest_portfolios
    from howlet.models import FilingSummary

    class StubClient:
        def list_13f_filings(self, cik, limit=1):
            return [
                FilingSummary(
                    cik=cik,
                    accession_number="0000000000-26-000001",
                    filing_date=date(2026, 5, 15),
                    period_of_report=date(2026, 3, 31),
                    primary_doc="primary.xml",
                )
            ]

        def get_information_table(self, filing):
            raise ValueError("malformed information table")

    portfolios = fetch_latest_portfolios(
        StubClient(), {"broken": "0001067983"}, cache=None
    )
    assert portfolios == []

def test_consensus_excludes_option_rows():
    from howlet.diff import _aggregate_by_cusip
    from howlet.models import Holding

    def holding(name, cusip, value, shares, put_call=None):
        return Holding(
            name_of_issuer=name,
            cusip=cusip,
            value_usd=value,
            shares=shares,
            share_type="SH",
            investment_discretion="SOLE",
            put_call=put_call,
        )

    # Burry-style: a small long plus a big put on the same CUSIP.
    raw = [
        holding("NVIDIA CORP", "67066G104", 100_000, 500),
        holding("NVIDIA CORP", "67066G104", 9_000_000, 50_000, "PUT"),
    ]
    portfolio = ManagerPortfolio(
        label="burry",
        cik="0000000001",
        period_of_report="2026-03-31",
        positions=_aggregate_by_cusip(raw),
    )
    assert portfolio.total_value_usd == 100_000  # put excluded

    rows = build_consensus_rows([portfolio], min_managers=1)
    assert len(rows) == 1
    assert rows[0].total_value_usd == 100_000
    assert rows[0].weights_pct["burry"] == 100.0
