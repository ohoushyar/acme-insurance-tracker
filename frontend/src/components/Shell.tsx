import { type ReactNode, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ApiError, resendVerification } from "../api";
import { useAuth } from "../auth";
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
  const { user } = useAuth();
  const [bannerError, setBannerError] = useState("");
  const [bannerMessage, setBannerMessage] = useState("");
  const [resending, setResending] = useState(false);
  const remindersLabel =
    unreadCount > 0 ? `Reminders, ${unreadCount} unread` : "Reminders";
  const needsVerification = user?.email_verified_at === null;

  async function onResend(): Promise<void> {
    setBannerError("");
    setBannerMessage("");
    setResending(true);
    try {
      await resendVerification();
      setBannerMessage("Check your inbox for a verification link.");
    } catch (err) {
      setBannerError(
        err instanceof ApiError
          ? err.message
          : "Unable to send a verification email.",
      );
    } finally {
      setResending(false);
    }
  }

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
                to="/uploads"
                aria-current={
                  location.pathname.startsWith("/uploads") ? "page" : undefined
                }
              >
                Uploads
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
            <li>
              <Link
                to="/profile"
                aria-current={
                  location.pathname.startsWith("/profile") ? "page" : undefined
                }
              >
                Profile
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
      <main className="app-main">
        {needsVerification ? (
          <div className="verify-banner" role="status">
            <p>
              Verify your email to receive renewal reminders.
              <button
                className="btn-quiet"
                type="button"
                onClick={() => void onResend()}
                disabled={resending}
              >
                Resend verification email
              </button>
            </p>
            {bannerMessage ? <p className="muted">{bannerMessage}</p> : null}
            {bannerError ? <p className="error">{bannerError}</p> : null}
          </div>
        ) : null}
        {children}
      </main>
    </div>
  );
}
