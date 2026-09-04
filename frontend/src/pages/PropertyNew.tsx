import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiError, createProperty } from "../api";
import { useAuth } from "../auth";
import { PropertyFormFields } from "../components/PropertyFormFields";
import { Shell } from "../components/Shell";
import { propertyWriteBody } from "../property-write";

export function PropertyNew() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  const [label, setLabel] = useState("");
  const [address, setAddress] = useState("");
  const [statedValue, setStatedValue] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

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

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const body = propertyWriteBody(label, address, statedValue);
    if (!body) {
      setError("Label is required.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await createProperty(body);
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
      <h1>Add property</h1>
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
            Add property
          </button>
        </div>
      </form>
    </Shell>
  );
}
