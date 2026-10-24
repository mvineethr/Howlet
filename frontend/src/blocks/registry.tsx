import type { JSX } from "react";
import { Body1 } from "@fluentui/react-components";
import type { HomeState } from "../lib/legacy";
import { getWatchlists } from "../lib/legacy";
import Block from "./Block";
import WatchlistBlock from "./WatchlistBlock";
import SmartMoneyBlock from "./SmartMoneyBlock";
import PulseBlock from "./PulseBlock";
import NewsBlock from "./NewsBlock";
import WorldMarketsBlock from "./WorldMarketsBlock";
import WatchlistNewsBlock from "./WatchlistNewsBlock";
import WatchlistEventsBlock from "./WatchlistEventsBlock";
import { ConsensusPanel, FundPanel, HoldingsPanel, InsiderBuysPanel, PositionHistoryPanel } from "../pages/smart/panels";
import { stockSymbols } from "../pages/smart/InsiderBuysTab";
import { FilingsPanel, InsidersPanel } from "../pages/stock/panels";
import { FedPanel, YieldCurvePanel } from "../pages/markets/panels";
import CryptoTab from "../pages/markets/CryptoTab";
import FxTab from "../pages/markets/FxTab";

export type Needs = "manager" | "list" | "symbol" | "manager-symbol" | null;
type Entry = { label: string; needs: Needs; defaultSize: { w: number; h: number }; render: (cfg: Record<string, string>, onRemove: () => void) => JSX.Element };

export const BLOCKS: Record<string, Entry> = {
  watchlist: { label: "Watchlist", needs: "list", defaultSize: { w: 5, h: 10 }, render: (c, r) => <WatchlistBlock list={c.list} onRemove={r} /> },
  "manager-changes": { label: "Smart money moves", needs: "manager", defaultSize: { w: 7, h: 10 }, render: (c, r) => <SmartMoneyBlock manager={c.manager} onRemove={r} /> },
  pulse: { label: "Market pulse", needs: null, defaultSize: { w: 12, h: 5 }, render: (_c, r) => <PulseBlock onRemove={r} /> },
  "market-news": { label: "News", needs: null, defaultSize: { w: 12, h: 10 }, render: (_c, r) => <NewsBlock onRemove={r} /> },
  "manager-portfolio": { label: "13F portfolio", needs: "manager", defaultSize: { w: 7, h: 12 }, render: (c, r) => <HoldingsPanel manager={c.manager} top={15} compact onRemove={r} /> },
  consensus: { label: "Smart money consensus", needs: null, defaultSize: { w: 7, h: 12 }, render: (_c, r) => <ConsensusPanel limit={10} onRemove={r} /> },
  "watchlist-news": { label: "Watchlist news", needs: "list", defaultSize: { w: 6, h: 10 }, render: (c, r) => <WatchlistNewsBlock list={c.list} onRemove={r} /> },
  "watchlist-events": { label: "Watchlist events", needs: "list", defaultSize: { w: 6, h: 10 }, render: (c, r) => <WatchlistEventsBlock list={c.list} onRemove={r} /> },
  insiders: { label: "Insider transactions", needs: "symbol", defaultSize: { w: 6, h: 10 }, render: (c, r) => <InsidersPanel symbol={c.symbol} title={`Insider transactions · ${c.symbol}`} onRemove={r} /> },
  "insider-buys": {
    label: "Insider buys (screen)", needs: "list", defaultSize: { w: 6, h: 10 },
    render: (c, r) => <InsiderBuysPanel title={`Insider buys · ${c.list}`} list={stockSymbols(getWatchlists()[c.list] ?? []).slice(0, 15)} onRemove={r} />,
  },
  "position-history": { label: "13F position history", needs: "manager-symbol", defaultSize: { w: 6, h: 10 }, render: (c, r) => <PositionHistoryPanel manager={c.manager} query={c.symbol} onRemove={r} /> },
  fed: { label: "Fed & policy", needs: null, defaultSize: { w: 6, h: 10 }, render: (_c, r) => <FedPanel limit={10} onRemove={r} /> },
  "yield-curve": { label: "Treasury yield curve", needs: null, defaultSize: { w: 6, h: 10 }, render: (_c, r) => <YieldCurvePanel onRemove={r} /> },
  "world-markets": { label: "World markets", needs: null, defaultSize: { w: 12, h: 12 }, render: (_c, r) => <WorldMarketsBlock onRemove={r} /> },
  crypto: { label: "Crypto top 20", needs: null, defaultSize: { w: 7, h: 12 }, render: (_c, r) => <CryptoTab limit={20} onRemove={r} /> },
  filings: { label: "SEC filings", needs: "symbol", defaultSize: { w: 6, h: 10 }, render: (c, r) => <FilingsPanel symbol={c.symbol} title={`SEC filings · ${c.symbol}`} onRemove={r} /> },
  "fx-matrix": { label: "FX cross rates", needs: null, defaultSize: { w: 7, h: 10 }, render: (_c, r) => <FxTab onRemove={r} /> },
  fund: { label: "ETF/fund holdings", needs: "symbol", defaultSize: { w: 7, h: 12 }, render: (c, r) => <FundPanel symbol={c.symbol} top={25} onRemove={r} /> },
};

export function blockFor(type: string): Entry {
  return BLOCKS[type] ?? {
    label: type, needs: null, defaultSize: { w: 6, h: 8 },
    render: (_c, r) => (
      <Block title={type} onRemove={r}>
        <Body1>Unknown block type — remove it.</Body1>
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
