import { type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

export function Shell({
  children,
  onLogout,
}: {
  children: ReactNode;
  onLogout?: () => void;
}) {
  const location = useLocation();
  return (
    <div className="app-shell">
      <aside className="app-nav">
        <p className="app-brand">Insurance Tracker</p>
        <nav aria-label="Main">
          <ul className="app-nav-list">
            <li>
              <Link
                to="/"
                aria-current={location.pathname === "/" ? "page" : undefined}
              >
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
