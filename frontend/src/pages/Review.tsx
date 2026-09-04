import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  confirmDocument,
  getDocument,
  type Deductible,
  type DocumentJob,
  type ExtractedPolicy,
  type FieldConfidence,
  type Location,
} from "../api";
import { useAuth } from "../auth";
import { Shell } from "../components/Shell";
import { normalizeExtracted } from "../extracted";

const LOW_CONFIDENCE = 0.7;

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

function formatConfidence(value: number | undefined): string {
  if (value === undefined) {
    return "";
  }
  return `${Math.round(value * 100)}%`;
}

function isLowConfidence(value: number | undefined): boolean {
  return (value ?? 0) < LOW_CONFIDENCE;
}

function ConfidenceBadge({ value }: { value: number | undefined }) {
  const label = formatConfidence(value);
  if (!label) {
    return null;
  }
  return (
    <span
      className={
        isLowConfidence(value) ? "confidence confidence-low" : "confidence"
      }
    >
      {label}
    </span>
  );
}

function needsAttention(draft: ExtractedPolicy): boolean {
  const missingScalar = SCALAR_FIELDS.some(
    (field) => draft[field.key] == null || draft[field.key] === "",
  );
  if (missingScalar) {
    return true;
  }
  return Object.values(draft.confidence).some((value) =>
    isLowConfidence(value),
  );
}

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

export function Review() {
  const { user, loading, logout } = useAuth();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<DocumentJob | null>(null);
  const [draft, setDraft] = useState<ExtractedPolicy | null>(null);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function updateDraft(
    updater: (current: ExtractedPolicy) => ExtractedPolicy,
  ): void {
    setDraft((current) => (current ? updater(current) : current));
  }

  useEffect(() => {
    if (!user || !id) {
      return;
    }
    let cancelled = false;
    void getDocument(id)
      .then((document) => {
        if (cancelled) {
          return;
        }
        setJob(document);
        if (document.extracted != null) {
          setDraft(normalizeExtracted(document.extracted));
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError ? err.message : "Unable to load document.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id, user]);

  if (loading) {
    return (
      <Shell>
        <p className="muted">Loading…</p>
      </Shell>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (loadError) {
    return (
      <Shell onLogout={logout}>
        <p className="error">{loadError}</p>
        <Link to="/uploads">Back to uploads</Link>
      </Shell>
    );
  }

  if (!job || !id) {
    return (
      <Shell onLogout={logout}>
        <p className="muted">Loading…</p>
      </Shell>
    );
  }

  const canEdit =
    (job.status === "completed" || job.status === "reviewed") && draft;

  if (!canEdit || !draft) {
    return (
      <Shell onLogout={logout}>
        <h1>Review extracted fields</h1>
        <p className="muted">
          This document is {job.status}. Extraction has to finish before you can
          confirm fields.
        </p>
        <Link to="/uploads">Back to uploads</Link>
      </Shell>
    );
  }

  async function onConfirm(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!id || !draft) {
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await confirmDocument(id, draft);
      navigate("/");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to confirm extraction.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Shell onLogout={logout}>
      <h1>Review extracted fields</h1>
      <p className="review-filename">{job.original_filename}</p>
      <p className="lede">
        These fields were extracted automatically from the uploaded document.
        Confirm they look right before adding them to your portfolio.
      </p>
      <p>
        <a
          href={`/api/v1/documents/${id}/file`}
          target="_blank"
          rel="noreferrer"
        >
          View original PDF
        </a>
      </p>
      {needsAttention(draft) ? (
        <p className="warning" role="status">
          Some fields are missing or low confidence. You can still confirm.
        </p>
      ) : null}
      <form className="review-form" onSubmit={(event) => void onConfirm(event)}>
        {SCALAR_FIELDS.map((field) => (
          <div className="review-field" key={field.key}>
            <label htmlFor={field.key}>
              {field.label}
              <ConfidenceBadge value={draft.confidence[field.key]} />
            </label>
            <input
              id={field.key}
              name={field.key}
              type={field.type}
              value={draft[field.key] ?? ""}
              onChange={(event) =>
                updateDraft((current) =>
                  setScalar(current, field.key, event.target.value),
                )
              }
            />
          </div>
        ))}

        <fieldset className="review-fieldset">
          <legend>
            Carriers
            <ConfidenceBadge value={draft.confidence.carriers} />
          </legend>
          {draft.carriers.map((carrier, index) => (
            <div className="review-row" key={`carrier-${index}`}>
              <label htmlFor={`carrier-${index}`}>Carrier</label>
              <input
                id={`carrier-${index}`}
                value={carrier}
                onChange={(event) => {
                  const value = event.target.value;
                  updateDraft((current) =>
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
                  updateDraft((current) =>
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
              updateDraft((current) =>
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
          <legend>
            Deductibles by peril
            <ConfidenceBadge value={draft.confidence.deductibles} />
          </legend>
          {draft.deductibles.map((item, index) => (
            <div className="review-row" key={`deductible-${index}`}>
              <label htmlFor={`deductible-peril-${index}`}>Peril</label>
              <input
                id={`deductible-peril-${index}`}
                value={item.peril ?? ""}
                onChange={(event) => {
                  const value = event.target.value;
                  updateDraft((current) =>
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
                  updateDraft((current) =>
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
                  updateDraft((current) =>
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
              updateDraft((current) =>
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
          <legend>
            Locations
            <ConfidenceBadge value={draft.confidence.locations} />
          </legend>
          {draft.locations.map((item, index) => (
            <div className="review-row" key={`location-${index}`}>
              <label htmlFor={`location-label-${index}`}>Label</label>
              <input
                id={`location-label-${index}`}
                value={item.label ?? ""}
                onChange={(event) => {
                  const value = event.target.value;
                  updateDraft((current) =>
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
                  updateDraft((current) =>
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
                  updateDraft((current) =>
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
              updateDraft((current) =>
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

        {error ? <p className="error">{error}</p> : null}
        <div className="review-actions">
          <button
            className="btn-light"
            type="button"
            onClick={() => navigate("/uploads")}
          >
            Cancel
          </button>
          <button className="btn-dark" type="submit" disabled={submitting}>
            Looks right — confirm
          </button>
        </div>
      </form>
    </Shell>
  );
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
