import { Button, Input, Tab, TabList, Text } from "@fluentui/react-components";
import { Add16Regular, Checkmark16Regular, Delete16Regular, Edit16Regular } from "@fluentui/react-icons";
import { useState } from "react";
import type { HomeState } from "../../lib/legacy";
import { addTab, deleteTab, renameTab } from "../../lib/homeState";

type Edit = { mode: "add" } | { mode: "rename"; id: string } | null;

export default function HomeTabBar({ home, save }: { home: HomeState; save: (h: HomeState) => void }) {
  const [edit, setEdit] = useState<Edit>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [confirmDel, setConfirmDel] = useState(false);
  const active = home.tabs.find((t) => t.id === home.active) ?? home.tabs[0];

  const start = (e: Edit, initial = "") => { setEdit(e); setText(initial); setError(""); setConfirmDel(false); };
  const commit = () => {
    if (!edit) return;
    const r = edit.mode === "add" ? addTab(home, text) : renameTab(home, edit.id, text);
    if ("error" in r) { setError(r.error); return; }
    save(r); setEdit(null);
  };

  return (
    <>
      <TabList selectedValue={active.id} onTabSelect={(_, d) => { setConfirmDel(false); save({ ...home, active: String(d.value) }); }}>
        {home.tabs.map((t) => (
          <Tab key={t.id} value={t.id} onDoubleClick={() => start({ mode: "rename", id: t.id }, t.name)}>{t.name}</Tab>
        ))}
      </TabList>
      <Button icon={<Edit16Regular />} appearance="subtle" aria-label={`Rename tab ${active.name}`} onClick={() => start({ mode: "rename", id: active.id }, active.name)} />
      {active.id !== "home" && home.tabs.length > 1 && (confirmDel ? (
        <>
          <Text size={200}>Delete tab?</Text>
          <Button size="small" appearance="primary" onClick={() => { save(deleteTab(home, active.id)); setConfirmDel(false); }}>Delete</Button>
          <Button size="small" appearance="subtle" onClick={() => setConfirmDel(false)}>Cancel</Button>
        </>
      ) : (
        <Button icon={<Delete16Regular />} appearance="subtle" aria-label={`Delete tab ${active.name}`} onClick={() => { setEdit(null); setConfirmDel(true); }} />
      ))}
      {edit ? (
        <>
          <Input size="small" autoFocus value={text} placeholder="Tab name" aria-label="Tab name" onChange={(_, d) => { setText(d.value); setError(""); }}
            onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setEdit(null); }} />
          <Button size="small" icon={<Checkmark16Regular />} aria-label="Confirm tab name" onClick={commit} />
          {error && <Text size={200} role="alert">{error}</Text>}
        </>
      ) : (
        <Button icon={<Add16Regular />} appearance="subtle" onClick={() => start({ mode: "add" })}>Tab</Button>
      )}
    </>
  );
}
