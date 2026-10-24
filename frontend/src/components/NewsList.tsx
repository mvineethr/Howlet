import { Link } from "@fluentui/react-components";
import type { NewsItem } from "../lib/api";
import { ago, safeHref } from "../lib/fmt";

export default function NewsList({ items, empty }: { items: NewsItem[]; empty: string }) {
  if (!items.length) return <div style={{ color: "var(--dim)" }}>{empty}</div>;
  return (
    <>
      {items.map((n, i) => (
        <div key={`${n.link}-${i}`} style={{ padding: "5px 0", borderBottom: "1px solid var(--hair)" }}>
          <Link href={safeHref(n.link)} target="_blank" rel="noopener noreferrer">{n.title}</Link>
          <div style={{ color: "var(--dim)", fontSize: "0.85em" }}>
            {[n.source, n.symbol, ago(n.published)].filter(Boolean).join(" · ")}
          </div>
        </div>
      ))}
    </>
  );
}
