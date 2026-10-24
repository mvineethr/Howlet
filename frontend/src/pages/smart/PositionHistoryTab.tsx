import { useState } from "react";
import { Button, Input } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api } from "../../lib/api";
import { fmtInt, fmtMoney, fmtNum, signed } from "../../lib/fmt";
import { useRoute } from "../../lib/route";
import Block from "../../blocks/Block";
import ManagerPicker from "../../components/ManagerPicker";

export default function PositionHistoryTab({ manager, query }: { manager: string; query: string }) {
  const go = useRoute((r) => r.go);
  const [mgr, setMgr] = useState(manager);
  const [text, setText] = useState(query);
  const run = () => { if (mgr && text.trim()) go({ kind: "page", page: "smart", params: ["history", mgr, text.trim()] }); };
  const ready = !!manager && !!query;
  const { data, loading, error, fetchedAt } = useApi(ready ? `phist:${manager}:${query}` : null, () => api.positionHistory(manager, query, 8));
  const maxV = Math.max(...(data?.quarters ?? []).map((q) => q.value_usd), 1);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ width: 260 }}><ManagerPicker key={manager} value={manager} onPick={setMgr} /></div>
        <Input size="small" placeholder="Ticker, CUSIP or name" aria-label="Ticker, CUSIP or name" value={text}
          onChange={(_, d) => setText(d.value)} onKeyDown={(e) => { if (e.key === "Enter") run(); }} />
        <Button size="small" appearance="primary" onClick={run}>Show</Button>
      </div>
      {!ready ? (
        <span style={{ color: "var(--dim)" }}>Pick a manager and a security to see their stake quarter by quarter.</span>
      ) : (
        <Block fixed sec title={data ? `${data.issuer} · CUSIP ${data.cusips.join(", ")}` : "Position history"} loading={loading} error={error} fetchedAt={fetchedAt}>
          {data && (
            <table className="dt">
              <thead><tr><th>Period</th><th>Value</th><th style={{ textAlign: "right" }}>Shares</th><th style={{ textAlign: "right" }}>Weight</th></tr></thead>
              <tbody>
                {data.quarters.map((q, i) => {
                  const d = i ? q.shares - data.quarters[i - 1].shares : 0;
                  return (
                    <tr key={`${q.period_of_report}:${i}`}>
                      <td>{q.period_of_report ?? "?"}</td>
                      <td>
                        <span className="num">{fmtMoney(q.value_usd)}</span>
                        <span style={{ display: "inline-block", verticalAlign: "middle", marginLeft: 8, height: 8, width: (q.value_usd / maxV) * 160, background: "var(--accent)", borderRadius: 3 }} />
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <span className="num">{fmtInt(q.shares)}</span>
                        {d !== 0 && <span className="num" style={{ marginLeft: 6, color: d > 0 ? "var(--up)" : "var(--down)" }}>{`(${signed(d, 0)})`}</span>}
                      </td>
                      <td style={{ textAlign: "right" }}><span className="num">{`${fmtNum(q.weight_pct, 1)}%`}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Block>
      )}
    </div>
  );
}
