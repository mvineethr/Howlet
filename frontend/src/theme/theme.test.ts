import { brandRamp, AMBER } from "./tokens";
import { buildTheme, resolveMode, applyCssVars } from "./theme";

const lightness = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return (Math.max(r, g, b) + Math.min(r, g, b)) / 2;
};

test("brandRamp has 16 shades, dark to light", () => {
  const ramp = brandRamp(AMBER);
  const keys = Object.keys(ramp).map(Number);
  expect(keys).toEqual([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160]);
  const ls = keys.map((k) => lightness((ramp as Record<number, string>)[k]));
  for (let i = 1; i < ls.length; i++) expect(ls[i]).toBeGreaterThan(ls[i - 1]);
});

test("resolveMode follows Windows only in system mode", () => {
  expect(resolveMode("system", true)).toBe("dark");
  expect(resolveMode("system", false)).toBe("light");
  expect(resolveMode("light", true)).toBe("light");
  expect(resolveMode("dark", false)).toBe("dark");
});

test("buildTheme uses Segoe UI and brand-coloured foreground in dark", () => {
  const t = buildTheme(true, AMBER);
  expect(t.fontFamilyBase).toContain("Segoe UI");
  expect(t.fontFamilyMonospace).toContain("Cascadia Mono");
  expect(t.colorBrandForeground1).toBe(brandRamp(AMBER)[110]);
});

test("applyCssVars writes tokens onto :root", () => {
  applyCssVars(true, AMBER);
  const s = document.documentElement.style;
  expect(s.getPropertyValue("--accent")).toBe(AMBER);
  expect(s.getPropertyValue("--up")).not.toBe("");
});
