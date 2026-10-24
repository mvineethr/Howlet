type Props = { dates: string[]; a: number[]; b: number[]; aLabel: string; bLabel: string };

/** Two lines on one scale (e.g. account value vs SPY). Colours come from CSS tokens. */
export default function CompareChart({ dates, a, b, aLabel, bLabel }: Props) {
  const W = 600, H = 160, P = 4;
  if (dates.length < 2) return <span style={{ color: "var(--dim)" }}>The chart starts after the account's second trading day.</span>;
  const all = [...a, ...b];
  const lo = Math.min(...all), hi = Math.max(...all), span = hi - lo || 1;
  const pts = (v: number[]) => v.map((y, i) =>
    `${(P + (i / (v.length - 1)) * (W - 2 * P)).toFixed(1)},${(H - P - ((y - lo) / span) * (H - 2 * P)).toFixed(1)}`).join(" ");
  return (
    <div>
      <svg role="img" aria-label={`${aLabel} vs ${bLabel}`} viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none">
        <polyline points={pts(b)} fill="none" stroke="var(--cyan)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        <polyline points={pts(a)} fill="none" stroke="var(--amber)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
      </svg>
      <div style={{ display: "flex", gap: 16, fontSize: "0.85em", color: "var(--dim)" }}>
        <span><span style={{ color: "var(--amber)" }}>━</span> {aLabel}</span>
        <span><span style={{ color: "var(--cyan)" }}>━</span> {bLabel}</span>
        <span style={{ marginLeft: "auto" }}>{dates[0]} → {dates[dates.length - 1]}</span>
      </div>
    </div>
  );
}
