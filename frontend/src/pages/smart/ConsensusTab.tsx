import { Button, Caption1, Dropdown, Option } from "@fluentui/react-components";
import { useState } from "react";
import { useApi } from "../../lib/useApi";
import { api, type ConsensusRow } from "../../lib/api";
import { fmtMoney, fmtNum } from "../../lib/fmt";
import { downloadCsv } from "../../lib/csv";
import Block from "../../blocks/Block";
import DataTable, { tableCsv, type Column } from "../../components/DataTable";

export default function ConsensusTab() {
  const [min, setMin] = useState(2);
  const { data, error, loading, fetchedAt } = useApi(`consensus:${min}`, () => api.consensus(min, 25));
  const n = data?.managers.length ?? 0;
  const cols: Column<ConsensusRow>[] = [
    { key: "i", label: "Issuer", render: (r) => r.issuer, csv: (r) => r.issuer },
    { key: "h", label: "Held by", align: "right", render: (r) => <span className="num" style={{ color: "var(--up)" }}>{`${r.manager_count} of ${n}`}</span>, csv: (r) => r.manager_count },
    { key: "m", label: "Managers", render: (r) => <span title={Object.entries(r.weights_pct).map(([k, v]) => `${k}: ${v.toFixed(1)}%`).join("\n")}>{Object.keys(r.weights_pct).join(", ")}</span>, csv: (r) => Object.keys(r.weights_pct).join(" ") },
    { key: "w", label: "Combined weight", align: "right", render: (r) => <span className="num">{`${fmtNum(r.combined_weight_pct, 1)}%`}</span>, csv: (r) => r.combined_weight_pct },
    { key: "v", label: "Total value", align: "right", render: (r) => <span className="num">{fmtMoney(r.total_value_usd)}</span>, csv: (r) => r.total_value_usd },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span>Held by at least</span>
        <Dropdown size="small" value={String(min)} selectedOptions={[String(min)]} onOptionSelect={(_, d) => setMin(Number(d.optionValue))} aria-label="Minimum managers">
          {[2, 3, 4, 5].map((m) => <Option key={m} value={String(m)}>{String(m)}</Option>)}
        </Dropdown>
        <span>managers</span>
      </div>
      <Block fixed sec title={data ? `Consensus across ${n} managers` : "Consensus"} loading={loading} error={error} fetchedAt={fetchedAt}
        actions={data?.rows.length ? <Button size="small" onClick={() => downloadCsv("consensus.csv", tableCsv(cols, data.rows))}>Export CSV</Button> : undefined}>
        {!data && !error && <span style={{ color: "var(--dim)" }}>Comparing every tracked manager's latest 13F (first run maps tickers; can take a minute)…</span>}
        {data && (
          <>
            <Caption1 style={{ color: "var(--dim)" }}>{data.managers.map((m) => m.label).join(" / ")}</Caption1>
            <DataTable columns={cols} rows={data.rows} rowKey={(r) => r.cusip} empty="No overlapping positions found." />
          </>
        )}
      </Block>
    </div>
  );
}
