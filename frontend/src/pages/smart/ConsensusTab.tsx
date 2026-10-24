import { Dropdown, Option } from "@fluentui/react-components";
import { useState } from "react";
import { ConsensusPanel } from "./panels";

export default function ConsensusTab() {
  const [min, setMin] = useState(2);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span>Held by at least</span>
        <Dropdown size="small" value={String(min)} selectedOptions={[String(min)]} onOptionSelect={(_, d) => setMin(Number(d.optionValue))} aria-label="Minimum managers">
          {[2, 3, 4, 5].map((m) => <Option key={m} value={String(m)}>{String(m)}</Option>)}
        </Dropdown>
        <span>managers</span>
      </div>
      <ConsensusPanel min={min} />
    </div>
  );
}
