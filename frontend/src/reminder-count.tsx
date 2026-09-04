/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useLocation } from "react-router-dom";
import { listReminders } from "./api";
import { useAuth } from "./auth";

type RemindersContextValue = {
  unreadCount: number;
  refreshReminders: () => Promise<void>;
};

const RemindersContext = createContext<RemindersContextValue>({
  unreadCount: 0,
  refreshReminders: async () => {},
});

export function useReminders(): RemindersContextValue {
  return useContext(RemindersContext);
}

export function RemindersProvider({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  const [fetched, setFetched] = useState<{
    userId: string;
    unreadCount: number;
  } | null>(null);
  const enabled = Boolean(user) && !loading;
  const unreadCount =
    user != null && fetched?.userId === user.id ? fetched.unreadCount : 0;

  const refreshReminders = useCallback(async () => {
    if (!user) {
      return;
    }
    const userId = user.id;
    try {
      const data = await listReminders();
      setFetched({ userId, unreadCount: data.unread_count });
    } catch {
      // Keep the last known count rather than flashing zero.
    }
  }, [user]);

  useEffect(() => {
    if (!enabled || user == null) {
      return;
    }
    const userId = user.id;
    let cancelled = false;
    void listReminders()
      .then((data) => {
        if (!cancelled) {
          setFetched({ userId, unreadCount: data.unread_count });
        }
      })
      .catch(() => {
        // Keep the last known count rather than flashing zero.
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, user, location.pathname]);

  return (
    <RemindersContext.Provider value={{ unreadCount, refreshReminders }}>
      {children}
    </RemindersContext.Provider>
  );
}
