"""Tests for Form 4 insider-transaction parsing (offline, mocked HTTP)."""

from __future__ import annotations

from datetime import date

import responses

from edgar.client import EdgarClient
from edgar.form4 import get_form4_transactions, list_form4_filings, parse_form4
from edgar.models import FilingSummary

# Trimmed from a real AAPL Form 4 captured live on 2026-07-17
# (accession 0001140361-26-025622); don't simplify - the footnote-only
# price on the M transaction and the derivativeTable are the point.
SAMPLE_FORM4_XML = b"""<?xml version="1.0"?>
<ownershipDocument>
    <schemaVersion>X0609</schemaVersion>
    <documentType>4</documentType>
    <periodOfReport>2026-06-15</periodOfReport>
    <issuer>
        <issuerCik>0000320193</issuerCik>
        <issuerName>Apple Inc.</issuerName>
        <issuerTradingSymbol>AAPL</issuerTradingSymbol>
    </issuer>
    <reportingOwner>
        <reportingOwnerId>
            <rptOwnerCik>0001780525</rptOwnerCik>
            <rptOwnerName>Newstead Jennifer</rptOwnerName>
        </reportingOwnerId>
        <reportingOwnerRelationship>
            <isOfficer>true</isOfficer>
            <officerTitle>SVP, GC and Secretary</officerTitle>
        </reportingOwnerRelationship>
    </reportingOwner>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <securityTitle><value>Common Stock</value></securityTitle>
            <transactionDate><value>2026-06-15</value></transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>M</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares><value>30104</value></transactionShares>
                <transactionPricePerShare><footnoteId id="F1"/></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts>
                <sharesOwnedFollowingTransaction><value>57784</value></sharesOwnedFollowingTransaction>
            </postTransactionAmounts>
            <ownershipNature>
                <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
            </ownershipNature>
        </nonDerivativeTransaction>
        <nonDerivativeTransaction>
            <securityTitle><value>Common Stock</value><footnoteId id="F2"/></securityTitle>
            <transactionDate><value>2026-06-15</value></transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>F</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares><value>16238</value></transactionShares>
                <transactionPricePerShare><value>296.42</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts>
                <sharesOwnedFollowingTransaction><value>41546</value></sharesOwnedFollowingTransaction>
            </postTransactionAmounts>
            <ownershipNature>
                <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
            </ownershipNature>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
    <derivativeTable>
        <derivativeTransaction>
            <securityTitle><value>Restricted Stock Unit</value></securityTitle>
            <transactionDate><value>2026-06-15</value></transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>M</transactionCode>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares><value>30104</value></transactionShares>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
        </derivativeTransaction>
    </derivativeTable>
</ownershipDocument>
"""

FILING = FilingSummary(
    cik="0000320193",
    accession_number="0001140361-26-025622",
    filing_date=date(2026, 6, 17),
    period_of_report=date(2026, 6, 15),
    # The submissions API reports the XSL-rendered view path; the raw
    # XML is the bare filename (verified live).
    primary_doc="xslF345X06/form4.xml",
)


def test_parse_form4_nonderivative_only():
    txns = parse_form4(SAMPLE_FORM4_XML, FILING)
    # The derivativeTable RSU row must NOT appear.
    assert len(txns) == 2

    vest, withhold = txns
    assert vest.insider_name == "Newstead Jennifer"
    assert vest.relationship == "SVP, GC and Secretary"
    assert vest.transaction_code == "M"
    assert vest.acquired_disposed == "A"
    assert vest.shares == 30104
    assert vest.price_per_share is None  # footnote-only price
    assert vest.value_usd is None
    assert vest.shares_owned_after == 57784

    assert withhold.transaction_code == "F"
    assert withhold.price_per_share == 296.42
    assert withhold.value_usd == 16238 * 296.42
    assert withhold.direct_or_indirect == "D"
    assert withhold.filing_date == "2026-06-17"
    assert withhold.accession_number == "0001140361-26-025622"


@responses.activate
def test_get_form4_transactions_strips_xsl_prefix():
    # The raw XML must be fetched from the bare filename, not the
    # xslF345X06/ rendered-view path.
    responses.add(
        responses.GET,
        "https://www.sec.gov/Archives/edgar/data/320193/000114036126025622/form4.xml",
        body=SAMPLE_FORM4_XML,
    )
    client = EdgarClient("Test Suite test@example.com")
    txns = get_form4_transactions(client, FILING)
    assert len(txns) == 2


@responses.activate
def test_list_form4_filings_filters_form_type():
    responses.add(
        responses.GET,
        "https://data.sec.gov/submissions/CIK0000320193.json",
        json={
            "filings": {
                "recent": {
                    "form": ["4", "10-K", "4", "13F-HR"],
                    "accessionNumber": ["a-1", "a-2", "a-3", "a-4"],
                    "filingDate": [
                        "2026-06-17", "2026-05-01", "2026-04-10", "2026-02-14",
                    ],
                    "reportDate": [
                        "2026-06-15", "2025-12-31", "2026-04-08", "2025-12-31",
                    ],
                    "primaryDocument": [
                        "xslF345X06/form4.xml", "aapl-10k.htm",
                        "xslF345X06/form4.xml", "info.xml",
                    ],
                },
            }
        },
    )
    client = EdgarClient("Test Suite test@example.com")
    filings = list_form4_filings(client, 320193, limit=5)
    assert [f.accession_number for f in filings] == ["a-1", "a-3"]
    assert filings[0].period_of_report == date(2026, 6, 15)
