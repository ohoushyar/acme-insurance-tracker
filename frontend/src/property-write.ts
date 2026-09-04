import { canonicalMoneyString } from "./money";

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export function propertyWriteBody(
  label: string,
  address: string,
  statedValue: string,
): {
  label: string;
  address: string | null;
  stated_value: string | null;
} | null {
  const trimmedLabel = label.trim();
  if (!trimmedLabel) {
    return null;
  }
  const stated = emptyToNull(statedValue);
  return {
    label: trimmedLabel,
    address: emptyToNull(address),
    stated_value:
      stated === null ? null : (canonicalMoneyString(stated) ?? stated),
  };
}
