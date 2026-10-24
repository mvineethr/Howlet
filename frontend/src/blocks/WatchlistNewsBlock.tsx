import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { getWatchlists } from "../lib/legacy";
import { stockSymbols } from "../pages/smart/InsiderBuysTab";
import NewsList from "../components/NewsList";
import Block from "./Block";

export default function WatchlistNewsBlock({ list = "default", onRemove }: { list?: string; onRemove?: () => void }) {
  const syms = stockSymbols(getWatchlists()[list] ?? []).slice(0, 10);
  const { data, error, loading, fetchedAt } = useApi(syms.length ? `wl-news:${syms.join(",")}` : null, () => api.newsFor(syms, 20), 300_000);
  return (
    <Block title={`Watchlist news · ${list}`} {...{ loading, error, fetchedAt, refreshMs: 300_000, onRemove }}>
      {!syms.length && <span style={{ color: "var(--dim)" }}>No stock symbols in this list.</span>}
      {data && <NewsList items={data} empty="No headlines yet for these names." />}
    </Block>
  );
}
