"""Data models for 13F filings and holdings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class FilingSummary:
    """Metadata about a single 13F-HR filing pulled from the submissions API."""

    cik: str
    accession_number: str
    filing_date: date
    period_of_report: date | None
    primary_doc: str
    form: str | None = None  # e.g. "13F-HR", "4", "8-K"

    @property
    def accession_no_dashes(self) -> str:
        return self.accession_number.replace("-", "")

    @property
    def filing_index_url(self) -> str:
        """Base URL for this filing's document folder on sec.gov."""
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(self.cik)}/{self.accession_no_dashes}/"
        )


@dataclass
class Holding:
    """A single position from a 13F 'information table'.

    `value_usd` is the <value> element normalized to whole US dollars.
    Since the SEC's Jan 2023 technical amendment, filers report it in
    whole dollars (verified live: Berkshire's reported total only
    matches their ~$263B portfolio when read as dollars). Filings from
    before 2023 reported it rounded to the nearest $1,000 instead, so
    pre-2023 values are scaled x1000 at parse time (see
    `EdgarClient._parse_information_table`).

    `put_call` is the <putCall> element when the row is an option
    ("PUT" or "CALL"); None for a plain long-equity row. Option rows
    must never be folded into long-equity totals - see `diff.py`.
    """

    name_of_issuer: str
    cusip: str
    value_usd: int
    shares: int
    share_type: str  # "SH" (shares) or "PRN" (principal amount, e.g. bonds)
    investment_discretion: str
    ticker: str | None = None
    put_call: str | None = None  # "PUT" / "CALL" / None (long equity)
    # Voting authority (<votingAuthority><Sole>/<Shared>/<None>), in
    # shares. A filing can list the same CUSIP several times with
    # different voting splits - these fields are part of a row's
    # identity, so merging amendments must not collapse them.
    voting_sole: int = 0
    voting_shared: int = 0
    voting_none: int = 0

    @property
    def is_option(self) -> bool:
        return self.put_call is not None


@dataclass
class HoldingChange:
    """One CUSIP's position, compared between two filings.

    A single filing can list the same CUSIP in multiple `infoTable` entries
    (e.g. split across sub-accounts or voting authority) - see Berkshire's
    own 13F, which lists AAPL five times in one filing. Values here are
    pre-aggregated per CUSIP per filing before comparison, so each CUSIP
    appears at most once.
    """

    cusip: str
    name_of_issuer: str
    status: str  # "NEW", "SOLD", "INCREASED", "DECREASED", "UNCHANGED"
    prior_value_usd: int
    current_value_usd: int
    prior_shares: int
    current_shares: int
    # True when the prior share count was multiplied by a split factor
    # before comparing (see diff_holdings(..., split_factors=...)).
    split_adjusted: bool = False

    @property
    def value_change_usd(self) -> int:
        return self.current_value_usd - self.prior_value_usd

    @property
    def shares_change(self) -> int:
        return self.current_shares - self.prior_shares
