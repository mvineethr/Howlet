import { toCsv } from "./csv";

test("quotes commas, quotes and newlines; nulls are empty", () => {
  const csv = toCsv(["a", "b"], [["x,y", 'say "hi"'], [null, 3], ["line\nbreak", undefined]]);
  expect(csv).toBe('a,b\r\n"x,y","say ""hi"""\r\n,3\r\n"line\nbreak",');
});

test("string cells starting with a formula char get a quote prefix; numbers untouched", () => {
  expect(toCsv(["a", "b"], [["=1+1", -5.2]])).toBe("a,b\r\n'=1+1,-5.2");
});
