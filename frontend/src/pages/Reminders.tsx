import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import {
  ApiError,
  listReminders,
  markReminderRead,
  markReminderUnread,
  type Reminder,
} from "../api";
import { useAuth } from "../auth";
import { Shell } from "../components/Shell";
import { useReminders } from "../reminder-count";

function reminderTitle(item: Reminder): string {
  return item.named_insured?.trim() || "Untitled policy";
}

function reminderCopy(item: Reminder): string {
  const insured = reminderTitle(item);
  const coverage = item.coverage_type?.trim() || "Coverage";
  return `${insured} · ${coverage} · ${item.threshold_days}-day reminder · renews ${item.renewal_date}`;
}

export function Reminders() {
  const { user, loading, logout } = useAuth();
  const [items, setItems] = useState<Reminder[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;
    void listReminders()
      .then((data) => {
        if (!cancelled) {
          setItems(data.items);
          setListLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError ? err.message : "Unable to load reminders.",
          );
          setListLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

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

  if (loadError) {
    return (
      <Shell onLogout={logout}>
        <p className="error">{loadError}</p>
      </Shell>
    );
  }

  if (listLoading) {
    return (
      <Shell onLogout={logout}>
        <p className="muted">Loading…</p>
      </Shell>
    );
  }

  const unread = items.filter((item) => item.read_at == null);
  const read = items.filter((item) => item.read_at != null);

  function onUpdated(updated: Reminder): void {
    setItems((current) =>
      current.map((row) => (row.id === updated.id ? updated : row)),
    );
    setActionError("");
  }

  return (
    <Shell onLogout={logout}>
      <h1>Reminders</h1>
      <p className="lede">
        60-, 30-, and 10-day notices before a policy renews. Mark one as read
        after you've seen it, or unread to bring it back.
      </p>
      {actionError ? <p className="error">{actionError}</p> : null}
      {items.length === 0 ? (
        <p className="muted">No renewal reminders right now.</p>
      ) : (
        <>
          {unread.length > 0 ? (
            <section
              className="urgency-group"
              aria-labelledby="unread-reminders"
            >
              <h2 className="urgency-heading" id="unread-reminders">
                Unread
              </h2>
              {unread.map((item) => (
                <ReminderCard
                  key={item.id}
                  item={item}
                  onUpdated={onUpdated}
                  onError={setActionError}
                />
              ))}
            </section>
          ) : null}
          {read.length > 0 ? (
            <section className="urgency-group" aria-labelledby="read-reminders">
              <h2 className="urgency-heading" id="read-reminders">
                Read
              </h2>
              {read.map((item) => (
                <ReminderCard
                  key={item.id}
                  item={item}
                  onUpdated={onUpdated}
                  onError={setActionError}
                />
              ))}
            </section>
          ) : null}
        </>
      )}
    </Shell>
  );
}

function ReminderCard({
  item,
  onUpdated,
  onError,
}: {
  item: Reminder;
  onUpdated: (item: Reminder) => void;
  onError: (message: string) => void;
}) {
  const { refreshReminders } = useReminders();
  const title = reminderTitle(item);
  const isUnread = item.read_at == null;

  async function onToggleRead(): Promise<void> {
    try {
      const updated = isUnread
        ? await markReminderRead(item.id)
        : await markReminderUnread(item.id);
      onUpdated(updated);
      await refreshReminders();
    } catch (err: unknown) {
      onError(
        err instanceof ApiError
          ? err.message
          : isUnread
            ? "Unable to mark reminder as read."
            : "Unable to mark reminder as unread.",
      );
    }
  }

  return (
    <article className="job-card">
      <p className="job-summary">{reminderCopy(item)}</p>
      <div className="card-actions">
        <Link to={`/policies/${item.policy_id}`} aria-label={`View ${title}`}>
          View
        </Link>
        <button
          className="btn-quiet"
          type="button"
          aria-label={`Mark ${title} as ${isUnread ? "read" : "unread"}`}
          onClick={() => void onToggleRead()}
        >
          {isUnread ? "Mark as read" : "Mark as unread"}
        </button>
      </div>
    </article>
  );
}
