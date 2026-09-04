import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ApiError,
  deletePolicy,
  getPolicy,
  getPolicyHistory,
  linkPolicy,
  listPolicies,
  listProperties,
  unlinkPolicy,
  type FieldConfidence,
  type Policy,
  type PolicyHistoryPoint,
  type Property,
} from "../api";
import { useAuth } from "../auth";
import { ConfirmDelete } from "../components/ConfirmDelete";
import { Shell } from "../components/Shell";
import { displayMoney } from "../money";

function display(value: string | null | undefined): string {
  return value && value.trim() !== "" ? value : "—";
}

function confidencePct(
  confidence: FieldConfidence,
  key: keyof FieldConfidence,
): string {
  const raw = confidence[key];
  if (typeof raw !== "number" || Number.isNaN(raw)) {
    return "—";
  }
  return `${Math.round(raw * 100)}%`;
}

function DetailLine({
  label,
  value,
  confidence,
  tone,
}: {
  label: string;
  value: string;
  confidence?: string;
  tone?: "urgent" | "default";
}) {
  return (
    <div className="detail-line">
      <span className="detail-label">
        {label}
        {confidence ? (
          <span className="detail-confidence"> {confidence}</span>
        ) : null}
      </span>
      <span
        className={
          tone === "urgent"
            ? "detail-value detail-value-urgent"
            : "detail-value"
        }
      >
        {value}
      </span>
    </div>
  );
}

export function PolicyDetail() {
  const { user, loading, logout } = useAuth();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [history, setHistory] = useState<PolicyHistoryPoint[]>([]);
  const [peers, setPeers] = useState<Policy[]>([]);
  const [peerId, setPeerId] = useState("");
  const [loadError, setLoadError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [linkError, setLinkError] = useState("");
  const [confirming, setConfirming] = useState(false);

  async function refresh(policyId: string): Promise<void> {
    const [loaded, hist, listed] = await Promise.all([
      getPolicy(policyId),
      getPolicyHistory(policyId),
      listPolicies(),
    ]);
    setPolicy(loaded);
    setHistory(hist.items);
    setPeers(listed.items.filter((item) => item.id !== policyId));
    const suggestion = loaded.link_suggestions?.[0]?.policy_id ?? "";
    setPeerId(suggestion);
  }

  useEffect(() => {
    if (!user || !id) {
      return;
    }
    let cancelled = false;
    void Promise.all([getPolicy(id), getPolicyHistory(id), listPolicies()])
      .then(([loaded, hist, listed]) => {
        if (cancelled) {
          return;
        }
        setPolicy(loaded);
        setHistory(hist.items);
        setPeers(listed.items.filter((item) => item.id !== id));
        setPeerId(loaded.link_suggestions?.[0]?.policy_id ?? "");
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError ? err.message : "Unable to load policy.",
          );
        }
      });
    void listProperties()
      .then((listed) => {
        if (!cancelled) {
          setProperties(listed.items);
        }
      })
      .catch(() => {
        // Attached labels are best-effort; detail still renders policy fields.
      });
    return () => {
      cancelled = true;
    };
  }, [id, user]);

  async function onConfirmDelete(): Promise<void> {
    if (!policy) {
      return;
    }
    setDeleteError("");
    try {
      await deletePolicy(policy.id);
      navigate("/");
    } catch (err) {
      setDeleteError(
        err instanceof ApiError ? err.message : "Unable to delete policy.",
      );
    }
  }

  async function onLink(): Promise<void> {
    if (!policy || !peerId) {
      return;
    }
    setLinkError("");
    try {
      await linkPolicy(policy.id, peerId);
      await refresh(policy.id);
    } catch (err) {
      setLinkError(
        err instanceof ApiError ? err.message : "Unable to link policies.",
      );
    }
  }

  async function onUnlink(): Promise<void> {
    if (!policy) {
      return;
    }
    setLinkError("");
    try {
      await unlinkPolicy(policy.id);
      await refresh(policy.id);
    } catch (err) {
      setLinkError(
        err instanceof ApiError ? err.message : "Unable to unlink policy.",
      );
    }
  }

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
        <Link to="/">Back to portfolio</Link>
      </Shell>
    );
  }

  if (!policy) {
    return (
      <Shell onLogout={logout}>
        <p className="muted">Loading…</p>
      </Shell>
    );
  }

  const title =
    policy.named_insured || policy.policy_number || "Untitled policy";
  const attached = (policy.property_ids ?? [])
    .map((propertyId) =>
      properties.find((property) => property.id === propertyId),
    )
    .filter((property): property is Property => Boolean(property));
  const confidence = policy.confidence;
  const chartData = history.map((point) => ({
    year: point.year,
    premium: point.premium == null ? null : Number(point.premium),
  }));
  const suggestionIds = new Set(
    (policy.link_suggestions ?? []).map((item) => item.policy_id),
  );
  const orderedPeers = [
    ...peers.filter((item) => suggestionIds.has(item.id)),
    ...peers.filter((item) => !suggestionIds.has(item.id)),
  ];

  return (
    <Shell onLogout={logout}>
      <p className="eyebrow">
        {policy.coverage_type
          ? `${policy.coverage_type} insurance`
          : "Policy detail"}
      </p>
      <h1>{title}</h1>

      <section aria-label="Policy fields" className="detail-panel">
        <DetailLine
          label="Policy number"
          value={display(policy.policy_number)}
          confidence={confidencePct(confidence, "policy_number")}
        />
        <DetailLine
          label="Named insured"
          value={display(policy.named_insured)}
          confidence={confidencePct(confidence, "named_insured")}
        />
        <DetailLine
          label="Broker"
          value={display(policy.broker)}
          confidence={confidencePct(confidence, "broker")}
        />
        <DetailLine
          label="Effective date"
          value={display(policy.effective_date)}
          confidence={confidencePct(confidence, "effective_date")}
        />
        <DetailLine
          label="Renewal date"
          value={display(policy.renewal_date)}
          confidence={confidencePct(confidence, "renewal_date")}
        />
        <DetailLine
          label="Term premium"
          value={displayMoney(policy.term_premium)}
          confidence={confidencePct(confidence, "term_premium")}
        />
        <DetailLine
          label="Policy fee"
          value={displayMoney(policy.policy_fee)}
          confidence={confidencePct(confidence, "policy_fee")}
        />
        <DetailLine
          label="Total premium"
          value={displayMoney(policy.total_premium)}
          confidence={confidencePct(confidence, "total_premium")}
        />
        <DetailLine
          label="Last year's premium"
          value={displayMoney(policy.previous_premium)}
        />
        <DetailLine
          label="Year-over-year change"
          value={
            typeof policy.yoy_change_pct === "number"
              ? `${policy.yoy_change_pct > 0 ? "+" : ""}${policy.yoy_change_pct.toFixed(1)}%`
              : "—"
          }
          tone={policy.yoy_flagged ? "urgent" : "default"}
        />
        <DetailLine
          label="Limit of insurance"
          value={displayMoney(policy.limit_of_insurance)}
          confidence={confidencePct(confidence, "limit_of_insurance")}
        />
        <DetailLine
          label="Coverage type"
          value={display(policy.coverage_type)}
          confidence={confidencePct(confidence, "coverage_type")}
        />
      </section>

      {chartData.length >= 2 ? (
        <section aria-label="Premium history" className="detail-section">
          <h2>Premium history</h2>
          <div className="trend-chart">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="#E4E1D8" strokeDasharray="3 3" />
                <XAxis dataKey="year" stroke="#5B6472" />
                <YAxis
                  stroke="#5B6472"
                  tickFormatter={(value) => `$${value}`}
                />
                <Tooltip formatter={(value) => [`$${value}`, "Premium"]} />
                <Line
                  type="monotone"
                  dataKey="premium"
                  stroke="#1C2430"
                  strokeWidth={2}
                  dot
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}

      <section aria-label="Carriers" className="detail-section">
        <h2>
          Carriers{" "}
          <span className="detail-confidence">
            {confidencePct(confidence, "carriers")}
          </span>
        </h2>
        {policy.carriers.length === 0 ? (
          <p className="muted">—</p>
        ) : (
          <ul className="detail-list">
            {policy.carriers.map((carrier) => (
              <li key={carrier}>{carrier}</li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Deductibles" className="detail-section">
        <h2>
          Deductibles{" "}
          <span className="detail-confidence">
            {confidencePct(confidence, "deductibles")}
          </span>
        </h2>
        {policy.deductibles.length === 0 ? (
          <p className="muted">—</p>
        ) : (
          policy.deductibles.map((item, index) => (
            <DetailLine
              key={`${item.peril ?? "peril"}-${index}`}
              label={display(item.peril)}
              value={display(item.amount)}
            />
          ))
        )}
      </section>

      <section aria-label="Locations" className="detail-section">
        <h2>
          Locations{" "}
          <span className="detail-confidence">
            {confidencePct(confidence, "locations")}
          </span>
        </h2>
        {policy.locations.length === 0 ? (
          <p className="muted">—</p>
        ) : (
          policy.locations.map((location, index) => (
            <DetailLine
              key={`${location.label ?? "location"}-${index}`}
              label={display(location.label)}
              value={display(location.address)}
            />
          ))
        )}
      </section>

      <section aria-label="Attached properties" className="detail-section">
        <h2>Attached properties</h2>
        {attached.length === 0 ? (
          <p className="muted">None attached</p>
        ) : (
          <ul className="detail-list">
            {attached.map((property) => (
              <li key={property.id}>{property.label}</li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Link prior year" className="detail-section">
        <h2>Multi-year link</h2>
        {policy.series_id ? (
          <p className="muted">Linked in a premium series.</p>
        ) : (
          <p className="muted">
            Link to a prior-year policy to unlock YoY change and trends.
          </p>
        )}
        {linkError ? <p className="error">{linkError}</p> : null}
        <div className="link-controls">
          <label>
            Prior policy
            <select
              aria-label="Prior policy"
              value={peerId}
              onChange={(event) => setPeerId(event.target.value)}
            >
              <option value="">Select a policy…</option>
              {orderedPeers.map((item) => (
                <option key={item.id} value={item.id}>
                  {(suggestionIds.has(item.id) ? "Suggested: " : "") +
                    (item.named_insured ||
                      item.policy_number ||
                      "Untitled policy")}
                </option>
              ))}
            </select>
          </label>
          <div className="card-actions">
            <button
              type="button"
              className="btn-quiet"
              disabled={!peerId}
              onClick={() => void onLink()}
            >
              Link prior year
            </button>
            {policy.series_id ? (
              <button
                type="button"
                className="btn-quiet"
                onClick={() => void onUnlink()}
              >
                Unlink from series
              </button>
            ) : null}
          </div>
        </div>
      </section>

      {policy.source_document_id ? (
        <p>
          <Link to={`/documents/${policy.source_document_id}/review`}>
            Source document
          </Link>
        </p>
      ) : null}

      {deleteError ? <p className="error">{deleteError}</p> : null}
      {confirming ? (
        <ConfirmDelete
          label={title}
          warning={`Delete ${title}? The uploaded document will be kept.`}
          onConfirm={() => void onConfirmDelete()}
          onCancel={() => setConfirming(false)}
        />
      ) : (
        <div className="card-actions">
          <Link to={`/policies/${policy.id}/edit`} aria-label={`Edit ${title}`}>
            Edit
          </Link>
          <button
            className="btn-quiet"
            type="button"
            aria-label={`Delete ${title}`}
            onClick={() => setConfirming(true)}
          >
            Delete
          </button>
          <Link to="/">Back to portfolio</Link>
        </div>
      )}
    </Shell>
  );
}
