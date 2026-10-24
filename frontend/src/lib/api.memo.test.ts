import { api, clearApiMemo } from "./api";

afterEach(() => { vi.restoreAllMocks(); clearApiMemo(); });

test("concurrent macro calls make one fetch", async () => {
  const f = vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(new Response("{}")));
  await Promise.all([api.macro(), api.macro()]);
  expect(f).toHaveBeenCalledTimes(1);
});

test("a rejected portfolio call is retried", async () => {
  const f = vi.spyOn(globalThis, "fetch")
    .mockImplementationOnce(() => Promise.resolve(new Response("{}", { status: 502 })))
    .mockImplementation(() => Promise.resolve(new Response('{"cik":"1"}')));
  await expect(api.portfolio("Buffett")).rejects.toBeTruthy();
  await expect(api.portfolio("buffett")).resolves.toEqual({ cik: "1" });
  expect(f).toHaveBeenCalledTimes(2);
});
