import {
  Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Input, Menu, MenuDivider, MenuItem,
  MenuList, MenuPopover, MenuTrigger, Text,
} from "@fluentui/react-components";
import { useState } from "react";
import type { HomeState } from "../../lib/legacy";
import {
  applySnapshot, deleteSnapshot, loadSnapshots, saveSnapshot, SNAPSHOTS_KEY, type Snapshots,
} from "../../lib/homeState";
import { writeJson } from "../../lib/storage";
import { firstRunHome } from "../../blocks/registry";

type Pending = { text: string; run: () => void } | null;

export default function LayoutsMenu({ home, save }: { home: HomeState; save: (h: HomeState) => void }) {
  const [snaps, setSnaps] = useState<Snapshots>(loadSnapshots);
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState<Pending>(null);
  const names = Object.keys(snaps).sort();

  const persist = (s: Snapshots) => { setSnaps(s); writeJson(SNAPSHOTS_KEY, s); };
  const doSave = () => {
    const key = name.trim().toLowerCase();
    const r = saveSnapshot(snaps, name, home);
    const err = (r as { error?: unknown }).error;
    if (typeof err === "string") { setError(err); return; }
    const write = () => { persist(r as Snapshots); setNaming(false); setPending(null); };
    if (key in snaps) setPending({ text: `Overwrite layout "${key}"?`, run: write }); else write();
  };

  return (
    <>
      <Menu>
        <MenuTrigger disableButtonEnhancement><Button appearance="subtle">Layouts</Button></MenuTrigger>
        <MenuPopover>
          <MenuList>
            <MenuItem onClick={() => { setName(""); setError(""); setNaming(true); }}>Save current…</MenuItem>
            <Menu>
              <MenuTrigger disableButtonEnhancement><MenuItem disabled={!names.length}>Load</MenuItem></MenuTrigger>
              <MenuPopover><MenuList>
                {names.map((n) => (
                  <MenuItem key={n} onClick={() => setPending({ text: `Replace the current Home with "${n}"?`, run: () => save(applySnapshot(snaps[n])) })}>{n}</MenuItem>
                ))}
              </MenuList></MenuPopover>
            </Menu>
            <Menu>
              <MenuTrigger disableButtonEnhancement><MenuItem disabled={!names.length}>Delete</MenuItem></MenuTrigger>
              <MenuPopover><MenuList>
                {names.map((n) => <MenuItem key={n} onClick={() => persist(deleteSnapshot(snaps, n))}>{n}</MenuItem>)}
              </MenuList></MenuPopover>
            </Menu>
            <MenuDivider />
            <MenuItem onClick={() => setPending({ text: "Replace the current Home with the default layout?", run: () => save(firstRunHome()) })}>Restore default</MenuItem>
          </MenuList>
        </MenuPopover>
      </Menu>
      <Dialog open={naming} onOpenChange={(_, d) => setNaming(d.open)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Save layout</DialogTitle>
            <DialogContent>
              <Input autoFocus value={name} placeholder="Layout name" aria-label="Layout name"
                onChange={(_, d) => { setName(d.value); setError(""); }} onKeyDown={(e) => { if (e.key === "Enter") doSave(); }} />
              {error && <Text block size={200}>{error}</Text>}
            </DialogContent>
            <DialogActions>
              <Button appearance="secondary" onClick={() => setNaming(false)}>Cancel</Button>
              <Button appearance="primary" onClick={doSave}>Save</Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
      <Dialog open={!!pending} onOpenChange={(_, d) => { if (!d.open) setPending(null); }}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Are you sure?</DialogTitle>
            <DialogContent>{pending?.text}</DialogContent>
            <DialogActions>
              <Button appearance="secondary" onClick={() => setPending(null)}>Cancel</Button>
              <Button appearance="primary" onClick={() => { pending?.run(); setPending(null); }}>Confirm</Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </>
  );
}
