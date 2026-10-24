import { addPriceAlert, evaluate, getAlerts, removeAlert, type PriceAlert } from "./alerts";

beforeEach(() => localStorage.clear());

const a = (over: Partial<PriceAlert>): PriceAlert => ({ id: "1", sym: "AAPL", op: ">", px: 100, fired: null, ...over });

test("fires only crossed, unfired alerts with a known price", () => {
  const list = [
    a({ id: "1", op: ">", px: 100 }),           // 101 > 100: fires
    a({ id: "2", op: "<", px: 100 }),           // 101 < 100: no
    a({ id: "3", sym: "TSLA" }),                 // no price: no
    a({ id: "4", fired: { price: 1, at: "x" } }), // already fired: no
  ];
  const fired = evaluate(list, { AAPL: 101 }, "2026-10-23T00:00:00Z");
  expect(fired.map((f) => f.id)).toEqual(["1"]);
  expect(fired[0].fired).toEqual({ price: 101, at: "2026-10-23T00:00:00Z" });
});

test("add and remove persist in the howlet_price_alerts_v1 key", () => {
  addPriceAlert("tsla", "<", 200);
  const [x] = getAlerts();
  expect(x).toMatchObject({ sym: "TSLA", op: "<", px: 200, fired: null });
  expect(JSON.parse(localStorage.getItem("howlet_price_alerts_v1")!)).toHaveLength(1);
  removeAlert(x.id);
  expect(getAlerts()).toEqual([]);
});
