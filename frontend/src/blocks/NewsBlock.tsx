import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import NewsList from "../components/NewsList";
import Block from "./Block";

export default function NewsBlock({ onRemove }: { onRemove?: () => void }) {
  const { data, error, loading, fetchedAt } = useApi("news", () => api.news(20), 300_000);
  return (
    <Block title="News" {...{ loading, error, fetchedAt, refreshMs: 300_000, onRemove }}>
      {data && <NewsList items={data} empty="No headlines right now." />}
    </Block>
  );
}
