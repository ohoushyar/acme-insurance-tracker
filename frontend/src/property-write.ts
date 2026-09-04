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
  return {
    label: trimmedLabel,
    address: emptyToNull(address),
    stated_value: emptyToNull(statedValue),
  };
}
