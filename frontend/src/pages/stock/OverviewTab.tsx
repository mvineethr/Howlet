import { Badge } from "@fluentui/react-components";
import type { ReactNode } from "react";
import { useApi } from "../../lib/useApi";
import { api, type SecurityDetail, type Studies } from "../../lib/api";
import { fmtInt, fmtNum, signed, tone } from "../../lib/fmt";
import Block from "../../blocks/Block";

const STUDY_ROWS: [keyof Studies, string][] = [
  ["sma20", "SMA 20"], ["sma50", "SMA 50"], ["ema12", "EMA 12"], ["ema26", "EMA 26"], ["rsi14", "RSI 14"],
  ["macd", "MACD"], ["macd_signal", "MACD signal"], ["macd_histogram", "MACD hist"],
  ["bollinger_upper", "Bollinger upper"], ["bollinger_mid", "Bollinger mid"], ["bollinger_lower", "Bollinger lower"],
];
const ORB_COLOR = { ABOVE_RANGE: "success", BELOW_RANGE: "danger", INSIDE_RANGE: "informative" } as const;

const Stat = ({ k, v }: { k: string; v: ReactNode }) => (
  <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", borderBottom: "1px solid var(--hair)" }}>
    <span style={{ color: "var(--dim)" }}>{k}</span><span className="num">{v}</span>
  </div>
);

export default function OverviewTab({ symbol, q }: { symbol: string; q: SecurityDetail | undefined }) {
  const ev = useApi(`events:${symbol}`, () => api.events(symbol));
  const e = ev.data;
  const studies = q ? STUDY_ROWS.filter(([k]) => k in (q.studies ?? {})) : [];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 12, alignItems: "start" }}>
      <Block fixed title="Quote">
        {q && (
          <>
            <Stat k="Previous close" v={fmtNum(q.previous_close)} />
            <Stat k="Day range" v={`${fmtNum(q.day_low)} – ${fmtNum(q.day_high)}`} />
            <Stat k="52-week range" v={`${fmtNum(q.week52_low)} – ${fmtNum(q.week52_high)}`} />
            <Stat k="Volume" v={fmtInt(q.volume)} />
            <Stat k={`Range change (${q.range})`} v={<span style={{ color: tone(q.range_change_pct) }}>{q.range_change_pct == null ? "—" : `${signed(q.range_change_pct)}%`}</span>} />
            <Stat k="Type" v={q.instrument_type ?? "—"} />
            <Stat k="Exchange" v={q.exchange ?? "—"} />
            <Stat k="Currency" v={q.currency ?? "—"} />
          </>
        )}
      </Block>
      <Block fixed title="Events" loading={ev.loading} error={ev.error} fetchedAt={ev.fetchedAt}>
        {e && (
          <>
            <Stat k="Next earnings" v={e.next_earnings_date ?? "unknown"} />
            <Stat k="Analysts" v={e.analyst_recommendation ?? "n/a"} />
            {e.analyst_counts && (
              <div style={{ color: "var(--dim)", padding: "4px 0" }}>
                Strong buy {e.analyst_counts.strong_buy} · Buy {e.analyst_counts.buy} · Hold {e.analyst_counts.hold} · Sell {e.analyst_counts.sell} · Strong sell {e.analyst_counts.strong_sell}
              </div>
            )}
            <div style={{ marginTop: 6, fontWeight: 600 }}>Shareholder meetings</div>
            {e.shareholder_meetings.length
              ? e.shareholder_meetings.slice(0, 5).map((m) => <div key={m.accession_number}>{`${m.form} · ${m.filing_date}`}</div>)
              : <div style={{ color: "var(--dim)" }}>None on file.</div>}
          </>
        )}
      </Block>
      <Block fixed title="Studies">
        {q && (
          <>
            {studies.length
              ? studies.map(([k, label]) => <Stat key={k} k={label} v={fmtNum(q.studies[k] ?? null)} />)
              : <div style={{ color: "var(--dim)" }}>Not enough history to compute studies at this range.</div>}
            <div style={{ marginTop: 8, fontWeight: 600 }}>Opening range breakout</div>
            {q.orb == null ? (
              <div style={{ color: "var(--dim)" }}>ORB unavailable (needs today's intraday bars — try during market hours).</div>
            ) : (
              <>
                <Badge appearance="tint" color={ORB_COLOR[q.orb.status]}>{q.orb.status.replace("_", " ")}</Badge>
                <Stat k="Range" v={`${fmtNum(q.orb.range_low)} – ${fmtNum(q.orb.range_high)}`} />
                <Stat k="Breakout" v={<span style={{ color: tone(q.orb.breakout_pct) }}>{q.orb.breakout_pct === 0 ? "—" : `${signed(q.orb.breakout_pct)}%`}</span>} />
              </>
            )}
          </>
        )}
      </Block>
    </div>
  );
}
