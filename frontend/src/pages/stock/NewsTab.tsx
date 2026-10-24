import { useApi } from "../../lib/useApi";
import { api } from "../../lib/api";
import Block from "../../blocks/Block";
import NewsList from "../../components/NewsList";

const FIVE_MIN = 300_000;

export default function NewsTab({ symbol }: { symbol: string }) {
  const { data, error, loading, fetchedAt } = useApi(`news:${symbol}`, () => api.newsFor([symbol], 15), FIVE_MIN);
  return (
    <Block fixed title={`News · ${symbol}`} loading={loading} error={error} fetchedAt={fetchedAt} refreshMs={FIVE_MIN}>
      {data && <NewsList items={data} empty="No headlines for this symbol." />}
    </Block>
  );
}
