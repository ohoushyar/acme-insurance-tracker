import { describe, expect, it } from "vitest";
import { normalizeExtracted } from "./extracted";

describe("normalizeExtracted money fields", () => {
  it("converts scientific notation to a plain decimal string", () => {
    const result = normalizeExtracted({
      limit_of_insurance: "4.80E+6",
      term_premium: "1.85E+5",
    });
    expect(result.limit_of_insurance).toBe("4800000");
    expect(result.term_premium).toBe("185000");
  });

  it("keeps ordinary money strings unchanged", () => {
    const result = normalizeExtracted({
      limit_of_insurance: "25000000.00",
      total_premium: "186500.00",
    });
    expect(result.limit_of_insurance).toBe("25000000.00");
    expect(result.total_premium).toBe("186500.00");
  });
});
