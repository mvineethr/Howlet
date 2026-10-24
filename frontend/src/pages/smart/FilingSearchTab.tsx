import { useState } from "react";
import { Button, Caption1, Input, Link } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type FullTextHit } from "../../lib/api";
import { safeHref } from "../../lib/fmt";
import { useRoute } from "../../lib/route";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";

export const parseForms = (s: string): string[] => s.split(/[,\s]+/).map((f) => f.toUpperCase()).filter(Boolean);

const cols: Column<FullTextHit>[] = [
  { key: "d", label: "Filed", render: (r) => r.file_date },
  { key: "c", label: "Company", render: (r) => r.company },
  { key: "f", label: "Form", render: (r) => r.form },
  { key: "u", label: "Document", render: (r) => <Link href={safeHref(r.url)} target="_blank" rel="noopener noreferrer">{r.file_description || r.file_type || "document"}</Link> },
];

export default function FilingSearchTab({ query, forms }: { query: string; forms: string }) {
  const go = useRoute((r) => r.go);
  const [text, setText] = useState(query);
  const [formsText, setFormsText] = useState(forms);
  const run = () => {
    const q = text.trim();
    if (!q) return;
    const f = formsText.trim();
    go({ kind: "page", page: "smart", params: f ? ["search", q, f] : ["search", q] });
  };
  const onKey = (e: React.KeyboardEvent) => { if (e.key === "Enter") run(); };
  const { data, loading, error, fetchedAt } = useApi(query ? `fts:${query}:${forms}` : null, () => api.fulltext(query, parseForms(forms), 25));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Input size="small" style={{ width: 320 }} placeholder={'Words or a quoted phrase (e.g. "share repurchase")'} aria-label="Search words" value={text} onChange={(_, d) => setText(d.value)} onKeyDown={onKey} />
        <Input size="small" placeholder="Forms (optional, e.g. 10-K, 8-K)" aria-label="Forms" value={formsText} onChange={(_, d) => setFormsText(d.value)} onKeyDown={onKey} />
        <Button size="small" appearance="primary" onClick={run}>Search</Button>
      </div>
      <Caption1 style={{ color: "var(--dim)" }}>EDGAR full-text search covers filings since 2001.</Caption1>
      {query && (
        <Block fixed sec title={`Full-text search · "${query}"`} loading={loading} error={error} fetchedAt={fetchedAt}>
          {data && <DataTable columns={cols} rows={data.results} rowKey={(r, i) => `${r.accession_number}:${i}`} empty="No filings matched." />}
        </Block>
      )}
    </div>
  );
}
