const MONEY_SCALAR_KEYS = [
  "term_premium",
  "policy_fee",
  "total_premium",
  "limit_of_insurance",
] as const;

export type MoneyScalarKey = (typeof MONEY_SCALAR_KEYS)[number];

export function isMoneyScalarKey(key: string): key is MoneyScalarKey {
  return (MONEY_SCALAR_KEYS as readonly string[]).includes(key);
}

export function formatMoney(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function parseMoneyAmount(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value !== "string") {
    return null;
  }
  const text = value.trim();
  if (text === "") {
    return null;
  }
  const stripped = text.replace(/^(?:US\$|USD|\$)\s*/i, "").replace(/,/g, "");
  if (stripped === "") {
    return null;
  }
  const amount = Number(stripped);
  return Number.isFinite(amount) ? amount : null;
}

export function formatMoneyField(value: unknown): string {
  if (value == null) {
    return "";
  }
  if (typeof value === "string" && value.trim() === "") {
    return "";
  }
  const amount = parseMoneyAmount(value);
  if (amount === null) {
    return typeof value === "string" ? value : "";
  }
  return formatMoney(amount);
}

export function canonicalMoneyString(value: unknown): string | null {
  if (value == null) {
    return null;
  }
  const amount = parseMoneyAmount(value);
  if (amount === null) {
    return typeof value === "string" && value.trim() !== ""
      ? value.trim()
      : null;
  }
  if (Number.isInteger(amount)) {
    return String(amount);
  }
  return amount.toLocaleString("en-US", {
    useGrouping: false,
    maximumFractionDigits: 2,
  });
}

export function displayMoney(value: string | null | undefined): string {
  if (value == null || value.trim() === "") {
    return "—";
  }
  return formatMoneyField(value);
}
