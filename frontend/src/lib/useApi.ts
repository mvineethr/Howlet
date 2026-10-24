import { useCallback, useEffect, useRef, useState } from "react";

export function useApi<T>(key: string | null, fetcher: () => Promise<T>, refreshMs?: number) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [loading, setLoading] = useState(false);
  const [fetchedAt, setFetchedAt] = useState<number>();
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const reqId = useRef(0);

  const load = useCallback(() => {
    if (key === null) return;
    const id = ++reqId.current;
    setLoading(true);
    fetcherRef.current()
      .then((d) => { if (id === reqId.current) { setData(d); setError(undefined); setFetchedAt(Date.now()); } })
      .catch((e: Error) => { if (id === reqId.current) setError(e); }) // keep last good data on failure
      .finally(() => { if (id === reqId.current) setLoading(false); });
  }, [key]);

  useEffect(() => {
    setData(undefined);
    setError(undefined);
    load();
    if (!refreshMs || key === null) return;
    const id = setInterval(load, refreshMs);
    return () => clearInterval(id);
  }, [key, refreshMs, load]);

  // Drop any in-flight response once the key changes or the block unmounts.
  useEffect(() => () => { reqId.current++; }, [key]);

  return { data, error, loading, fetchedAt, reload: load };
}
