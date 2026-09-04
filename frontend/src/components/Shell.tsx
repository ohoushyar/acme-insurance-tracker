import { type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useReminders } from "../reminder-count";

export function Shell({
  children,
  onLogout,
}: {
  children: ReactNode;
  onLogout?: () => void;
}) {
  const location = useLocation();
  const { unreadCount } = useReminders();
  const remindersLabel =
    unreadCount > 0 ? `Reminders, ${unreadCount} unread` : "Reminders";

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
            <li>
              <Link
                to="/properties"
                aria-current={
                  location.pathname.startsWith("/properties")
                    ? "page"
                    : undefined
                }
              >
                Properties
              </Link>
            </li>
            <li>
              <Link
                to="/reminders"
                aria-current={
                  location.pathname.startsWith("/reminders")
                    ? "page"
                    : undefined
                }
                aria-label={remindersLabel}
              >
                Reminders
                {unreadCount > 0 ? (
                  <span className="nav-count">{unreadCount}</span>
                ) : null}
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
