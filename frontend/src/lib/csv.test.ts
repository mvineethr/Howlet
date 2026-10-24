import { toCsv } from "./csv";

test("quotes commas, quotes and newlines; nulls are empty", () => {
  const csv = toCsv(["a", "b"], [["x,y", 'say "hi"'], [null, 3], ["line\nbreak", undefined]]);
  expect(csv).toBe('a,b\r\n"x,y","say ""hi"""\r\n,3\r\n"line\nbreak",');
});
