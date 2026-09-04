import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, verifyEmail } from "../api";
import { useAuth } from "../auth";

export function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const { user, loading, setUser } = useAuth();
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const missingToken = token === "";

  useEffect(() => {
    if (!token || loading) {
      return;
    }
    let cancelled = false;
    const hadSession = user !== null;
    verifyEmail(token)
      .then((verified) => {
        if (cancelled) return;
        if (hadSession) {
          setUser(verified);
          navigate("/", { replace: true });
          return;
        }
        setDone(true);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? err.message
            : "This verification link is not valid.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [token, loading, user, navigate, setUser]);

  return (
    <main className="auth-page">
      <div className="auth-card">
        <h1>Insurance Tracker</h1>
        <p className="lede">Verify your email</p>
        {missingToken ? (
          <p className="error">This verification link is missing a token.</p>
        ) : error ? (
          <p className="error">{error}</p>
        ) : done ? (
          <p className="muted">Your email is verified. Sign in to continue.</p>
        ) : (
          <p className="muted">Verifying…</p>
        )}
        <p className="muted">
          <Link to="/login">{done ? "Sign in" : "Back to sign in"}</Link>
        </p>
      </div>
    </main>
  );
}
