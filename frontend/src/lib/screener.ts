export type ScreenerInputs = { peMax: string; mcapMinB: string; growthMin: string; marginMin: string };

const FIELDS: [keyof ScreenerInputs, string, number][] = [
  ["peMax", "pe_ratio_max", 1],
  ["mcapMinB", "market_cap_min", 1e9],
  ["growthMin", "revenue_growth_pct_min", 1],
  ["marginMin", "net_margin_pct_min", 1],
];

export function buildScreenerQuery(f: ScreenerInputs): { qs: string } | { error: keyof ScreenerInputs } {
  const p = new URLSearchParams();
  for (const [field, param, scale] of FIELDS) {
    const raw = f[field].trim();
    if (!raw) continue;
    const n = Number(raw);
    if (!Number.isFinite(n)) return { error: field };
    p.set(param, String(n * scale));
  }
  return { qs: p.toString() };
}
