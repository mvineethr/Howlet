"""Howlet - free Python client for SEC EDGAR 13F institutional holdings data.

No API key required. SEC just asks that requests carry a descriptive
User-Agent (name + contact email). See README.md for setup.
"""

from .cache import FilingCache, cached_information_table
from .client import EdgarClient
from .consensus import build_consensus, build_consensus_rows
from .diff import diff_holdings
from .events import CorporateEventsClient
from .fundamentals import FundamentalsClient
from .market import Quote, YahooMarketClient
from .models import FilingSummary, Holding, HoldingChange
from .news import NewsClient, NewsItem
from .options import OptionsClient
from .paper import PaperError, PaperStore
from .tickers import CusipTickerResolver
from .views import Services

__version__ = "0.8.1"
__all__ = [
    "CorporateEventsClient",
    "CusipTickerResolver",
    "EdgarClient",
    "FilingCache",
    "FilingSummary",
    "FundamentalsClient",
    "Holding",
    "HoldingChange",
    "NewsClient",
    "NewsItem",
    "OptionsClient",
    "PaperError",
    "PaperStore",
    "Quote",
    "Services",
    "YahooMarketClient",
    "build_consensus",
    "build_consensus_rows",
    "cached_information_table",
    "diff_holdings",
]
