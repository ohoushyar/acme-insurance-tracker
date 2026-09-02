import { type ReactNode } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth";

function Shell({
  children,
  onLogout,
}: {
  children: ReactNode;
  onLogout?: () => void;
}) {
  return (
    <div className="app-shell">
      <aside className="app-nav">
        <p className="app-brand">Insurance Tracker</p>
        <nav aria-label="Main">
          <ul className="app-nav-list">
            <li>
              <Link to="/" aria-current="page">
                Portfolio
              </Link>
            </li>
          </ul>
        </nav>
        {onLogout ? (
          <button
            className="btn-quiet"
            type="button"
            onClick={() => void onLogout()}
          >
            Log out
          </button>
        ) : null}
      </aside>
      <main className="app-main">{children}</main>
    </div>
  );
}

export function Home() {
  const { user, loading, logout } = useAuth();

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
      <h1>Your insurance portfolio</h1>
      <p className="lede">
        Policies you upload will appear here, grouped by renewal date.
      </p>
      <p className="muted">{user.email}</p>
    </Shell>
  );
}
