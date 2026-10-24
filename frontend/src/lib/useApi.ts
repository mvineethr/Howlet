import { useCallback, useEffect, useRef, useState } from "react";

export function useApi<T>(key: string | null, fetcher: () => Promise<T>, refreshMs?: number) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [loading, setLoading] = useState(false);
  const [fetchedAt, setFetchedAt] = useState<number>();
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const load = useCallback(() => {
    if (key === null) return;
    setLoading(true);
    fetcherRef.current()
      .then((d) => { setData(d); setError(undefined); setFetchedAt(Date.now()); })
      .catch((e: Error) => setError(e)) // keep last good data on failure
      .finally(() => setLoading(false));
  }, [key]);

  useEffect(() => {
    setData(undefined);
    setError(undefined);
    load();
    if (!refreshMs || key === null) return;
    const id = setInterval(load, refreshMs);
    return () => clearInterval(id);
  }, [key, refreshMs, load]);

  return { data, error, loading, fetchedAt, reload: load };
}
