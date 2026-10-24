import { useEffect, useRef, useState } from "react";

const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export default function Num({ value, pct, digits = 2, flash = true }: { value: number | null | undefined; pct?: boolean; digits?: number; flash?: boolean }) {
  const prev = useRef(value);
  const [dir, setDir] = useState<"up" | "down" | null>(null);
  useEffect(() => {
    if (flash && !reduced() && prev.current != null && value != null && value !== prev.current) {
      setDir(value > prev.current ? "up" : "down");
      const t = setTimeout(() => setDir(null), 600);
      prev.current = value;
      return () => clearTimeout(t);
    }
    prev.current = value;
  }, [value, flash]);
  if (value == null) return <span style={{ color: "var(--dim)" }}>—</span>;
  const color = pct ? (value > 0 ? "var(--up)" : value < 0 ? "var(--down)" : "var(--dim)") : undefined;
  const text = pct ? `${value > 0 ? "+" : ""}${value.toFixed(digits)}%` : value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return (
    <span style={{ fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color,
      background: dir ? `color-mix(in srgb, var(--${dir}) 25%, transparent)` : undefined,
      transition: "background 0.6s", borderRadius: 3 }}>{text}</span>
  );
}
