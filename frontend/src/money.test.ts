import { describe, expect, it } from "vitest";
import {
  canonicalMoneyString,
  displayMoney,
  formatMoney,
  formatMoneyField,
  parseMoneyAmount,
} from "./money";

describe("money formatting", () => {
  it("formats whole-dollar amounts as USD currency", () => {
    expect(formatMoney(4800000)).toBe("$4,800,000");
    expect(formatMoney(25000000)).toBe("$25,000,000");
  });

  it("parses scientific notation, currency strings, and plain numbers", () => {
    expect(parseMoneyAmount("4.80E+6")).toBe(4800000);
    expect(parseMoneyAmount("4.80e+6")).toBe(4800000);
    expect(parseMoneyAmount("$4,800,000")).toBe(4800000);
    expect(parseMoneyAmount("25000000.00")).toBe(25000000);
    expect(parseMoneyAmount(15612455)).toBe(15612455);
    expect(parseMoneyAmount("")).toBeNull();
    expect(parseMoneyAmount("approx 25M")).toBeNull();
  });

  it("shows scientific notation as currency", () => {
    expect(formatMoneyField("4.80E+6")).toBe("$4,800,000");
    expect(formatMoneyField("25000000.00")).toBe("$25,000,000");
    expect(displayMoney("4.80E+6")).toBe("$4,800,000");
    expect(displayMoney(null)).toBe("—");
  });

  it("canonicalizes scientific notation to a plain decimal string", () => {
    expect(canonicalMoneyString("4.80E+6")).toBe("4800000");
    expect(canonicalMoneyString("25000000.00")).toBe("25000000");
    expect(canonicalMoneyString("")).toBeNull();
  });
});
