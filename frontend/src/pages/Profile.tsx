import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { ApiError, changePassword } from "../api";
import { useAuth } from "../auth";
import { Shell } from "../components/Shell";

export function Profile() {
  const { user, loading, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
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
    setError("");
    setSuccess("");
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSuccess("Password updated.");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to update password.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Shell onLogout={logout}>
      <h1>Profile</h1>
      <p className="lede">{user.email}</p>
      <form className="review-form" onSubmit={(event) => void onSubmit(event)}>
        <div className="review-field">
          <label htmlFor="current-password">Current password</label>
          <input
            id="current-password"
            name="current_password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
            minLength={8}
          />
        </div>
        <div className="review-field">
          <label htmlFor="new-password">New password</label>
          <input
            id="new-password"
            name="new_password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            required
            minLength={8}
          />
        </div>
        <div className="review-field">
          <label htmlFor="confirm-password">Confirm new password</label>
          <input
            id="confirm-password"
            name="confirm_password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            required
            minLength={8}
          />
        </div>
        {error ? <p className="error">{error}</p> : null}
        {success ? <p className="muted">{success}</p> : null}
        <div className="review-actions">
          <button className="btn-dark" type="submit" disabled={submitting}>
            Update password
          </button>
        </div>
      </form>
    </Shell>
  );
}
