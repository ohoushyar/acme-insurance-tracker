import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import {
  ApiError,
  createProperty,
  deleteProperty,
  listProperties,
  updateProperty,
  type Property,
} from "../api";
import { useAuth } from "../auth";
import { ConfirmDelete } from "../components/ConfirmDelete";
import { Shell } from "../components/Shell";

function unlinkCopy(count: number): string {
  if (count <= 0) {
    return "It is not attached to any policies.";
  }
  if (count === 1) {
    return "This will unlink it from 1 policy.";
  }
  return `This will unlink it from ${count} policies.`;
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export function Properties() {
  const { user, loading, logout } = useAuth();
  const [properties, setProperties] = useState<Property[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [label, setLabel] = useState("");
  const [address, setAddress] = useState("");
  const [statedValue, setStatedValue] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;
    void listProperties()
      .then((data) => {
        if (!cancelled) {
          setProperties(data.items);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError
              ? err.message
              : "Unable to load properties.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  function resetForm(): void {
    setEditingId(null);
    setLabel("");
    setAddress("");
    setStatedValue("");
  }

  function startEdit(property: Property): void {
    setPendingDeleteId(null);
    setEditingId(property.id);
    setLabel(property.label);
    setAddress(property.address ?? "");
    setStatedValue(property.stated_value ?? "");
    setError("");
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      setError("Label is required.");
      return;
    }
    setError("");
    setSubmitting(true);
    const body = {
      label: trimmedLabel,
      address: emptyToNull(address),
      stated_value: emptyToNull(statedValue),
    };
    try {
      if (editingId) {
        const updated = await updateProperty(editingId, body);
        setProperties((current) =>
          current.map((item) => (item.id === updated.id ? updated : item)),
        );
      } else {
        const created = await createProperty(body);
        setProperties((current) => [...current, created]);
      }
      resetForm();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to save property.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function onConfirmDelete(property: Property): Promise<void> {
    setError("");
    try {
      await deleteProperty(property.id);
      setProperties((current) =>
        current.filter((item) => item.id !== property.id),
      );
      setPendingDeleteId(null);
      if (editingId === property.id) {
        resetForm();
      }
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
      <h1>Properties</h1>
      <p className="lede">
        Add an addressable property, then attach it to a policy from the policy
        editor.
      </p>
      <form className="review-form" onSubmit={(event) => void onSubmit(event)}>
        <div className="review-field">
          <label htmlFor="property-label">Label</label>
          <input
            id="property-label"
            name="label"
            type="text"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            required
          />
        </div>
        <div className="review-field">
          <label htmlFor="property-address">Address</label>
          <input
            id="property-address"
            name="address"
            type="text"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
          />
        </div>
        <div className="review-field">
          <label htmlFor="property-stated-value">Stated value</label>
          <input
            id="property-stated-value"
            name="stated_value"
            type="text"
            value={statedValue}
            onChange={(event) => setStatedValue(event.target.value)}
          />
        </div>
        {error ? <p className="error">{error}</p> : null}
        <div className="review-actions">
          {editingId ? (
            <button
              className="btn-light"
              type="button"
              onClick={() => {
                resetForm();
                setError("");
              }}
            >
              Cancel
            </button>
          ) : null}
          <button className="btn-dark" type="submit" disabled={submitting}>
            {editingId ? "Save property" : "Add property"}
          </button>
        </div>
      </form>
      {loadError ? <p className="error">{loadError}</p> : null}
      <section aria-label="Properties" className="job-list">
        {properties.length === 0 ? (
          <p className="muted">No properties yet.</p>
        ) : (
          properties.map((property) => (
            <article className="job-card" key={property.id}>
              <header className="job-card-header">
                <h3>{property.label}</h3>
              </header>
              {property.address ? (
                <p className="job-summary">{property.address}</p>
              ) : null}
              {property.stated_value ? (
                <p className="muted">{property.stated_value}</p>
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
                  <button
                    className="btn-quiet"
                    type="button"
                    aria-label={`Edit ${property.label}`}
                    onClick={() => startEdit(property)}
                  >
                    Edit
                  </button>
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
          ))
        )}
      </section>
    </Shell>
  );
}
