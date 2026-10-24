import { Link } from "@fluentui/react-components";
import { useRoute } from "../lib/route";

export default function Ticker({ symbol }: { symbol: string | null | undefined }) {
  const go = useRoute((r) => r.go);
  if (!symbol) return <span style={{ color: "var(--dim)" }}>—</span>;
  return (
    <Link onClick={(e) => { e.stopPropagation(); go({ kind: "stock", symbol, tab: "overview" }); }}>{symbol}</Link>
  );
}
