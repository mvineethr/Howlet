import type { JSX } from "react";
import { Body1, Link } from "@fluentui/react-components";
import type { HomeState } from "../lib/legacy";
import Block from "./Block";
import WatchlistBlock from "./WatchlistBlock";
import SmartMoneyBlock from "./SmartMoneyBlock";
import PulseBlock from "./PulseBlock";
import NewsBlock from "./NewsBlock";

type Entry = { label: string; defaultSize: { w: number; h: number }; render: (cfg: Record<string, string>, onRemove: () => void) => JSX.Element };

export const BLOCKS: Record<string, Entry> = {
  watchlist: { label: "Watchlist", defaultSize: { w: 5, h: 10 }, render: (c, r) => <WatchlistBlock list={c.list} onRemove={r} /> },
  "manager-changes": { label: "Smart money moves", defaultSize: { w: 7, h: 10 }, render: (c, r) => <SmartMoneyBlock manager={c.manager} onRemove={r} /> },
  pulse: { label: "Market pulse", defaultSize: { w: 12, h: 5 }, render: (_c, r) => <PulseBlock onRemove={r} /> },
  "market-news": { label: "News", defaultSize: { w: 12, h: 10 }, render: (_c, r) => <NewsBlock onRemove={r} /> },
};

export function blockFor(type: string): Entry {
  return BLOCKS[type] ?? {
    label: type, defaultSize: { w: 6, h: 8 },
    render: (_c, r) => (
      <Block title={type} onRemove={r}>
        <Body1>This block arrives in the next update. Open it in the <Link href="/classic">classic view</Link>.</Body1>
      </Block>
    ),
  };
}

export function firstRunHome(): HomeState {
  return {
    active: "home",
    tabs: [{
      id: "home", name: "Home", blocks: [
        { i: "pulse", type: "pulse", config: {}, x: 0, y: 0, w: 12, h: 5 },
        { i: "wl", type: "watchlist", config: { list: "default" }, x: 0, y: 5, w: 5, h: 10 },
        { i: "sm", type: "manager-changes", config: { manager: "buffett" }, x: 5, y: 5, w: 7, h: 10 },
        { i: "news", type: "market-news", config: {}, x: 0, y: 15, w: 12, h: 10 },
      ],
    }],
  };
}
