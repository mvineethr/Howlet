import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import Block from "../blocks/Block";
import NewsList from "../components/NewsList";

const FIVE_MIN = 300_000;
const EARNINGS = /CNBC Earnings|Seeking Alpha/;

export default function NewsPage() {
  const wire = useApi("news:60", () => api.news(60), FIVE_MIN);
  const fed = useApi("fed:15", () => api.fedEvents(15), FIVE_MIN);
  const earnings = (wire.data ?? []).filter((n) => EARNINGS.test(n.source)).slice(0, 15);
  const half = "calc((100vh - 120px) / 2)";
  return (
    <div style={{ padding: 16, display: "grid", gridTemplateColumns: "minmax(0, 3fr) minmax(0, 2fr)", gap: 12 }}>
      <div style={{ height: "calc(100vh - 108px)" }}>
        <Block fixed title="Market wire" loading={wire.loading} error={wire.error} fetchedAt={wire.fetchedAt} refreshMs={FIVE_MIN}>
          {wire.data && <NewsList items={wire.data} empty="No headlines right now." />}
        </Block>
      </div>
      <div style={{ display: "grid", gridTemplateRows: `${half} ${half}`, gap: 12 }}>
        <Block fixed title="Earnings & analysis" loading={wire.loading} error={wire.error} fetchedAt={wire.fetchedAt} refreshMs={FIVE_MIN}>
          {wire.data && <NewsList items={earnings} empty="Nothing tagged earnings/analysis in the current wire." />}
        </Block>
        <Block fixed title="Fed & policy" loading={fed.loading} error={fed.error} fetchedAt={fed.fetchedAt} refreshMs={FIVE_MIN}>
          {fed.data && <NewsList items={fed.data} empty="No Fed items right now." />}
        </Block>
      </div>
    </div>
  );
}
