import type {
  Deductible,
  ExtractedPolicy,
  FieldConfidence,
  Location,
} from "./api";

const ZERO_CONFIDENCE: FieldConfidence = {
  policy_number: 0,
  named_insured: 0,
  broker: 0,
  effective_date: 0,
  renewal_date: 0,
  term_premium: 0,
  policy_fee: 0,
  total_premium: 0,
  limit_of_insurance: 0,
  coverage_type: 0,
  carriers: 0,
  deductibles: 0,
  locations: 0,
};

function textOrNull(value: unknown): string | null {
  if (value == null) {
    return null;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value !== "string") {
    return null;
  }
  return value.trim() === "" ? null : value;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function normalizeDeductible(value: unknown): Deductible {
  const row = asRecord(value);
  if (!row) {
    return { peril: null, amount: null };
  }
  return {
    peril: textOrNull(row.peril),
    amount: textOrNull(row.amount),
  };
}

function normalizeLocation(value: unknown): Location {
  const row = asRecord(value);
  if (!row) {
    return { label: null, address: null };
  }
  return {
    label: textOrNull(row.label),
    address: textOrNull(row.address),
  };
}

function normalizeConfidence(value: unknown): FieldConfidence {
  const row = asRecord(value) ?? {};
  const confidence = { ...ZERO_CONFIDENCE };
  for (const key of Object.keys(ZERO_CONFIDENCE) as (keyof FieldConfidence)[]) {
    const score = row[key];
    if (typeof score === "number" && Number.isFinite(score)) {
      confidence[key] = score;
    }
  }
  return confidence;
}

export function normalizeExtracted(raw: unknown): ExtractedPolicy {
  const src = asRecord(raw) ?? {};
  return {
    policy_number: textOrNull(src.policy_number),
    named_insured: textOrNull(src.named_insured),
    broker: textOrNull(src.broker),
    effective_date: textOrNull(src.effective_date),
    renewal_date: textOrNull(src.renewal_date),
    term_premium: textOrNull(src.term_premium),
    policy_fee: textOrNull(src.policy_fee),
    total_premium: textOrNull(src.total_premium),
    limit_of_insurance: textOrNull(src.limit_of_insurance),
    coverage_type: textOrNull(src.coverage_type),
    carriers: Array.isArray(src.carriers)
      ? src.carriers.filter((item): item is string => typeof item === "string")
      : [],
    deductibles: Array.isArray(src.deductibles)
      ? src.deductibles.map(normalizeDeductible)
      : [],
    locations: Array.isArray(src.locations)
      ? src.locations.map(normalizeLocation)
      : [],
    confidence: normalizeConfidence(src.confidence),
  };
}
