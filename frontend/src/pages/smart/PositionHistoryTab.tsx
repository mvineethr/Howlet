import { useState } from "react";
import { Button, Input } from "@fluentui/react-components";
import { useRoute } from "../../lib/route";
import ManagerPicker from "../../components/ManagerPicker";
import { PositionHistoryPanel } from "./panels";

export default function PositionHistoryTab({ manager, query }: { manager: string; query: string }) {
  const go = useRoute((r) => r.go);
  const [mgr, setMgr] = useState(manager);
  const [text, setText] = useState(query);
  const run = () => { if (mgr && text.trim()) go({ kind: "page", page: "smart", params: ["history", mgr, text.trim()] }); };
  const ready = !!manager && !!query;

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
        <PositionHistoryPanel manager={manager} query={query} />
      )}
    </div>
  );
}
