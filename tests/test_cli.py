"""Tests for the CLI holdings/diff commands (network mocked)."""

from __future__ import annotations

from datetime import date

import pytest
from click.testing import CliRunner

from howlet import cli
from howlet.models import FilingSummary, Holding


def _filing(accession: str, period: date, filed: date) -> FilingSummary:
    return FilingSummary(
        cik="0001067983",
        accession_number=accession,
        filing_date=filed,
        period_of_report=period,
        primary_doc="primary.htm",
        form="13F-HR",
    )


def _holding(name: str, cusip: str, value: int, shares: int) -> Holding:
    return Holding(
        name_of_issuer=name,
        cusip=cusip,
        value_usd=value,
        shares=shares,
        share_type="SH",
        investment_discretion="SOLE",
    )


@pytest.fixture
def runner(monkeypatch) -> CliRunner:
    monkeypatch.setenv("EDGAR_USER_AGENT", "Test Suite test@example.com")
    return CliRunner()


class _FakeEdgarClient:
    """EdgarClient stub: list_13f_filings returns canned filings."""

    def __init__(self, filings: list[FilingSummary]):
        self._filings = filings

    def list_13f_filings(self, cik, limit: int = 8):
        return self._filings[:limit]


def test_holdings_limit_lists_all_filings(runner, monkeypatch):
    filings = [
        _filing("0001-24-000001", date(2024, 3, 31), date(2024, 5, 15)),
        _filing("0001-23-000003", date(2023, 12, 31), date(2024, 2, 14)),
    ]
    monkeypatch.setattr(cli, "EdgarClient", lambda ua: _FakeEdgarClient(filings))
    monkeypatch.setattr(
        cli,
        "cached_information_table",
        lambda client, cache, filing: [_holding("APPLE INC", "037833100", 50_000, 1_000)],
    )

    result = runner.invoke(cli.main, ["holdings", "buffett", "--limit", "2"])

    assert result.exit_code == 0, result.output
    # Both filings are listed (the --limit option now does something),
    # then the latest filing's holdings are shown.
    assert "2024-03-31" in result.output
    assert "2023-12-31" in result.output
    assert "APPLE INC" in result.output


def test_holdings_limit_one_shows_no_filings_table(runner, monkeypatch):
    filings = [_filing("0001-24-000001", date(2024, 3, 31), date(2024, 5, 15))]
    monkeypatch.setattr(cli, "EdgarClient", lambda ua: _FakeEdgarClient(filings))
    monkeypatch.setattr(
        cli,
        "cached_information_table",
        lambda client, cache, filing: [_holding("APPLE INC", "037833100", 50_000, 1_000)],
    )

    result = runner.invoke(cli.main, ["holdings", "buffett"])

    assert result.exit_code == 0, result.output
    assert "Recent 13F-HR filings" not in result.output
    assert "APPLE INC" in result.output


class _FakeResolver:
    def resolve(self, cusips):
        return dict.fromkeys(cusips, "NVDA")


class _FakeMarket:
    def get_splits(self, symbol):
        assert symbol == "NVDA"
        return [{"date": "2024-06-10", "numerator": 10, "denominator": 1}]


def test_diff_adjust_splits_flag_marks_split_adjusted_changes(runner, monkeypatch):
    current_f = _filing("0001-24-000001", date(2024, 6, 30), date(2024, 8, 14))
    prior_f = _filing("0001-24-000002", date(2024, 3, 31), date(2024, 5, 15))
    by_accession = {
        current_f.accession_number: [_holding("NVIDIA CORP", "67066G104", 1_320_000, 1_000)],
        prior_f.accession_number: [_holding("NVIDIA CORP", "67066G104", 120_000, 100)],
    }
    monkeypatch.setattr(
        cli, "EdgarClient", lambda ua: _FakeEdgarClient([current_f, prior_f])
    )
    monkeypatch.setattr(
        cli,
        "cached_information_table",
        lambda client, cache, filing: by_accession[filing.accession_number],
    )
    monkeypatch.setattr(cli, "CusipTickerResolver", lambda: _FakeResolver())
    monkeypatch.setattr(cli, "YahooMarketClient", lambda: _FakeMarket())

    # UNCHANGED rows are hidden by default, so show them explicitly.
    result = runner.invoke(
        cli.main, ["diff", "burry", "--adjust-splits", "--show-unchanged"]
    )

    assert result.exit_code == 0, result.output
    # 100 prior shares x10 split = 1,000: UNCHANGED, flagged as adjusted.
    assert "UNCHANGED" in result.output
    assert "Split-adjusted NVDA: x10" in result.output
    assert "* prior shares split-adjusted between the quarters" in result.output

    # Without the flag the same filings read as a 900-share buy.
    result = runner.invoke(cli.main, ["diff", "burry"])
    assert result.exit_code == 0, result.output
    assert "INCREASED" in result.output
    assert "Split-adjusted" not in result.output
