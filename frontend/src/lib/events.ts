import { useEffect, useState } from "react";
import { api, type Events } from "./api";

// Shared across mounts: events lookups hit throttled SEC proxy pages, so never refetch within a session.
const eventsCache = new Map<string, Events | "error">();

// Sequential on purpose: each lookup can trigger throttled SEC requests.
export function useSequentialEvents(symbols: string[]): Map<string, Events | "error"> {
  const [, setTick] = useState(0);
  const key = symbols.join(",");
  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (const s of key ? key.split(",") : []) {
        if (cancelled) break;
        if (!eventsCache.has(s)) {
          try { eventsCache.set(s, await api.events(s)); } catch { eventsCache.set(s, "error"); }
        }
        setTick((t) => t + 1);
      }
    })();
    return () => { cancelled = true; };
  }, [key]);
  return eventsCache;
}
