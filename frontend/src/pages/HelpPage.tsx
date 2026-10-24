import { Body1, Button, Link, Subtitle1, Subtitle2, Text, Title3 } from "@fluentui/react-components";
import { BLOCKS } from "../blocks/registry";
import { safeHref } from "../lib/fmt";

type Rows = [string, string][];

const GLOSSARY_FUNCS: Rows = [
    ["DES", "Description - the stock page itself. Its Overview tab has the quote (with day and 52-week ranges), events (earnings, analyst view, shareholder meetings) and studies (indicator readings and opening-range breakout). The chart and financials are separate tabs, and the 🦉 chips above the tabs show which tracked managers hold it."],
  ["GP", "Graph Price - jumps to the Chart tab of the same stock page."],
  ["FA", "Financial Analysis - yearly revenue, profit, earnings per share, assets and cash flow, straight from the audited SEC annual report."],
  ["HDS", "Holders - which of the tracked investors own a stock, how many shares, and how big a bet it is for them."],
  ["PORT", "Portfolio - the full list of stocks a given investor reported holding, biggest positions first."],
  ["EQS", "Equity Screener - filter a list of large companies by valuation, size, growth and profitability."],
  ["ECO", "Economics - Treasury yield curve, inflation and jobs numbers, and the Fed's latest announcements (on Markets)."],
  ["PAPER", "Paper trading - a practice account with fake money; orders fill against real (delayed) prices."],
  ["PF", "Portfolio - the stocks you own, with volatility, worst drop and risk-adjusted return."],
  ["MKTS", "Markets - a world snapshot: indices, currencies, commodities, rates and crypto."],
  ["OPT", "Options (also OMON) - calls and puts for a stock. Experimental; may be unavailable."],
  ["ALERT", "A price alert: ALERT AAPL > 350 rings the bell in the top bar when AAPL crosses 350."],
];
const GLOSSARY_TERMS: Rows = [
  ["13F", "A form the biggest investors must file with the SEC every 3 months, listing the US stocks they own. It is the source of the \"what is Buffett buying\" data, and it is always a bit delayed (see FAQ)."],
  ["CIK", "Central Index Key - the ID number the SEC gives every filer. Berkshire's is 1067983. You can type a CIK anywhere a manager name is accepted."],
  ["CUSIP", "The 9-character ID code for a specific security. 13F filings identify stocks by CUSIP; Howlet translates these into familiar tickers."],
  ["Q/Q", "Quarter over quarter - what an investor bought, sold, added to or trimmed since their previous filing."],
  ["Ticker", "A stock's short trading symbol (AAPL = Apple). Tickers shown as links open that stock's page."],
  ["Weight", "How big a position is as a percentage of that whole portfolio."],
  ["P/E", "Price-to-earnings - share price divided by yearly earnings per share; a rough \"how expensive is this stock\" gauge."],
  ["Mkt cap", "Market capitalization - a company's total value: share price times number of shares."],
  ["Net margin", "Profit as a percentage of revenue - how much of each sales dollar becomes profit."],
  ["EPS", "Earnings per share - company profit divided by its number of shares."],
  ["Sharpe", "Sharpe ratio - return earned per unit of risk taken. Higher is better; above ~1 is generally considered good."],
  ["Max drawdown", "The worst peak-to-bottom drop over the period - your biggest paper loss if you had bought the high."],
  ["Limit order", "Buy or sell only at your price or better - it may never fill."],
  ["Stop order", "Waits until the price crosses your level, then trades at the next available price - often used to cap a loss."],
  ["Paper trading", "Practising with pretend money against real prices, so mistakes cost nothing."],
  ["Volatility", "How much a price bounces around. Higher volatility means bigger swings and more risk."],
  ["Yield curve", "US government interest rates across different loan lengths (1 month to 30 years)."],
  ["FOMC", "Federal Open Market Committee - the Federal Reserve group that sets US interest rates."],
  ["DEF 14A", "A company's annual proxy statement - the filing tied to its yearly shareholder meeting."],
  ["IV / OI", "Implied volatility and open interest - options terms (expected swing, and how many contracts exist)."],
];
const GLOSSARY_STUDIES: Rows = [
  ["SMA / EMA", "Simple / Exponential Moving Average - a smoothed average price line that shows the trend through the noise."],
  ["RSI", "Relative Strength Index - a 0-100 momentum gauge; high can mean overbought, low can mean oversold."],
  ["MACD", "Moving Average Convergence Divergence - a popular momentum and trend-change indicator built from two moving averages."],
  ["Bollinger", "Bollinger Bands - a band around the average price that widens when things get volatile."],
  ["ORB", "Opening Range Breakout - the high/low of the first part of the session; trading above or below it is watched as a breakout signal."],
];
const COMMANDS: Rows = [
  ["Ctrl+K", "focus the command box (or just click it); Enter runs, Esc clears"],
  ["AAPL", "a bare ticker opens its stock page; a bare manager name or CIK opens that 13F portfolio"],
  ["AAPL FA / GP / HDS / OPT", "open that stock's Financials, Chart, Holders or Options tab (DES = Overview, CN = News)"],
  ["buffett  /  buffett PORT  /  1067983", "a manager's 13F portfolio (preset name or raw CIK) on Smart Money"],
  ["HOME  NEWS  MKTS  EQS  PF  MY  SETTINGS", "jump to a rail page (ECO and WEI also open Markets; WATCH opens Portfolio)"],
  ["ALERT AAPL > 350", "set a price alert; use < for a drop. Alerts are checked while Howlet is open"],
  ["HELP  /  ?  /  ABOUT  /  FAQ", "this page"],
  ["Ctrl+1 ... Ctrl+7", "jump to the rail pages in the order shown on the rail"],
  ["Alt+Left", "back to where you came from"],
];
const PAGES: Rows = [
  ["Home", "your customizable dashboard: a grid of blocks, with tabs and saved layouts."],
  ["Markets", "stocks, crypto, FX, and Economy: Treasury curve, jobs & inflation, Fed calendar, SEC rulemaking."],
  ["Smart Money", "what the tracked investors hold and changed, consensus across them, position history and insider buys."],
  ["Screener", "filter a curated large-cap universe by valuation, size, growth and profitability."],
  ["News", "a market wire, Fed and policy, and an earnings feed."],
  ["Portfolio", "your watchlists and personal portfolio, news and earnings dates scoped to them, and portfolio risk."],
  ["Settings", "appearance, rail order and visibility, defaults, layouts, backup and this help page."],
];
const STOCK_TABS: Rows = [
  ["Overview", "quote with day and 52-week ranges, events (earnings, analysts, shareholder meetings), and studies (indicators and opening-range breakout)."],
  ["Chart", "price chart with indicators."],
  ["Financials", "annual financials from SEC filings, with CSV export."],
  ["Holders", "tracked managers holding the stock (13F), plus insider transactions and SEC filings."],
  ["News", "headlines for the ticker."],
  ["Options", "calls and puts (experimental; can be switched off in Settings)."],
];
const FAQ: Rows = [
  ["Is this real-time?", "Quotes and charts are live-ish (free feed, may be a little delayed). The 13F holdings are not: investors only report quarterly, up to ~45 days after quarter-end, so \"what Buffett owns\" is always a few weeks to a few months old."],
  ["Why does a stock in a portfolio show no price?", "A few holdings (foreign-listed names, bonds) can't be matched to a US ticker from the free lookup, so there's no quote to attach. The position itself is still shown."],
  ["Why is the first load of a manager or holders slow?", "The first time, it translates every holding's ID into a ticker through a rate-limited free service. That result is saved on your machine, so it's fast every time after."],
  ["Where are my watchlists and layout saved?", "In your browser only (local storage). Nothing is sent to a server or account, and clearing your browser data resets it. Settings has Export and Import backup."],
  ["Do I need any API keys or a login?", "No. Everything works with zero keys and no account. (FRED is one optional extra macro source that takes a free key - Howlet is fully functional without it.)"],
  ["Is this investment advice?", "No. It's an information tool built on public data. Do your own research; nothing here is a recommendation."],
];
const TIPS = [
  "Tickers shown as links anywhere in Howlet open that stock's page.",
  "The first load of a manager, Holders or Screener view is slow (keyless OpenFIGI/SEC rate limits or a same-day fundamentals fetch); it is disk-cached after that.",
  "13F data is quarterly with up to a ~45 day lag - it is never real-time positioning.",
  "Options and earnings dates use an unofficial Yahoo auth workaround and can go dark if Yahoo changes it - everything else is unaffected if that happens.",
  "The Screener is not the full S&P 500 - there's no free, reliable, no-key source for live index membership. It's a hand-picked large-cap universe.",
];
const SECTIONS = ["About", "Glossary", "Commands", "Pages", "Blocks", "Charting", "FAQ", "Tips", "Plug this into your AI", "Sources"];
const id = (s: string) => `help-${s.toLowerCase().replace(/\W+/g, "-")}`;

function Table({ rows, wide }: { rows: Rows; wide?: boolean }) {
  return (
    <table style={{ borderCollapse: "collapse", width: "100%" }}>
      <tbody>{rows.map(([k, v]) => (
        <tr key={k} style={{ borderBottom: "1px solid var(--border)" }}>
          <td style={{ padding: "4px 12px 4px 0", verticalAlign: "top", whiteSpace: wide ? "normal" : "nowrap", width: wide ? "34%" : undefined }}><code>{k}</code></td>
          <td style={{ padding: "4px 0" }}><Body1>{v}</Body1></td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function Section({ name, children }: { name: string; children: React.ReactNode }) {
  return <section id={id(name)} style={{ display: "grid", gap: 8 }}><Subtitle1 as="h2">{name}</Subtitle1>{children}</section>;
}

export default function HelpPage() {
  const jump = (s: string) => document.getElementById(id(s))?.scrollIntoView({ behavior: "smooth", block: "start" });
  return (
    <div style={{ padding: 16, display: "grid", gap: 20, maxWidth: 860 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <img src="/static/logo.png" alt="Howlet" width={40} height={40} /><Title3 as="h1">Help &amp; glossary</Title3>
      </div>
      <nav aria-label="Help sections" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {SECTIONS.map((s) => <Button key={s} size="small" appearance="outline" onClick={() => jump(s)}>{s}</Button>)}
      </nav>

      <Section name="About">
        <Body1>Howlet is a free, open-source market terminal. It answers "what are famous investors buying?" using public SEC filings, and adds quotes, charts, fundamentals, news and economic data on top - all from free sources, with no API keys and no subscription. Press Ctrl+K and type a ticker, a manager name or a short command (below) to get around. Nothing here is investment advice.</Body1>
      </Section>

      <Section name="Glossary">
        <Body1>Howlet uses a lot of abbreviations (that is the Bloomberg heritage). Here is what each one means in plain English.</Body1>
        <Subtitle2 as="h3">Command codes</Subtitle2><Table rows={GLOSSARY_FUNCS} />
        <Subtitle2 as="h3">Data and finance terms</Subtitle2><Table rows={GLOSSARY_TERMS} />
        <Subtitle2 as="h3">Chart studies</Subtitle2><Table rows={GLOSSARY_STUDIES} />
      </Section>

      <Section name="Commands">
        <Body1>Press Ctrl+K, type, press Enter. Commands are SECURITY then FUNCTION, like AAPL FA.</Body1>
        <Table rows={COMMANDS} wide />
      </Section>

      <Section name="Pages">
        <Body1>The rail on the left has seven pages (Ctrl+1 to Ctrl+7 in rail order). You can reorder and hide them in Settings.</Body1>
        <Table rows={PAGES} />
        <Subtitle2 as="h3">Stock page tabs</Subtitle2><Table rows={STOCK_TABS} />
      </Section>

      <Section name="Blocks">
        <Body1>Home is built from blocks. Use Add block to pick one, "+" for extra tabs, and save named layouts to switch between setups. Everything is saved in your browser. The block types:</Body1>
        <ul style={{ margin: 0, columns: 2 }}>{Object.values(BLOCKS).map((b) => <li key={b.label}><Text>{b.label}</Text></li>)}</ul>
        <Body1>Settings also controls theme, accent colour, density, text size, refresh speed, alert sound and the start page.</Body1>
      </Section>

      <Section name="Charting">
        <Body1>The Chart tab uses KLineChart (Apache-2.0 open source, no paywall), fed by Howlet's own data. Stack indicators from the indicator picker - moving averages, Bollinger, Volume, MACD, RSI and more - and use the draw tools for trend lines, price levels, channels and Fibonacci. Indicators stay applied as you switch symbols, and the default range is set in Settings.</Body1>
      </Section>

      <Section name="FAQ"><Table rows={FAQ} wide /></Section>

      <Section name="Tips"><ul style={{ margin: 0, paddingLeft: 20 }}>{TIPS.map((t) => <li key={t}><Body1>{t}</Body1></li>)}</ul></Section>

      <Section name="Plug this into your AI">
        <Body1>Everything in Howlet is also exposed as MCP tools: run <code>howlet mcp</code>. See the{" "}
          <Link href={safeHref("https://github.com/mvineethr/Howlet")} target="_blank" rel="noopener noreferrer">README</Link> for Claude Code / Claude Desktop setup.</Body1>
      </Section>

      <Section name="Sources">
        <Body1>SEC EDGAR (13F holdings, XBRL fundamentals, Form 4, filings), OpenFIGI (CUSIP to ticker), Yahoo Finance (quotes and charts), Yahoo/CNBC/MarketWatch/SEC RSS (news), CoinGecko/Coinpaprika (crypto market caps), Federal Register (SEC rulemaking), Treasury and BLS (macro), ECB via Frankfurter (FX). All free, no API keys.</Body1>
      </Section>
    </div>
  );
}
