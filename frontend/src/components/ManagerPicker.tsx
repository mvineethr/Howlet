import { Combobox, Option } from "@fluentui/react-components";
import { useState } from "react";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";

export default function ManagerPicker({ value, onPick }: { value: string; onPick: (m: string) => void }) {
  const { data } = useApi("managers", api.managers);
  const [text, setText] = useState(value);
  const commit = (v: string) => { const m = v.trim().toLowerCase(); if (m) onPick(m); };
  return (
    <Combobox freeform size="small" placeholder="Manager or CIK" value={text} aria-label="Manager or CIK"
      onChange={(e) => setText((e.target as HTMLInputElement).value)}
      onOptionSelect={(_, d) => { if (d.optionValue) { setText(d.optionValue); commit(d.optionValue); } }}
      onKeyDown={(e) => { if (e.key === "Enter") commit(text); }}>
      {(data ?? []).map((m) => <Option key={m.cik} value={m.label}>{m.label}</Option>)}
    </Combobox>
  );
}
