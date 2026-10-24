import { useEffect, useState } from "react";
import {
  Button, Caption1, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle,
  Field, Input, Radio, RadioGroup, Text,
} from "@fluentui/react-components";
import { api, type PaperOrder } from "../lib/api";
import { useApi } from "../lib/useApi";
import { estimate, explain, parseNum, sharesFor, usd, type OrderType, type Side } from "../lib/paper";

type Props = { open: boolean; onClose: () => void; symbol?: string; onPlaced?: (o: PaperOrder) => void };

export default function OrderTicket({ open, onClose, symbol = "", onPlaced }: Props) {
  const [sym, setSym] = useState(symbol);
  const [quoteSym, setQuoteSym] = useState(symbol.trim().toUpperCase());
  const [side, setSide] = useState<Side>("buy");
  const [type, setType] = useState<OrderType>("market");
  const [mode, setMode] = useState<"shares" | "dollars">("shares");
  const [amount, setAmount] = useState("");
  const [levelText, setLevelText] = useState("");
  const [tif, setTif] = useState<"day" | "gtc">("day");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSym(symbol); setQuoteSym(symbol.trim().toUpperCase()); setAmount(""); setLevelText(""); setErr("");
  }, [open, symbol]);
  useEffect(() => { // wait for typing to pause before fetching a quote
    const t = setTimeout(() => setQuoteSym(sym.trim().toUpperCase()), 400);
    return () => clearTimeout(t);
  }, [sym]);

  const quote = useApi(open && quoteSym ? `ticket-quote:${quoteSym}` : null, () => api.quotes([quoteSym]));
  const acct = useApi(open ? "ticket-account" : null, () => api.paperAccount());
  const price = quote.data?.[0]?.price ?? null;
  const level = type === "market" ? null : parseNum(levelText);
  const amt = parseNum(amount);
  const unit = type === "market" ? price : level;
  const qty = amt == null || amt <= 0 ? null : mode === "shares" ? amt : unit ? sharesFor(amt, unit) : null;
  const est = qty == null ? null : estimate(type, qty, price, level);
  const a = acct.data?.account ? acct.data : null;
  const held = a?.positions.find((p) => p.symbol === quoteSym)?.qty ?? 0;
  const after = !a || est == null ? null
    : side === "buy" ? `Cash after: ${usd(a.cash - est)}` : `${quoteSym} shares after: ${+(held - (qty ?? 0)).toFixed(4)}`;

  const submit = async () => {
    if (!sym.trim() || qty == null) { setErr("Enter a symbol and a quantity."); return; }
    if (type !== "market" && (level == null || level <= 0)) { setErr(`Enter a ${type} price.`); return; }
    setBusy(true); setErr("");
    try {
      const o = await api.paperOrder({ symbol: sym.trim().toUpperCase(), side, qty, type,
        limit: type === "limit" ? level : null, stop: type === "stop" ? level : null, tif });
      onPlaced?.(o);
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(_, d) => { if (!d.open) onClose(); }}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Paper order</DialogTitle>
          <DialogContent style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Caption1 style={{ color: "var(--dim)" }}>Fake money — practice only. Prices are delayed up to 15 minutes.</Caption1>
            <Field label="Symbol">
              <Input value={sym} onChange={(_, d) => setSym(d.value)} />
            </Field>
            {price != null && <Text size={200}>Last price {usd(price)}</Text>}
            <RadioGroup layout="horizontal" value={side} onChange={(_, d) => setSide(d.value as Side)} aria-label="Side">
              <Radio value="buy" label="Buy" /><Radio value="sell" label="Sell" />
            </RadioGroup>
            <RadioGroup layout="horizontal" value={type} onChange={(_, d) => setType(d.value as OrderType)} aria-label="Order type">
              <Radio value="market" label="Market" /><Radio value="limit" label="Limit" /><Radio value="stop" label="Stop" />
            </RadioGroup>
            {type !== "market" && (
              <Field label={type === "limit" ? "Limit price" : "Stop price"}>
                <Input inputMode="decimal" value={levelText} onChange={(_, d) => setLevelText(d.value)} />
              </Field>
            )}
            <RadioGroup layout="horizontal" value={mode} onChange={(_, d) => setMode(d.value as "shares" | "dollars")} aria-label="Size by">
              <Radio value="shares" label="Shares" /><Radio value="dollars" label="Dollars" />
            </RadioGroup>
            <Field label={mode === "shares" ? "Quantity" : "Amount in dollars"}>
              <Input inputMode="decimal" value={amount} onChange={(_, d) => setAmount(d.value)} />
            </Field>
            {mode === "dollars" && qty != null && <Text size={200}>= {qty} shares</Text>}
            <RadioGroup layout="horizontal" value={tif} onChange={(_, d) => setTif(d.value as "day" | "gtc")} aria-label="Time in force">
              <Radio value="day" label="Today only" /><Radio value="gtc" label="Good 'til cancelled (90 days)" />
            </RadioGroup>
            <Text size={200}>{explain(side, type, level)}</Text>
            {est != null && <Text weight="semibold">Estimated {side === "buy" ? "cost" : "proceeds"} {usd(est)}</Text>}
            {after && <Text size={200} style={{ color: "var(--dim)" }}>{after}</Text>}
            {err && <Text role="alert" style={{ color: "var(--down)" }}>{err}</Text>}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={onClose}>Cancel</Button>
            <Button appearance="primary" disabled={busy} onClick={submit}>Place paper order</Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
