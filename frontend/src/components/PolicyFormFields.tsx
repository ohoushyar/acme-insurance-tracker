import type {
  Deductible,
  ExtractedPolicy,
  FieldConfidence,
  Location,
} from "../api";
import { isMoneyScalarKey } from "../money";
import { MoneyInput } from "./MoneyInput";

const SCALAR_FIELDS = [
  { key: "policy_number", label: "Policy number", type: "text" },
  { key: "named_insured", label: "Named insured", type: "text" },
  { key: "broker", label: "Broker", type: "text" },
  { key: "effective_date", label: "Effective date", type: "date" },
  { key: "renewal_date", label: "Renewal date", type: "date" },
  { key: "term_premium", label: "Term premium", type: "text" },
  { key: "policy_fee", label: "Policy fee", type: "text" },
  { key: "total_premium", label: "Total premium", type: "text" },
  { key: "limit_of_insurance", label: "Limit of insurance", type: "text" },
  { key: "coverage_type", label: "Coverage type", type: "text" },
] as const;

type ScalarKey = (typeof SCALAR_FIELDS)[number]["key"];

function setScalar(
  draft: ExtractedPolicy,
  key: ScalarKey,
  value: string,
): ExtractedPolicy {
  const next = value === "" ? null : value;
  return {
    ...draft,
    [key]: next,
    confidence: {
      ...draft.confidence,
      [key]: next ? 1 : 0,
    },
  };
}

function setListConfidence(
  draft: ExtractedPolicy,
  key: keyof FieldConfidence,
  patch: Partial<ExtractedPolicy>,
): ExtractedPolicy {
  return {
    ...draft,
    ...patch,
    confidence: { ...draft.confidence, [key]: 1 },
  };
}

function patchDeductible(
  items: Deductible[],
  index: number,
  key: "peril" | "amount",
  value: string,
): Deductible[] {
  return items.map((item, itemIndex) =>
    itemIndex === index
      ? { ...item, [key]: value === "" ? null : value }
      : item,
  );
}

function patchLocation(
  items: Location[],
  index: number,
  key: "label" | "address",
  value: string,
): Location[] {
  return items.map((item, itemIndex) =>
    itemIndex === index
      ? { ...item, [key]: value === "" ? null : value }
      : item,
  );
}

export function PolicyFormFields({
  draft,
  onChange,
}: {
  draft: ExtractedPolicy;
  onChange: (updater: (current: ExtractedPolicy) => ExtractedPolicy) => void;
}) {
  return (
    <>
      {SCALAR_FIELDS.map((field) => (
        <div className="review-field" key={field.key}>
          <label htmlFor={field.key}>{field.label}</label>
          {isMoneyScalarKey(field.key) ? (
            <MoneyInput
              id={field.key}
              name={field.key}
              value={draft[field.key] ?? ""}
              onChange={(value) =>
                onChange((current) => setScalar(current, field.key, value))
              }
            />
          ) : (
            <input
              id={field.key}
              name={field.key}
              type={field.type}
              value={draft[field.key] ?? ""}
              onChange={(event) =>
                onChange((current) =>
                  setScalar(current, field.key, event.target.value),
                )
              }
            />
          )}
        </div>
      ))}

      <fieldset className="review-fieldset">
        <legend>Carriers</legend>
        {draft.carriers.map((carrier, index) => (
          <div className="review-row" key={`carrier-${index}`}>
            <label htmlFor={`carrier-${index}`}>Carrier</label>
            <input
              id={`carrier-${index}`}
              value={carrier}
              onChange={(event) => {
                const value = event.target.value;
                onChange((current) =>
                  setListConfidence(current, "carriers", {
                    carriers: current.carriers.map((item, itemIndex) =>
                      itemIndex === index ? value : item,
                    ),
                  }),
                );
              }}
            />
            <button
              className="btn-quiet"
              type="button"
              aria-label={`Remove carrier ${carrier || index + 1}`}
              onClick={() => {
                onChange((current) =>
                  setListConfidence(current, "carriers", {
                    carriers: current.carriers.filter(
                      (_, itemIndex) => itemIndex !== index,
                    ),
                  }),
                );
              }}
            >
              Remove
            </button>
          </div>
        ))}
        <button
          className="btn-light"
          type="button"
          onClick={() =>
            onChange((current) =>
              setListConfidence(current, "carriers", {
                carriers: [...current.carriers, ""],
              }),
            )
          }
        >
          Add carrier
        </button>
      </fieldset>

      <fieldset className="review-fieldset">
        <legend>Deductibles by peril</legend>
        {draft.deductibles.map((item, index) => (
          <div className="review-row" key={`deductible-${index}`}>
            <label htmlFor={`deductible-peril-${index}`}>Peril</label>
            <input
              id={`deductible-peril-${index}`}
              value={item.peril ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                onChange((current) =>
                  setListConfidence(current, "deductibles", {
                    deductibles: patchDeductible(
                      current.deductibles,
                      index,
                      "peril",
                      value,
                    ),
                  }),
                );
              }}
            />
            <label htmlFor={`deductible-amount-${index}`}>Amount</label>
            <input
              id={`deductible-amount-${index}`}
              value={item.amount ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                onChange((current) =>
                  setListConfidence(current, "deductibles", {
                    deductibles: patchDeductible(
                      current.deductibles,
                      index,
                      "amount",
                      value,
                    ),
                  }),
                );
              }}
            />
            <button
              className="btn-quiet"
              type="button"
              aria-label={`Remove deductible ${item.peril ?? "row"}`}
              onClick={() => {
                onChange((current) =>
                  setListConfidence(current, "deductibles", {
                    deductibles: current.deductibles.filter(
                      (_, itemIndex) => itemIndex !== index,
                    ),
                  }),
                );
              }}
            >
              Remove
            </button>
          </div>
        ))}
        <button
          className="btn-light"
          type="button"
          onClick={() =>
            onChange((current) =>
              setListConfidence(current, "deductibles", {
                deductibles: [
                  ...current.deductibles,
                  { peril: null, amount: null },
                ],
              }),
            )
          }
        >
          Add deductible
        </button>
      </fieldset>

      <fieldset className="review-fieldset">
        <legend>Locations</legend>
        {draft.locations.map((item, index) => (
          <div className="review-row" key={`location-${index}`}>
            <label htmlFor={`location-label-${index}`}>Label</label>
            <input
              id={`location-label-${index}`}
              value={item.label ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                onChange((current) =>
                  setListConfidence(current, "locations", {
                    locations: patchLocation(
                      current.locations,
                      index,
                      "label",
                      value,
                    ),
                  }),
                );
              }}
            />
            <label htmlFor={`location-address-${index}`}>Address</label>
            <input
              id={`location-address-${index}`}
              value={item.address ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                onChange((current) =>
                  setListConfidence(current, "locations", {
                    locations: patchLocation(
                      current.locations,
                      index,
                      "address",
                      value,
                    ),
                  }),
                );
              }}
            />
            <button
              className="btn-quiet"
              type="button"
              aria-label={`Remove location ${item.label ?? "row"}`}
              onClick={() => {
                onChange((current) =>
                  setListConfidence(current, "locations", {
                    locations: current.locations.filter(
                      (_, itemIndex) => itemIndex !== index,
                    ),
                  }),
                );
              }}
            >
              Remove
            </button>
          </div>
        ))}
        <button
          className="btn-light"
          type="button"
          onClick={() =>
            onChange((current) =>
              setListConfidence(current, "locations", {
                locations: [
                  ...current.locations,
                  { label: null, address: null },
                ],
              }),
            )
          }
        >
          Add location
        </button>
      </fieldset>
    </>
  );
}
