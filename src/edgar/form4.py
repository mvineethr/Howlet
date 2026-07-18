"""Form 4 insider transactions from SEC EDGAR.

Officers, directors, and 10%+ owners must report their trades in the
company's stock on Form 4 within two business days - the closest thing
to a real-time "who's buying" signal EDGAR has, and completely free.

Form 4s are filed under BOTH the insider's CIK and the issuer's CIK, so
listing form "4" in the *issuer's* submissions history yields all insider
activity for that company. Each filing is a small `ownershipDocument`
XML (no namespace in practice, but parsed namespace-tolerantly like the
13F information table).

Only non-derivative transactions (actual common-stock trades) are
parsed; derivative rows (options/RSU grants themselves) are skipped -
the tradeable signal is open-market purchases (code P) and sales (S) of
the underlying stock. `price_per_share` is None when the filing gives a
footnote instead of a number (typical for RSU settlements).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lxml import etree

from .client import EdgarClient
from .models import FilingSummary

# SEC transaction codes (Form 4 instruction 8). P and S are the
# open-market signal; the rest are mostly compensation plumbing.
TRANSACTION_CODE_LABELS = {
    "P": "Open-market purchase",
    "S": "Open-market sale",
    "A": "Grant/award",
    "M": "Option/RSU conversion",
    "F": "Tax withholding",
    "G": "Gift",
    "D": "Disposition to issuer",
    "C": "Conversion of derivative",
    "X": "Option exercise",
    "J": "Other acquisition/disposition",
    "I": "Discretionary transaction",
    "W": "Acquired/disposed by will",
}


@dataclass
class InsiderTransaction:
    """One non-derivative transaction row from one Form 4."""

    insider_name: str
    insider_cik: str
    relationship: str  # e.g. "SVP, GC and Secretary", "Director, 10% owner"
    transaction_date: Optional[str]  # ISO date string
    transaction_code: str  # P, S, A, M, F, G, ...
    acquired_disposed: str  # "A" or "D"
    shares: float
    price_per_share: Optional[float]  # None when the filing footnotes it
    value_usd: Optional[float]  # shares * price, when price is known
    shares_owned_after: Optional[float]
    security_title: str
    direct_or_indirect: str  # "D" (direct) or "I" (indirect)
    filing_date: str
    accession_number: str


def list_form4_filings(
    client: EdgarClient, cik, limit: int = 15
) -> list[FilingSummary]:
    """Most recent Form 4 filings under a CIK (issuer or insider)."""
    return client.list_filings(cik, "4", limit=limit)


def get_form4_transactions(
    client: EdgarClient, filing: FilingSummary
) -> list[InsiderTransaction]:
    """Fetch + parse one Form 4 filing's non-derivative transactions.

    The submissions API reports `primaryDocument` as an XSL-rendered
    view path like "xslF345X06/form4.xml"; the raw XML lives at the
    bare filename in the filing folder, so the prefix is stripped.
    """
    xml_name = filing.primary_doc.split("/")[-1]
    resp = client._get(f"{filing.filing_index_url}{xml_name}")
    return parse_form4(resp.content, filing)


def parse_form4(
    xml_bytes: bytes, filing: FilingSummary
) -> list[InsiderTransaction]:
    """Parse an ownershipDocument XML into InsiderTransaction rows."""
    root = etree.fromstring(xml_bytes)

    def local_find(el, tag: str):
        for child in el.iter():
            if isinstance(child.tag, str) and etree.QName(child).localname == tag:
                return child
        return None

    def value_text(el, tag: str) -> Optional[str]:
        """Text of <tag><value>...</value></tag>; None if footnote-only."""
        node = local_find(el, tag)
        if node is None:
            return None
        value = local_find(node, "value")
        return value.text if value is not None else None

    # Owner(s): joint filings list several reportingOwner blocks.
    names, ciks, roles = [], [], []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if etree.QName(el).localname != "reportingOwner":
            continue
        owner_name = local_find(el, "rptOwnerName")
        owner_cik = local_find(el, "rptOwnerCik")
        names.append(owner_name.text.strip() if owner_name is not None and owner_name.text else "")
        ciks.append(owner_cik.text.strip() if owner_cik is not None and owner_cik.text else "")

        def flag(tag: str) -> bool:
            node = local_find(el, tag)
            return node is not None and (node.text or "").strip().lower() in ("1", "true")

        parts = []
        title = local_find(el, "officerTitle")
        if flag("isOfficer") and title is not None and title.text:
            parts.append(title.text.strip())
        elif flag("isOfficer"):
            parts.append("Officer")
        if flag("isDirector"):
            parts.append("Director")
        if flag("isTenPercentOwner"):
            parts.append("10% owner")
        if not parts and flag("isOther"):
            parts.append("Other")
        roles.append(", ".join(parts))

    insider_name = "; ".join(n for n in names if n)
    insider_cik = "; ".join(c for c in ciks if c)
    relationship = "; ".join(r for r in roles if r)

    transactions: list[InsiderTransaction] = []
    for entry in root.iter():
        if not isinstance(entry.tag, str):
            continue
        if etree.QName(entry).localname != "nonDerivativeTransaction":
            continue

        def num(tag: str) -> Optional[float]:
            text = value_text(entry, tag)
            try:
                return float(text) if text is not None else None
            except ValueError:
                return None

        shares = num("transactionShares") or 0.0
        price = num("transactionPricePerShare")
        code_node = local_find(entry, "transactionCode")
        transactions.append(
            InsiderTransaction(
                insider_name=insider_name,
                insider_cik=insider_cik,
                relationship=relationship,
                transaction_date=value_text(entry, "transactionDate"),
                transaction_code=(
                    code_node.text.strip() if code_node is not None and code_node.text else ""
                ),
                acquired_disposed=value_text(entry, "transactionAcquiredDisposedCode") or "",
                shares=shares,
                price_per_share=price,
                value_usd=shares * price if price else None,
                shares_owned_after=num("sharesOwnedFollowingTransaction"),
                security_title=value_text(entry, "securityTitle") or "",
                direct_or_indirect=value_text(entry, "directOrIndirectOwnership") or "",
                filing_date=filing.filing_date.isoformat(),
                accession_number=filing.accession_number,
            )
        )
    return transactions
