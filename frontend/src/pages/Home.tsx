import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";

export function Home() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return (
      <main className="page">
        <p className="muted">Loading…</p>
      </main>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <main className="page">
      <div className="shell-header">
        <div>
          <p className="eyebrow">Portfolio insurance</p>
          <h1>Your portfolio</h1>
        </div>
        <button
          className="btn-dark"
          type="button"
          onClick={() => void logout()}
        >
          Log out
        </button>
      </div>
      <p className="muted">{user.email}</p>
      <p className="muted">Upload and tracking arrive in a later step.</p>
    </main>
  );
}
