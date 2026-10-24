import { useState } from "react";
import { Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Dropdown, Field, Input, Option } from "@fluentui/react-components";
import { getWatchlists } from "../lib/legacy";
import ManagerPicker from "../components/ManagerPicker";
import { BLOCKS } from "./registry";

type Props = { open: boolean; onClose: () => void; onAdd: (type: string, config: Record<string, string>) => void };

export default function AddBlockDialog({ open, onClose, onAdd }: Props) {
  const [type, setType] = useState("");
  const [cfg, setCfg] = useState<Record<string, string>>({});
  const needs = type ? BLOCKS[type].needs : null;
  const lists = Object.keys(getWatchlists());
  const set = (k: string, v: string) => setCfg((c) => ({ ...c, [k]: v }));
  const required = needs === "manager" ? ["manager"] : needs === "list" ? ["list"] : needs === "symbol" ? ["symbol"] : needs === "manager-symbol" ? ["manager", "symbol"] : [];
  const ready = !!type && required.every((k) => cfg[k]);
  const close = () => { setType(""); setCfg({}); onClose(); };
  const submit = () => {
    onAdd(type, Object.fromEntries(required.map((k) => [k, cfg[k]])));
    setType(""); setCfg({});
  };
  return (
    <Dialog open={open} onOpenChange={(_, d) => { if (!d.open) close(); }}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Add block</DialogTitle>
          <DialogContent style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Field label="Block type">
              <Dropdown aria-label="Block type" value={type ? BLOCKS[type].label : ""} selectedOptions={type ? [type] : []}
                onOptionSelect={(_, d) => { setType(d.optionValue ?? ""); setCfg({}); }}>
                {Object.entries(BLOCKS).map(([t, e]) => <Option key={t} value={t} text={e.label}>{e.label}</Option>)}
              </Dropdown>
            </Field>
            {(needs === "manager" || needs === "manager-symbol") && (
              <Field label="Manager"><ManagerPicker value={cfg.manager ?? ""} onPick={(m) => set("manager", m)} /></Field>
            )}
            {needs === "list" && (
              <Field label="Watchlist">
                <Dropdown aria-label="Watchlist" value={cfg.list ?? ""} selectedOptions={cfg.list ? [cfg.list] : []} onOptionSelect={(_, d) => set("list", d.optionValue ?? "")}>
                  {lists.map((n) => <Option key={n} value={n}>{n}</Option>)}
                </Dropdown>
              </Field>
            )}
            {(needs === "symbol" || needs === "manager-symbol") && (
              <Field label="Symbol"><Input aria-label="Symbol" value={cfg.symbol ?? ""} onChange={(_, d) => set("symbol", d.value.trim().toUpperCase())} /></Field>
            )}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={close}>Cancel</Button>
            <Button appearance="primary" disabled={!ready} onClick={submit}>Add</Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
