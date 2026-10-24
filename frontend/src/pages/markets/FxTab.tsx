import { useApi } from "../../lib/useApi";
import { api } from "../../lib/api";
import { fmtNum } from "../../lib/fmt";
import Block from "../../blocks/Block";

const HOUR = 3_600_000;

export default function FxTab() {
  const { data, error, loading, fetchedAt } = useApi("fx", api.fx, HOUR);
  const cur = data?.currencies ?? [];
  return (
    <Block fixed title={`FX cross rates · ECB reference${data?.date ? `, ${data.date}` : ""} · row → column`}
      loading={loading} error={error} fetchedAt={fetchedAt} refreshMs={HOUR}>
      {data && (!data.matrix ? (
        <span style={{ color: "var(--dim)" }}>FX rates unavailable right now (ECB/Frankfurter unreachable).</span>
      ) : (
        <table className="dt">
          <thead><tr><th />{cur.map((c) => <th key={c} style={{ textAlign: "right" }}>{c}</th>)}</tr></thead>
          <tbody>
            {cur.map((row) => (
              <tr key={row}>
                <th style={{ position: "static" }}>{row}</th>
                {cur.map((col) => {
                  const v = data.matrix?.[row]?.[col];
                  return (
                    <td key={col} className="num" style={{ textAlign: "right", color: row === col ? "var(--dim)" : undefined }}>
                      {row === col || v == null ? "—" : fmtNum(v, v >= 100 ? 2 : 4)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      ))}
    </Block>
  );
}
