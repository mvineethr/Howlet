import { buildScreenerQuery } from "./screener";

const empty = { peMax: "", mcapMinB: "", growthMin: "", marginMin: "" };

test("blank fields are omitted; market cap is in billions", () => {
  expect(buildScreenerQuery(empty)).toEqual({ qs: "" });
  expect(buildScreenerQuery({ ...empty, peMax: " 15 ", mcapMinB: "2.5" }))
    .toEqual({ qs: "pe_ratio_max=15&market_cap_min=2500000000" });
  expect(buildScreenerQuery({ peMax: "20", mcapMinB: "", growthMin: "-5", marginMin: "10" }))
    .toEqual({ qs: "pe_ratio_max=20&revenue_growth_pct_min=-5&net_margin_pct_min=10" });
});

test("non-numeric input names the bad field", () => {
  expect(buildScreenerQuery({ ...empty, growthMin: "abc" })).toEqual({ error: "growthMin" });
  expect(buildScreenerQuery({ ...empty, peMax: "1e999" })).toEqual({ error: "peMax" });
});
