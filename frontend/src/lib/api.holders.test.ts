import { api, clearHoldersMemo } from "./api";

afterEach(() => { vi.restoreAllMocks(); clearHoldersMemo(); });
const body = { symbol: "AAPL", tracked_managers: [], holders: [] };

test("concurrent and repeat calls share one request", async () => {
  const f = vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(new Response(JSON.stringify(body))));
  const [a, b] = await Promise.all([api.holders("AAPL"), api.holders("aapl")]);
  await api.holders("AAPL");
  expect(a).toEqual(body);
  expect(b).toBe(a);
  expect(f).toHaveBeenCalledTimes(1);
});

test("a failure is not memoised", async () => {
  const f = vi.spyOn(globalThis, "fetch")
    .mockImplementationOnce(() => Promise.resolve(new Response("{}", { status: 502 })))
    .mockImplementation(() => Promise.resolve(new Response(JSON.stringify(body))));
  await expect(api.holders("MSFT")).rejects.toBeTruthy();
  await expect(api.holders("MSFT")).resolves.toEqual(body);
  expect(f).toHaveBeenCalledTimes(2);
});
