import { useState } from "react";
import { canonicalMoneyString, formatMoneyField } from "../money";

export function MoneyInput({
  id,
  name,
  value,
  onChange,
}: {
  id: string;
  name?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const [focused, setFocused] = useState(false);
  const display = focused || value === "" ? value : formatMoneyField(value);

  return (
    <input
      id={id}
      name={name}
      type="text"
      inputMode="decimal"
      value={display}
      onFocus={() => setFocused(true)}
      onBlur={() => {
        setFocused(false);
        const parsed = canonicalMoneyString(value);
        if (parsed !== value) {
          onChange(parsed ?? "");
        }
      }}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
