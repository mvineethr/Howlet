"""Thin client for the free SEC EDGAR APIs (data.sec.gov + www.sec.gov).

No API key needed. SEC's only requirement is a descriptive User-Agent header
on every request (your name + a contact email) - requests without one are
frequently rate-limited or rejected with a 403.

Reference: https://www.sec.gov/os/webmaster-faq#developers
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import requests
from lxml import etree

from .models import FilingSummary, Holding

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSIONS_PAGE_URL = "https://data.sec.gov/submissions/{name}"
COMPANY_SEARCH_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

# SEC asks for a soft cap of ~10 requests/second per source IP. We stay
# comfortably under that with simple fixed-interval throttling.
_MIN_INTERVAL_SECONDS = 0.12

# Retry budget for transient failures (429 rate-limit, 5xx). Backs off
# exponentially, honoring a Retry-After header if SEC sends one.
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE_SECONDS = 1.0


class EdgarClient:
    """A minimal, dependency-light client for SEC EDGAR's 13F data."""

    def __init__(self, user_agent: str):
        """
        Args:
            user_agent: REQUIRED by SEC. Format: "Your Name your@email.com".
                Generic strings like "python-requests" will get blocked.
        """
        if "@" not in user_agent:
            raise ValueError(
                "user_agent must include a contact email, e.g. "
                "'Jane Doe jane@example.com' - SEC requires this for all "
                "automated EDGAR requests."
            )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request_at = 0.0

    # ------------------------------------------------------------------ #
    # internal helpers
    # ------------------------------------------------------------------ #

    def _get(self, url: str, **kwargs) -> requests.Response:
        """GET with the self-throttle plus retry/backoff on 429 and 5xx.

        Transport-level ConnectionErrors are retried too: SEC resets
        stale keep-alive connections on long-lived sessions (WinError
        10054, seen live from the dashboard's shared client), and a
        retry on a fresh connection almost always succeeds.
        Non-retryable errors (4xx other than 429) raise immediately via
        raise_for_status(). After exhausting retries, callers see the
        usual requests exception.
        """
        resp: Optional[requests.Response] = None
        for attempt in range(_MAX_RETRIES + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < _MIN_INTERVAL_SECONDS:
                time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
            try:
                resp = self.session.get(url, timeout=20, **kwargs)
            except requests.ConnectionError:
                self._last_request_at = time.monotonic()
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_BASE_SECONDS * (2**attempt))
                    continue
                raise
            self._last_request_at = time.monotonic()

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < _MAX_RETRIES:
                    retry_after = resp.headers.get("Retry-After")
                    wait = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else _RETRY_BACKOFF_BASE_SECONDS * (2**attempt)
                    )
                    time.sleep(wait)
                    continue

            resp.raise_for_status()
            return resp

        resp.raise_for_status()  # last attempt's response; always raises here
        return resp  # pragma: no cover - unreachable, satisfies type checkers

    @staticmethod
    def pad_cik(cik) -> str:
        """The submissions API wants a 10-digit, zero-padded CIK string."""
        return str(cik).zfill(10)

    # ------------------------------------------------------------------ #
    # company / manager lookup
    # ------------------------------------------------------------------ #

    def search_company_cik(self, name: str) -> list[dict]:
        """Find candidate CIKs for a manager/fund by name.

        EDGAR's stored names are often messy ("BERKSHIRE HATHAWAY INC" vs
        "Berkshire Hathaway Inc."), so this returns a list of candidates
        for you to disambiguate rather than guessing a single answer.

        Example:
            >>> client.search_company_cik("berkshire")
            [{"name": "BERKSHIRE HATHAWAY INC", "cik": "0001067983"}, ...]

        Note: this parses the *HTML* results table, not `output=atom`.
        SEC's atom feed for this endpoint has a longstanding server-side bug
        where <entry title="..."> renders as a stringified Perl array ref
        (e.g. "ARRAY(0x55d6f0feff88)") instead of the company name - found
        by running this against the live API. The HTML table doesn't have
        that bug and is what this now uses.
        """
        params = {
            "action": "getcompany",
            "company": name,
            "type": "13F-HR",
            "dateb": "",
            "owner": "include",
            "count": "20",
        }
        resp = self._get(COMPANY_SEARCH_URL, params=params)
        tree = etree.HTML(resp.content)

        # An exact-match query skips the results table entirely: EDGAR
        # renders that company's filing list instead, with the identity
        # in a header span ("Third Point LLC CIK#: 0001040273 ...") and
        # a CIK form input (verified live - the filing table otherwise
        # parses as garbage "Documents" rows).
        company_spans = tree.xpath('//span[@class="companyName"]')
        if company_spans:
            span_text = company_spans[0].xpath("string(.)")
            cik_values = tree.xpath('//input[@name="CIK"]/@value')
            return [
                {
                    "name": span_text.split("CIK#:")[0].strip(),
                    "cik": cik_values[0] if cik_values else None,
                }
            ]

        results = []
        for row in tree.xpath('//table[@class="tableFile2"]/tr[position()>1]'):
            cells = row.xpath("./td")
            if len(cells) < 2:
                continue
            cik = cells[0].xpath("string(.//a)").strip() or None
            # Company name is the text node right before any nested <br/>
            # (some rows append a SIC code link after a line break).
            company_name = (cells[1].text or "").strip()
            if not company_name:
                company_name = cells[1].xpath("string(.)").strip()
            results.append({"name": company_name, "cik": cik})
        return results

    # ------------------------------------------------------------------ #
    # filings
    # ------------------------------------------------------------------ #

    def get_submissions(self, cik) -> dict:
        """Raw submissions history JSON for a CIK (all form types)."""
        url = SUBMISSIONS_URL.format(cik=self.pad_cik(cik))
        return self._get(url).json()

    def list_filings(
        self, cik, form_type: Optional[str], limit: int = 8
    ) -> list[FilingSummary]:
        """Most recent filings of one form type (or ANY form when
        form_type is None) for a CIK, newest first.

        `submissions/CIK....json` only covers the filer's *recent* filings
        (capped around 1000 across all form types). Filers with longer
        histories have older filings in a paginated `filings.files[]`
        array - each entry names a separate JSON page
        (`data.sec.gov/submissions/{name}`) with the same flat
        form/accessionNumber/filingDate/... arrays as `recent`, just not
        nested under a "filings" key. This walks `recent` first, then those
        pages in order, stopping once `limit` matching filings are found.
        """
        data = self.get_submissions(cik)
        filings: list[FilingSummary] = []
        padded_cik = self.pad_cik(cik)

        def consume(block: dict) -> bool:
            """Append matching filings from one block; True once limit hit."""
            for i, form in enumerate(block["form"]):
                if form_type is not None and form != form_type:
                    continue
                period_raw = block["reportDate"][i]
                filings.append(
                    FilingSummary(
                        cik=padded_cik,
                        accession_number=block["accessionNumber"][i],
                        filing_date=datetime.strptime(
                            block["filingDate"][i], "%Y-%m-%d"
                        ).date(),
                        period_of_report=(
                            datetime.strptime(period_raw, "%Y-%m-%d").date()
                            if period_raw
                            else None
                        ),
                        primary_doc=block["primaryDocument"][i],
                        form=form,
                    )
                )
                if len(filings) >= limit:
                    return True
            return False

        if consume(data["filings"]["recent"]):
            return filings

        for page in data["filings"].get("files", []):
            page_url = SUBMISSIONS_PAGE_URL.format(name=page["name"])
            page_data = self._get(page_url).json()
            if consume(page_data):
                break

        return filings

    def list_13f_filings(self, cik, limit: int = 8) -> list[FilingSummary]:
        """Most recent 13F-HR filings for a CIK, newest first."""
        return self.list_filings(cik, "13F-HR", limit=limit)

    # ------------------------------------------------------------------ #
    # holdings (the actual "information table")
    # ------------------------------------------------------------------ #

    def get_information_table(self, filing: FilingSummary) -> list[Holding]:
        """Fetch + parse the stock-by-stock holdings for a single filing.

        Every 13F-HR bundles a primary doc (human-readable cover page) plus
        a separate XML "information table" with the actual positions. This
        finds that second file in the filing's index and parses it.
        """
        index_url = f"{filing.filing_index_url}index.json"
        index = self._get(index_url).json()

        xml_name = None
        for item in index["directory"]["item"]:
            fname = item["name"]
            if fname.lower().endswith(".xml") and "info" in fname.lower():
                xml_name = fname
                break
        if xml_name is None:
            # Fallback for filers that name the file unusually: take the
            # first XML that isn't the primary document.
            for item in index["directory"]["item"]:
                fname = item["name"]
                if fname.lower().endswith(".xml") and fname != filing.primary_doc:
                    xml_name = fname
                    break
        if xml_name is None:
            raise ValueError(
                f"Could not locate an information-table XML for accession "
                f"{filing.accession_number}. The filer may have used an "
                f"unusual file layout - check {index_url} manually."
            )

        xml_url = f"{filing.filing_index_url}{xml_name}"
        resp = self._get(xml_url)
        return self._parse_information_table(resp.content)

    @staticmethod
    def _parse_information_table(xml_bytes: bytes) -> list[Holding]:
        """Parse a 13F XML information table into Holding objects.

        Namespaces vary slightly across filers/years, so this matches on
        local tag name rather than requiring an exact namespace URI.
        """
        root = etree.fromstring(xml_bytes)
        holdings: list[Holding] = []

        for entry in root.iter():
            if etree.QName(entry).localname != "infoTable":
                continue

            def text(tag: str) -> Optional[str]:
                for child in entry.iter():
                    if etree.QName(child).localname == tag:
                        return child.text
                return None

            holdings.append(
                Holding(
                    name_of_issuer=text("nameOfIssuer") or "",
                    cusip=text("cusip") or "",
                    value_usd=int(text("value") or 0),
                    shares=int(text("sshPrnamt") or 0),
                    share_type=text("sshPrnamtType") or "",
                    investment_discretion=text("investmentDiscretion") or "",
                )
            )
        return holdings
