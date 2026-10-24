import { renderHook, waitFor, act } from "@testing-library/react";
import { ApiError, getJson } from "./api";
import { useApi } from "./useApi";

afterEach(() => vi.restoreAllMocks());

test("getJson surfaces the server's JSON error text", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ error: "Upstream request failed: boom" }), { status: 502 }),
  );
  await expect(getJson("/api/x")).rejects.toMatchObject({ status: 502, message: "Upstream request failed: boom" });
  await expect(getJson("/api/x")).rejects.toBeInstanceOf(ApiError);
});

test("useApi keeps last good data when a refresh fails", async () => {
  let n = 0;
  const fetcher = () => (++n === 1 ? Promise.resolve(42) : Promise.reject(new Error("down")));
  const { result } = renderHook(() => useApi("k", fetcher));
  await waitFor(() => expect(result.current.data).toBe(42));
  act(() => result.current.reload());
  await waitFor(() => expect(result.current.error?.message).toBe("down"));
  expect(result.current.data).toBe(42);
});

test("useApi with a null key does not fetch", () => {
  const fetcher = vi.fn(() => Promise.resolve(1));
  renderHook(() => useApi(null, fetcher));
  expect(fetcher).not.toHaveBeenCalled();
});
