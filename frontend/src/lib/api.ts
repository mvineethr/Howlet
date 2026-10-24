export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  let body: unknown = null;
  try { body = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) {
    const msg = body && typeof body === "object" && "error" in body ? String((body as { error: unknown }).error) : `HTTP ${res.status}`;
    throw new ApiError(msg, res.status);
  }
  return body as T;
}

export type Quote = {
  symbol: string; name: string | null; price: number; change: number | null;
  change_pct: number | null; previous_close: number | null; currency: string | null;
  day_low: number | null; day_high: number | null; week52_low: number | null;
  week52_high: number | null; volume: number | null; sparkline?: number[];
};
export type TapeRow = { symbol: string; label: string; price: number; change: number | null; change_pct: number | null };
export type NewsItem = { title: string; link: string; source: string; symbol: string | null; published: string | null };
export type DiffChange = { issuer: string; cusip: string; status: string; value_change_usd: number; shares_change: number; current_value_usd: number };
export type DiffResult = { prior_period: string | null; current_period: string | null; changes: DiffChange[] };
export type Holder = { manager: string; period_of_report: string | null; issuer: string; shares: number; value_usd: number; weight_pct: number };
export type HoldersResult = { symbol: string; tracked_managers: string[]; holders: Holder[] };
export type ManagerRef = { label: string; cik: string };
export type Security = Quote & { exchange?: string | null; instrument_type?: string | null };

export type FilingAlert = { label: string; cik: string; accession_number: string; filing_date: string; period_of_report: string | null };

export type MarketRow = { symbol: string; label: string; price: number; change_pct: number | null; sparkline: number[] };
export type MarketSection = { section: string; rows: MarketRow[] };
export type CryptoRow = { rank: number; symbol: string; name: string; price: number; change_pct_24h: number | null;
  market_cap: number | null; volume_24h: number | null; high_24h: number | null; low_24h: number | null };
export type CryptoResult = { source: string; rows: CryptoRow[] };
export type FxResult = { date?: string; currencies?: string[]; matrix?: Record<string, Record<string, number>> };
export type BlsPoint = { value: string; period: string; year: string };
export type MacroResult = {
  treasury_yield_curve: { date?: string; curve?: { maturity: string; yield_pct: number }[] } | null;
  bls_series: Record<string, BlsPoint[]> | null;
  fred_available: boolean;
  fred_series: Record<string, { description: string; latest: number | string | null; date: string | null }> | null;
};
export type RegDoc = { title: string; type: string | null; document_number: string; html_url: string; publication_date: string | null };
export type ScreenerRow = { symbol: string; price: number | null; change_pct: number | null; market_cap: number | null;
  pe_ratio: number | null; eps_diluted: number | null; revenue: number | null; revenue_growth_pct: number | null; net_margin_pct: number | null };
export type ScreenerResult = { universe_size: number; matched: number; rows: ScreenerRow[] };

export type Studies = Partial<Record<"sma20" | "sma50" | "ema12" | "ema26" | "rsi14" | "macd" | "macd_signal" |
  "macd_histogram" | "bollinger_upper" | "bollinger_mid" | "bollinger_lower", number | null>>;
export type Orb = { range_high: number; range_low: number; last_price: number; status: "ABOVE_RANGE" | "BELOW_RANGE" | "INSIDE_RANGE"; breakout_pct: number };
export type SecurityDetail = Security & {
  currency: string | null; range: string; range_change_pct: number | null;
  history_ts: number[]; history_open: number[]; history_high: number[]; history_low: number[];
  history_close: number[]; history_volume: number[]; studies: Studies; orb: Orb | null;
};
export type Events = {
  symbol: string; next_earnings_date: string | null; analyst_recommendation: string | null;
  analyst_counts: { strong_buy: number; buy: number; hold: number; sell: number; strong_sell: number } | null;
  shareholder_meetings: { form: string; filing_date: string; accession_number: string; primary_doc?: string }[];
};
export type FiscalYear = { fiscal_year: number; end_date: string; revenue: number | null; net_income: number | null;
  eps_diluted: number | null; total_assets: number | null; total_liabilities: number | null;
  stockholders_equity: number | null; operating_cash_flow: number | null };
export type Facts = { symbol: string; cik: string; company: string; fiscal_years: FiscalYear[] };
export type InsiderTxn = { insider: string; relationship: string | null; date: string | null; code: string; code_label: string;
  shares: number | null; price_per_share: number | null; value_usd: number | null; filing_date: string; accession_number: string };
export type Insiders = { symbol: string; company: string; filings_scanned: number;
  summary: { open_market_purchases: number; purchase_value_usd: number; open_market_sales: number; sale_value_usd: number };
  transactions: InsiderTxn[] };
export type Filing = { form: string | null; filing_date: string; period_of_report: string | null; accession_number: string; url: string };
export type Filings = { symbol: string; company: string; filings: Filing[] };
export type OptionContract = { contract_symbol: string; strike: number; last_price: number | null; bid: number | null; ask: number | null;
  volume: number | null; open_interest: number | null; implied_volatility: number | null; in_the_money: boolean };
export type OptionsChain = { symbol: string; underlying_price: number | null; expiration_dates: string[];
  selected_expiration: string | null; calls: OptionContract[]; puts: OptionContract[] };

const holdersMemo = new Map<string, { at: number; p: Promise<HoldersResult> }>();
const HOLDERS_TTL = 10 * 60_000;
export const clearHoldersMemo = () => holdersMemo.clear();
function holdersMemoised(symbol: string): Promise<HoldersResult> {
  const key = symbol.toUpperCase();
  const hit = holdersMemo.get(key);
  if (hit && Date.now() - hit.at < HOLDERS_TTL) return hit.p;
  const p = getJson<HoldersResult>(`/api/holders/${encodeURIComponent(key)}`);
  holdersMemo.set(key, { at: Date.now(), p });
  p.catch(() => { if (holdersMemo.get(key)?.p === p) holdersMemo.delete(key); });
  return p;
}

const q = encodeURIComponent;
export const api = {
  quotes: (symbols: string[]) => getJson<Quote[]>(`/api/quotes?symbols=${q(symbols.slice(0, 30).join(","))}`),
  tape: () => getJson<TapeRow[]>("/api/tape"),
  news: (limit = 20) => getJson<NewsItem[]>(`/api/news?limit=${limit}`),
  diff: (manager: string) => getJson<DiffResult>(`/api/diff/${q(manager)}`),
  holders: holdersMemoised,
  managers: () => getJson<ManagerRef[]>("/api/managers"),
  filingAlerts: () => getJson<FilingAlert[]>("/api/filing-alerts"),
  security: (symbol: string, range?: string) => getJson<SecurityDetail>(`/api/security/${q(symbol)}${range ? `?range=${q(range)}` : ""}`),
  events: (s: string) => getJson<Events>(`/api/events/${q(s)}`),
  facts: (s: string) => getJson<Facts>(`/api/facts/${q(s)}`),
  insiders: (s: string, filings = 15) => getJson<Insiders>(`/api/insiders/${q(s)}?filings=${filings}`),
  filings: (s: string, limit = 15) => getJson<Filings>(`/api/filings/${q(s)}?limit=${limit}`),
  options: (s: string, expiration?: string) => getJson<OptionsChain>(`/api/options/${q(s)}${expiration ? `?expiration=${q(expiration)}` : ""}`),
  newsFor: (symbols: string[], limit = 15) => getJson<NewsItem[]>(`/api/news?limit=${limit}&symbols=${q(symbols.join(","))}`),
  markets: () => getJson<MarketSection[]>("/api/markets"),
  crypto: (limit = 50) => getJson<CryptoResult>(`/api/crypto?limit=${limit}`),
  fx: () => getJson<FxResult>("/api/fx"),
  macro: () => getJson<MacroResult>("/api/macro"),
  fedEvents: (limit = 15) => getJson<NewsItem[]>(`/api/fed-events?limit=${limit}`),
  regulatory: (limit = 15) => getJson<RegDoc[]>(`/api/regulatory?limit=${limit}`),
  screener: (qs: string) => getJson<ScreenerResult>(`/api/screener?${qs}`),
};
