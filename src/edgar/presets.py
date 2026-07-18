"""A handful of well-known 13F filer CIKs, so the CLI/demo doesn't require
looking one up first.

CIKs are stable, public identifiers - verified against SEC EDGAR. If you add
more, verify via `edgar search "<name>"` rather than guessing.

NOTE: 13F filings report the *manager's* aggregate long equity positions,
quarterly, with up to a ~45 day reporting lag. They exclude short positions,
most options, cash, and non-US/non-equity holdings. See README for caveats.
"""

FAMOUS_INVESTORS: dict[str, str] = {
    "buffett": "1067983",  # Berkshire Hathaway Inc.
    "berkshire": "1067983",
    "burry": "1649339",  # Scion Asset Management, LLC (Michael Burry)
    "ackman": "1336528",  # Pershing Square Capital Management, L.P.
    "icahn": "921669",  # Carl C. Icahn, Individual
    "tepper": "1656456",  # Appaloosa LP (David Tepper; the pre-2016
    "appaloosa": "1656456",  # filer was APPALOOSA MANAGEMENT LP, 1006438)
    "klarman": "1061768",  # BAUPOST GROUP LLC/MA (Seth Klarman)
    "baupost": "1061768",
    "loeb": "1040273",  # Third Point LLC (Daniel Loeb)
    "thirdpoint": "1040273",
    "dalio": "1350694",  # Bridgewater Associates, LP (Ray Dalio)
    "bridgewater": "1350694",
    "druckenmiller": "1536411",  # Duquesne Family Office LLC
    "duquesne": "1536411",
    "marks": "949509",  # OAKTREE CAPITAL MANAGEMENT LP (Howard Marks)
    "oaktree": "949509",
    "lilu": "1709323",  # Himalaya Capital Management LLC (Li Lu)
    "himalaya": "1709323",
    "einhorn": "1489933",  # DME Capital Management, LP - Greenlight's
    "greenlight": "1489933",  # successor filer (old CIK 1079114 stopped
    # filing 13F-HRs after 2023-12-31; verified live)
    "fundsmith": "1569205",  # Fundsmith LLP (Terry Smith)
    "tigerglobal": "1167483",  # TIGER GLOBAL MANAGEMENT LLC
}

# Every CIK above was verified live (2026-07-17): name via
# `edgar search`, plus a check that the entity's LATEST 13F-HR is
# current (2026-03-31 period) - EDGAR entity names are inconsistent,
# and famous managers migrate filers (Appaloosa, Greenlight->DME), so a
# name match alone can hand you a filer that stopped reporting years ago.
