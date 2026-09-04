import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, forgotPassword } from "../api";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await forgotPassword(email);
      setSubmitted(true);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to send reset email.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <h1>Insurance Tracker</h1>
        <p className="lede">Reset your password</p>
        {submitted ? (
          <p className="muted">
            If an account exists for that address, we sent a reset link.
          </p>
        ) : (
          <form onSubmit={(event) => void onSubmit(event)}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            {error ? <p className="error">{error}</p> : null}
            <button className="btn-dark" type="submit" disabled={submitting}>
              Send reset link
            </button>
          </form>
        )}
        <p className="muted">
          <Link to="/login">Back to sign in</Link>
        </p>
      </div>
    </main>
  );
}
