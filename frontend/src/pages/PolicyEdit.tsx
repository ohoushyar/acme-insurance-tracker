import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  getPolicy,
  listProperties,
  updatePolicy,
  type ExtractedPolicy,
  type Property,
} from "../api";
import { useAuth } from "../auth";
import { PolicyFormFields } from "../components/PolicyFormFields";
import { Shell } from "../components/Shell";
import { normalizeExtracted } from "../extracted";

export function PolicyEdit() {
  const { user, loading, logout } = useAuth();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [draft, setDraft] = useState<ExtractedPolicy | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loadError, setLoadError] = useState("");
  const [propertiesError, setPropertiesError] = useState("");
  const [error, setError] = useState("");
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
    void getPolicy(id)
      .then((policy) => {
        if (cancelled) {
          return;
        }
        setDraft(normalizeExtracted(policy));
        setSelectedIds(policy.property_ids ?? []);
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
        if (!cancelled) {
          setPropertiesError("Unable to load properties.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id, user]);

  function toggleProperty(propertyId: string): void {
    setSelectedIds((current) =>
      current.includes(propertyId)
        ? current.filter((item) => item !== propertyId)
        : [...current, propertyId],
    );
  }

  async function onSave(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!id || !draft) {
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await updatePolicy(id, { ...draft, property_ids: selectedIds });
      navigate("/");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to save policy.",
      );
    } finally {
      setSubmitting(false);
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

  if (!draft || !id) {
    return (
      <Shell onLogout={logout}>
        <p className="muted">Loading…</p>
      </Shell>
    );
  }

  return (
    <Shell onLogout={logout}>
      <h1>Edit policy</h1>
      <p className="lede">
        Update confirmed fields and attach properties from your portfolio.
      </p>
      <form className="review-form" onSubmit={(event) => void onSave(event)}>
        <PolicyFormFields draft={draft} onChange={updateDraft} />
        <fieldset className="review-fieldset">
          <legend>Attached properties</legend>
          {propertiesError ? (
            <p className="error">{propertiesError}</p>
          ) : properties.length === 0 ? (
            <p className="muted">
              No properties yet.{" "}
              <Link to="/properties/new">Add a property</Link>.
            </p>
          ) : (
            <div className="attach-list">
              {properties.map((property) => (
                <label key={property.id} htmlFor={`attach-${property.id}`}>
                  <input
                    id={`attach-${property.id}`}
                    type="checkbox"
                    checked={selectedIds.includes(property.id)}
                    onChange={() => toggleProperty(property.id)}
                  />
                  {property.label}
                </label>
              ))}
            </div>
          )}
        </fieldset>
        {error ? <p className="error">{error}</p> : null}
        <div className="review-actions">
          <button
            className="btn-light"
            type="button"
            onClick={() => navigate("/")}
          >
            Cancel
          </button>
          <button className="btn-dark" type="submit" disabled={submitting}>
            Save policy
          </button>
        </div>
      </form>
    </Shell>
  );
}
