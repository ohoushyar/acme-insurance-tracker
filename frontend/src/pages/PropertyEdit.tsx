import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { ApiError, getProperty, updateProperty } from "../api";
import { useAuth } from "../auth";
import { PropertyFormFields } from "../components/PropertyFormFields";
import { Shell } from "../components/Shell";
import { canonicalMoneyString } from "../money";
import { propertyWriteBody } from "../property-write";

export function PropertyEdit() {
  const { user, loading, logout } = useAuth();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [label, setLabel] = useState("");
  const [address, setAddress] = useState("");
  const [statedValue, setStatedValue] = useState("");
  const [loadError, setLoadError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!user || !id) {
      return;
    }
    let cancelled = false;
    void getProperty(id)
      .then((property) => {
        if (cancelled) {
          return;
        }
        setLabel(property.label);
        setAddress(property.address ?? "");
        setStatedValue(canonicalMoneyString(property.stated_value) ?? "");
        setLoaded(true);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError ? err.message : "Unable to load property.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user, id]);

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
        <Link to="/properties">Back to properties</Link>
      </Shell>
    );
  }

  if (!loaded) {
    return (
      <Shell onLogout={logout}>
        <p className="muted">Loading…</p>
      </Shell>
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!id) {
      return;
    }
    const body = propertyWriteBody(label, address, statedValue);
    if (!body) {
      setError("Label is required.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await updateProperty(id, body);
      navigate("/properties");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to save property.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Shell onLogout={logout}>
      <h1>Edit property</h1>
      <form className="review-form" onSubmit={(event) => void onSubmit(event)}>
        <PropertyFormFields
          label={label}
          address={address}
          statedValue={statedValue}
          onLabelChange={setLabel}
          onAddressChange={setAddress}
          onStatedValueChange={setStatedValue}
        />
        {error ? <p className="error">{error}</p> : null}
        <div className="review-actions">
          <button
            className="btn-light"
            type="button"
            onClick={() => navigate("/properties")}
          >
            Cancel
          </button>
          <button className="btn-dark" type="submit" disabled={submitting}>
            Save property
          </button>
        </div>
      </form>
    </Shell>
  );
}
