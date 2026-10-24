export default function Sparkline({ values, w = 70, h = 16 }: { values?: number[]; w?: number; h?: number }) {
  if (!values || values.length < 2) return null;
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(h - ((v - min) / span) * h).toFixed(1)}`).join(" ");
  const up = values[values.length - 1] >= values[0];
  return (
    <svg width={w} height={h} aria-hidden="true" style={{ display: "block" }}>
      <polyline points={pts} fill="none" strokeWidth={1.2} stroke={up ? "var(--up)" : "var(--down)"} />
    </svg>
  );
}
