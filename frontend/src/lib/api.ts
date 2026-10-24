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

const q = encodeURIComponent;
export const api = {
  quotes: (symbols: string[]) => getJson<Quote[]>(`/api/quotes?symbols=${q(symbols.slice(0, 30).join(","))}`),
  tape: () => getJson<TapeRow[]>("/api/tape"),
  news: (limit = 20) => getJson<NewsItem[]>(`/api/news?limit=${limit}`),
  diff: (manager: string) => getJson<DiffResult>(`/api/diff/${q(manager)}`),
  holders: (symbol: string) => getJson<HoldersResult>(`/api/holders/${q(symbol)}`),
  managers: () => getJson<ManagerRef[]>("/api/managers"),
  filingAlerts: () => getJson<FilingAlert[]>("/api/filing-alerts"),
  security: (symbol: string) => getJson<Security>(`/api/security/${q(symbol)}`),
  markets: () => getJson<MarketSection[]>("/api/markets"),
  crypto: (limit = 50) => getJson<CryptoResult>(`/api/crypto?limit=${limit}`),
  fx: () => getJson<FxResult>("/api/fx"),
  macro: () => getJson<MacroResult>("/api/macro"),
  fedEvents: (limit = 15) => getJson<NewsItem[]>(`/api/fed-events?limit=${limit}`),
  regulatory: (limit = 15) => getJson<RegDoc[]>(`/api/regulatory?limit=${limit}`),
  screener: (qs: string) => getJson<ScreenerResult>(`/api/screener?${qs}`),
};
