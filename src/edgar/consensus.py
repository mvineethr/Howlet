"""Multi-manager "smart money consensus".

Answers: which stocks do several famous managers hold at the same time,
and how much conviction (portfolio weight) does each have? This is a view
Bloomberg terminals don't hand you directly - it falls straight out of
combining N managers' latest 13F information tables by CUSIP.

Pure aggregation logic lives in `build_consensus_rows` (no network) so it
can be unit-tested offline; `fetch_latest_portfolios` does the EDGAR I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .cache import FilingCache, cached_information_table
from .client import EdgarClient
from .diff import _aggregate_by_cusip


@dataclass
class ManagerPortfolio:
    """One manager's latest filing, aggregated to one row per CUSIP."""

    label: str
    cik: str
    period_of_report: Optional[str]
    positions: dict[str, dict]  # cusip -> {name_of_issuer, value_usd, shares}

    @property
    def total_value_usd(self) -> int:
        return sum(p["value_usd"] for p in self.positions.values())


@dataclass
class ConsensusRow:
    """One security held by one or more of the tracked managers."""

    cusip: str
    name_of_issuer: str
    manager_count: int
    total_value_usd: int
    # label -> weight of this position in that manager's portfolio (%)
    weights_pct: dict[str, float] = field(default_factory=dict)

    @property
    def managers(self) -> list[str]:
        return sorted(self.weights_pct)

    @property
    def combined_weight_pct(self) -> float:
        """Sum of per-manager weights - a crude conviction score."""
        return sum(self.weights_pct.values())


def fetch_latest_portfolios(
    client: EdgarClient,
    managers: dict[str, str],
    cache: Optional[FilingCache] = None,
) -> list[ManagerPortfolio]:
    """Latest 13F portfolio per manager. Managers with no filings are skipped.

    `managers` maps display label -> CIK. Duplicate CIKs (e.g. the
    "buffett" and "berkshire" preset aliases) are collapsed to the first
    label seen.
    """
    seen_ciks: set[str] = set()
    portfolios: list[ManagerPortfolio] = []
    for label, cik in managers.items():
        padded = EdgarClient.pad_cik(cik)
        if padded in seen_ciks:
            continue
        seen_ciks.add(padded)

        filings = client.list_13f_filings(cik, limit=1)
        if not filings:
            continue
        holdings = cached_information_table(client, cache, filings[0])
        portfolios.append(
            ManagerPortfolio(
                label=label,
                cik=padded,
                period_of_report=(
                    filings[0].period_of_report.isoformat()
                    if filings[0].period_of_report
                    else None
                ),
                positions=_aggregate_by_cusip(holdings),
            )
        )
    return portfolios


def build_consensus_rows(
    portfolios: list[ManagerPortfolio], min_managers: int = 1
) -> list[ConsensusRow]:
    """Combine portfolios into per-CUSIP consensus rows.

    Sorted by (number of managers holding, combined portfolio weight),
    descending - i.e. the most agreed-upon, highest-conviction names first.
    """
    rows: dict[str, ConsensusRow] = {}
    for portfolio in portfolios:
        total = portfolio.total_value_usd
        for cusip, position in portfolio.positions.items():
            row = rows.setdefault(
                cusip,
                ConsensusRow(
                    cusip=cusip,
                    name_of_issuer=position["name_of_issuer"],
                    manager_count=0,
                    total_value_usd=0,
                ),
            )
            row.manager_count += 1
            row.total_value_usd += position["value_usd"]
            weight = (
                position["value_usd"] / total * 100.0 if total else 0.0
            )
            row.weights_pct[portfolio.label] = weight

    result = [r for r in rows.values() if r.manager_count >= min_managers]
    result.sort(
        key=lambda r: (r.manager_count, r.combined_weight_pct), reverse=True
    )
    return result


def build_consensus(
    client: EdgarClient,
    managers: dict[str, str],
    cache: Optional[FilingCache] = None,
    min_managers: int = 2,
) -> list[ConsensusRow]:
    """End-to-end: fetch every manager's latest 13F and cross-reference."""
    portfolios = fetch_latest_portfolios(client, managers, cache=cache)
    return build_consensus_rows(portfolios, min_managers=min_managers)
