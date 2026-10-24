type N = number | null | undefined;
const bad = (n: N): n is null | undefined => n == null || Number.isNaN(n);

export const fmtNum = (n: N, digits = 2): string =>
  bad(n) ? "—" : n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const fmtInt = (n: N): string => (bad(n) ? "—" : Math.round(n).toLocaleString("en-US"));

export function fmtMoney(usd: N): string {
  if (bad(usd)) return "—";
  const a = Math.abs(usd), s = usd < 0 ? "-" : "";
  if (a >= 1e12) return `${s}$${(a / 1e12).toFixed(2)}T`;
  if (a >= 1e9) return `${s}$${(a / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(1)}M`;
  return `${s}$${fmtInt(a)}`;
}

export const signed = (n: N, digits = 2): string => (bad(n) ? "—" : `${n > 0 ? "+" : ""}${fmtNum(n, digits)}`);

export const tone = (n: N): string => (bad(n) || n === 0 ? "var(--dim)" : n > 0 ? "var(--up)" : "var(--down)");

export const priceDigits = (p: N): number => (!bad(p) && Math.abs(p) < 1 ? 4 : 2);

export function ago(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const m = Math.max(0, Math.round((now - t) / 60000));
  return m < 60 ? `${m}m` : m < 1440 ? `${Math.round(m / 60)}h` : `${Math.round(m / 1440)}d`;
}

export const safeHref = (url: string | null | undefined): string | undefined =>
  url && /^https?:\/\//i.test(url) ? url : undefined;
