import { Input, Text, makeStyles, tokens } from "@fluentui/react-components";
import { Search20Regular } from "@fluentui/react-icons";
import { useEffect, useRef, useState } from "react";
import { parseCommand } from "../lib/commands";
import { useRoute } from "../lib/route";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { addPriceAlert } from "../lib/alerts";

const useStyles = makeStyles({
  box: { width: "min(520px, 60vw)" },
  msg: { marginLeft: "8px", color: tokens.colorNeutralForeground3 },
});

export default function CommandBox() {
  const s = useStyles();
  const ref = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");
  const go = useRoute((r) => r.go);
  const { data: managers } = useApi("managers", api.managers);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key.toLowerCase() === "k") { e.preventDefault(); ref.current?.focus(); ref.current?.select(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const run = () => {
    const cmd = parseCommand(text, (managers ?? []).map((m) => m.label));
    if (!cmd) return;
    if (cmd.kind === "go") go(cmd.route);
    else if (cmd.kind === "manager") location.href = `/classic?cmd=${encodeURIComponent(cmd.id + " PORT")}`;
    else if (cmd.kind === "alert") { addPriceAlert(cmd.symbol, cmd.op, cmd.price); setMsg(`Alert set: ${cmd.symbol} ${cmd.op} ${cmd.price}`); }
    else { setMsg(cmd.message); return; }
    if (cmd.kind !== "alert") setMsg("");
    setText("");
    ref.current?.blur();
  };

  return (
    <div style={{ display: "flex", alignItems: "center" }}>
      <Input ref={ref} className={s.box} value={text} contentBefore={<Search20Regular />}
        placeholder="Search or command…   Ctrl+K   (AAPL · buffett · AAPL FA · ALERT TSLA < 200)"
        aria-label="Search or command" onChange={(_, d) => setText(d.value)}
        onKeyDown={(e) => { if (e.key === "Enter") run(); if (e.key === "Escape") { setText(""); ref.current?.blur(); } }} />
      {msg && <Text size={200} className={s.msg} role="status">{msg}</Text>}
    </div>
  );
}
