import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import {
  ApiError,
  deletePolicy,
  listPolicies,
  listProperties,
  type Policy,
  type Property,
} from "../api";
import { useAuth } from "../auth";
import { ConfirmDelete } from "../components/ConfirmDelete";
import { Shell } from "../components/Shell";
import {
  URGENCY_LABELS,
  URGENCY_ORDER,
  daysUntil,
  formatMoney,
  groupPolicies,
  portfolioStats,
  type UrgencyKey,
} from "../urgency";

function locationLabels(policy: Policy): string[] {
  return (policy.locations ?? [])
    .map((location) => location.label)
    .filter((label): label is string => Boolean(label));
}

function attachedLabels(policy: Policy, properties: Property[]): string[] {
  return (policy.property_ids ?? [])
    .map((id) => properties.find((property) => property.id === id)?.label)
    .filter((label): label is string => Boolean(label));
}

function PolicyCard({
  policy,
  properties,
  onDeleted,
  today,
}: {
  policy: Policy;
  properties: Property[];
  onDeleted: (id: string) => void;
  today: Date;
}) {
  const [confirming, setConfirming] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const title =
    policy.named_insured || policy.policy_number || "Untitled policy";
  const places = [
    ...attachedLabels(policy, properties),
    ...locationLabels(policy),
  ];
  const days = daysUntil(policy.renewal_date, today);

  async function onConfirmDelete(): Promise<void> {
    setDeleteError("");
    try {
      await deletePolicy(policy.id);
      onDeleted(policy.id);
    } catch (err) {
      setDeleteError(
        err instanceof ApiError ? err.message : "Unable to delete policy.",
      );
    }
  }

  return (
    <article className="job-card">
      <header className="job-card-header">
        <h3>{title}</h3>
        {policy.coverage_type ? (
          <p className="job-status">{policy.coverage_type}</p>
        ) : null}
      </header>
      <p className="job-summary">
        {policy.policy_number ? <span>{policy.policy_number}</span> : null}
        {policy.policy_number && policy.renewal_date ? " · " : null}
        {policy.renewal_date ? <span>{policy.renewal_date}</span> : null}
        {(policy.policy_number || policy.renewal_date) && policy.total_premium
          ? " · "
          : null}
        {policy.total_premium ? <span>{policy.total_premium}</span> : null}
      </p>
      {days !== null ? (
        <p className="muted">
          {days < 0
            ? `${Math.abs(days)} days past renewal`
            : `${days} days until renewal`}
        </p>
      ) : null}
      {typeof policy.yoy_change_pct === "number" ? (
        <p
          className={
            policy.yoy_flagged ? "yoy-badge yoy-badge-flagged" : "yoy-badge"
          }
        >
          {policy.yoy_change_pct > 0 ? "+" : ""}
          {policy.yoy_change_pct.toFixed(1)}% YoY
        </p>
      ) : null}
      {places.length > 0 ? <p className="muted">{places.join(" · ")}</p> : null}
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
          <Link to={`/policies/${policy.id}`} aria-label={`View ${title}`}>
            View
          </Link>
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
        </div>
      )}
    </article>
  );
}

function StatStrip({
  totalPremium,
  renewingWithin30,
  renewingWithin90,
  premiumUpYoY,
}: {
  totalPremium: number;
  renewingWithin30: number;
  renewingWithin90: number;
  premiumUpYoY: number;
}) {
  return (
    <div className="stat-strip" role="region" aria-label="Portfolio summary">
      <div className="stat">
        <div className="stat-label">Total annual premium</div>
        <div className="stat-value">{formatMoney(totalPremium)}</div>
      </div>
      <div className="stat">
        <div className="stat-label">Renewing within 30 days</div>
        <div
          className={
            renewingWithin30 > 0 ? "stat-value stat-value-urgent" : "stat-value"
          }
        >
          {renewingWithin30}
        </div>
      </div>
      <div className="stat">
        <div className="stat-label">Renewing within 90 days</div>
        <div
          className={
            renewingWithin90 > 0 ? "stat-value stat-value-soon" : "stat-value"
          }
        >
          {renewingWithin90}
        </div>
      </div>
      <div className="stat">
        <div className="stat-label">Premium up 10%+</div>
        <div
          className={
            premiumUpYoY > 0 ? "stat-value stat-value-urgent" : "stat-value"
          }
        >
          {premiumUpYoY}
        </div>
      </div>
    </div>
  );
}

function UrgencySection({
  urgencyKey,
  policies,
  properties,
  today,
  onDeleted,
}: {
  urgencyKey: UrgencyKey;
  policies: Policy[];
  properties: Property[];
  today: Date;
  onDeleted: (id: string) => void;
}) {
  if (policies.length === 0) {
    return null;
  }
  return (
    <section className="urgency-group" aria-label={URGENCY_LABELS[urgencyKey]}>
      <h2 className={`urgency-heading urgency-${urgencyKey}`}>
        {URGENCY_LABELS[urgencyKey]}
      </h2>
      {policies.map((policy) => (
        <PolicyCard
          key={policy.id}
          policy={policy}
          properties={properties}
          today={today}
          onDeleted={onDeleted}
        />
      ))}
    </section>
  );
}

export function Home() {
  const { user, loading, logout } = useAuth();
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [policiesLoaded, setPoliciesLoaded] = useState(false);
  const [policyError, setPolicyError] = useState("");
  const [propertyError, setPropertyError] = useState("");

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;
    void listPolicies()
      .then((saved) => {
        if (!cancelled) {
          setPolicies(saved.items);
          setPoliciesLoaded(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPolicyError("Unable to load saved policies.");
          setPoliciesLoaded(true);
        }
      });
    void listProperties()
      .then((listed) => {
        if (!cancelled) {
          setProperties(listed.items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPropertyError("Unable to load properties.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

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

  const today = new Date();
  const stats = portfolioStats(policies, today);
  const groups = groupPolicies(policies, today);

  function removePolicy(id: string): void {
    setPolicies((current) => current.filter((item) => item.id !== id));
  }

  return (
    <Shell onLogout={logout}>
      <h1>Your insurance portfolio</h1>
      <p className="lede">
        Policies grouped by renewal urgency. Upload a PDF from Uploads to add
        one.
      </p>
      {policyError ? <p className="error">{policyError}</p> : null}
      {propertyError ? <p className="error">{propertyError}</p> : null}
      {!policiesLoaded ? <p className="muted">Loading…</p> : null}
      {policiesLoaded && !policyError && policies.length === 0 ? (
        <p className="muted">
          No saved policies yet. <Link to="/uploads">Upload a PDF</Link>
        </p>
      ) : null}
      {policiesLoaded && policies.length > 0 ? (
        <div aria-label="Saved policies" role="region" className="job-list">
          <StatStrip
            totalPremium={stats.totalPremium}
            renewingWithin30={stats.renewingWithin30}
            renewingWithin90={stats.renewingWithin90}
            premiumUpYoY={stats.premiumUpYoY}
          />
          {URGENCY_ORDER.map((key) => (
            <UrgencySection
              key={key}
              urgencyKey={key}
              policies={groups[key]}
              properties={properties}
              today={today}
              onDeleted={removePolicy}
            />
          ))}
        </div>
      ) : null}
    </Shell>
  );
}
