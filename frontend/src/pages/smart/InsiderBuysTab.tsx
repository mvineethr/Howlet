import { useState } from "react";
import { Dropdown, Option } from "@fluentui/react-components";
import { getWatchlists } from "../../lib/legacy";
import { InsiderBuysPanel } from "./panels";

// Indices, FX, futures and crypto have no Form 4s.
export const stockSymbols = (list: string[]): string[] =>
  list.filter((s) => !s.startsWith("^") && !s.includes("=") && !s.includes("-USD"));

export default function InsiderBuysTab() {
  const lists = getWatchlists();
  const names = Object.keys(lists);
  const [name, setName] = useState(names.includes("default") ? "default" : names[0]);
  const symbols = stockSymbols(lists[name] ?? []).slice(0, 15);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ width: 260 }}>
        <Dropdown size="small" aria-label="Watchlist" value={name} selectedOptions={[name]} onOptionSelect={(_, d) => d.optionValue && setName(d.optionValue)}>
          {names.map((n) => <Option key={n} value={n}>{n}</Option>)}
        </Dropdown>
      </div>
      <InsiderBuysPanel list={symbols} />
    </div>
  );
}
