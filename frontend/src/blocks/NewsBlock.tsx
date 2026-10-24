import { Link } from "@fluentui/react-components";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import Block from "./Block";

const ago = (iso: string | null) => {
  if (!iso) return "";
  const m = Math.round((Date.now() - Date.parse(iso)) / 60000);
  return m < 60 ? `${m}m` : m < 1440 ? `${Math.round(m / 60)}h` : `${Math.round(m / 1440)}d`;
};

export default function NewsBlock({ onRemove }: { onRemove?: () => void }) {
  const { data, error, loading, fetchedAt } = useApi("news", () => api.news(20), 300_000);
  return (
    <Block title="News" {...{ loading, error, fetchedAt, refreshMs: 300_000, onRemove }}>
      {data?.map((n) => (
        <div key={n.link} style={{ padding: "4px 0", borderBottom: "1px solid var(--hair)" }}>
          <Link href={n.link} target="_blank" rel="noreferrer">{n.title}</Link>
          <div style={{ color: "var(--dim)", fontSize: "0.85em" }}>{n.source} · {ago(n.published)}</div>
        </div>
      ))}
    </Block>
  );
}
