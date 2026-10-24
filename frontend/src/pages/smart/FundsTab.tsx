import { useState } from "react";
import { Button, Caption1, Input } from "@fluentui/react-components";
import { useRoute } from "../../lib/route";
import { FundPanel } from "./panels";

export default function FundsTab({ symbol }: { symbol: string }) {
  const go = useRoute((r) => r.go);
  const [text, setText] = useState(symbol);
  const run = () => { const s = text.trim().toUpperCase(); if (s) go({ kind: "page", page: "smart", params: ["funds", s] }); };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <Input size="small" placeholder="ETF or mutual fund ticker" aria-label="Fund ticker" value={text} onChange={(_, d) => setText(d.value)} onKeyDown={(e) => { if (e.key === "Enter") run(); }} />
        <Button size="small" appearance="primary" onClick={run}>Load</Button>
      </div>
      <Caption1 style={{ color: "var(--dim)" }}>Funds report holdings monthly on SEC Form N-PORT. Unit investment trusts such as SPY don't file it.</Caption1>
      {symbol && <FundPanel symbol={symbol} />}
    </div>
  );
}
