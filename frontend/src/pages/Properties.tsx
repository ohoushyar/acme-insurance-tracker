import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import {
  ApiError,
  deleteProperty,
  listProperties,
  type Property,
} from "../api";
import { useAuth } from "../auth";
import { ConfirmDelete } from "../components/ConfirmDelete";
import { Shell } from "../components/Shell";
import { formatMoneyField } from "../money";

function unlinkCopy(count: number): string {
  if (count <= 0) {
    return "It is not attached to any policies.";
  }
  if (count === 1) {
    return "This will unlink it from 1 policy.";
  }
  return `This will unlink it from ${count} policies.`;
}

export function Properties() {
  const { user, loading, logout } = useAuth();
  const [properties, setProperties] = useState<Property[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;
    void listProperties()
      .then((data) => {
        if (!cancelled) {
          setProperties(data.items);
          setListLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError
              ? err.message
              : "Unable to load properties.",
          );
          setListLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  async function onConfirmDelete(property: Property): Promise<void> {
    setError("");
    try {
      await deleteProperty(property.id);
      setProperties((current) =>
        current.filter((item) => item.id !== property.id),
      );
      setPendingDeleteId(null);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to delete property.",
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

  return (
    <Shell onLogout={logout}>
      <div className="shell-header">
        <h1>Properties</h1>
        <Link
          className="btn-dark btn-add"
          to="/properties/new"
          aria-label="Add property"
        >
          +
        </Link>
      </div>
      <p className="lede">
        Add an addressable property, then attach it to a policy from the policy
        editor.
      </p>
      {error ? <p className="error">{error}</p> : null}
      {loadError ? <p className="error">{loadError}</p> : null}
      <section aria-label="Properties" className="job-list">
        {listLoading ? <p className="muted">Loading…</p> : null}
        {!listLoading && !loadError && properties.length === 0 ? (
          <p className="muted">No properties yet.</p>
        ) : null}
        {properties.map((property) => (
          <article className="job-card" key={property.id}>
            <header className="job-card-header">
              <h3>{property.label}</h3>
            </header>
            {property.address ? (
              <p className="job-summary">{property.address}</p>
            ) : null}
            {property.stated_value ? (
              <p className="muted">{formatMoneyField(property.stated_value)}</p>
            ) : null}
            {pendingDeleteId === property.id ? (
              <ConfirmDelete
                label={property.label}
                warning={`Delete ${property.label}? ${unlinkCopy(property.policy_ids.length)}`}
                onConfirm={() => void onConfirmDelete(property)}
                onCancel={() => setPendingDeleteId(null)}
              />
            ) : (
              <div className="card-actions">
                <Link
                  to={`/properties/${property.id}/edit`}
                  aria-label={`Edit ${property.label}`}
                >
                  Edit
                </Link>
                <button
                  className="btn-quiet"
                  type="button"
                  aria-label={`Delete ${property.label}`}
                  onClick={() => setPendingDeleteId(property.id)}
                >
                  Delete
                </button>
              </div>
            )}
          </article>
        ))}
      </section>
    </Shell>
  );
}
