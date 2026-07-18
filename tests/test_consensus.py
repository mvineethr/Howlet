"""Tests for the multi-manager consensus logic (pure, no network)."""

from __future__ import annotations

from edgar.consensus import ManagerPortfolio, build_consensus_rows


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
