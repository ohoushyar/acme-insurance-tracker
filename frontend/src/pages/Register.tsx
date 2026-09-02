import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";

export function Register() {
  const { user, loading, register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    return <Navigate to="/" replace />;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await register(email, password);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to create account.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page">
      <p className="eyebrow">Portfolio insurance</p>
      <h1>Create account</h1>
      <form onSubmit={onSubmit}>
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
        <label htmlFor="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          minLength={8}
        />
        {error ? <p className="error">{error}</p> : null}
        <button className="btn-dark" type="submit" disabled={submitting}>
          Create account
        </button>
      </form>
      <p className="muted">
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </main>
  );
}
