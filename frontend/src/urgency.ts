import type { Policy } from "./api";

export type UrgencyKey = "urgent" | "soon" | "on_track" | "unknown";

export const URGENCY_ORDER: UrgencyKey[] = [
  "urgent",
  "soon",
  "on_track",
  "unknown",
];

export const URGENCY_LABELS: Record<UrgencyKey, string> = {
  urgent: "Renews within 30 days",
  soon: "Renews within 90 days",
  on_track: "On track",
  unknown: "No renewal date",
};

export type PortfolioStats = {
  totalPremium: number;
  renewingWithin30: number;
  renewingWithin90: number;
  premiumUpYoY: number;
};

function parseDayUtc(isoDate: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!year || !month || !day) {
    return null;
  }
  return new Date(Date.UTC(year, month - 1, day));
}

function startOfUtcDay(date: Date): Date {
  return new Date(
    Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()),
  );
}

/** Whole UTC days from today to renewal (negative if past). */
export function daysUntil(
  renewalDate: string | null | undefined,
  today: Date,
): number | null {
  if (!renewalDate) {
    return null;
  }
  const renewal = parseDayUtc(renewalDate);
  if (!renewal) {
    return null;
  }
  const start = startOfUtcDay(today);
  return Math.round((renewal.getTime() - start.getTime()) / 86_400_000);
}

export function urgencyOf(days: number | null): UrgencyKey {
  if (days === null) {
    return "unknown";
  }
  if (days <= 30) {
    return "urgent";
  }
  if (days <= 90) {
    return "soon";
  }
  return "on_track";
}

export function premiumAmount(policy: Policy): number {
  if (policy.total_premium == null || policy.total_premium === "") {
    return 0;
  }
  const value = Number(policy.total_premium);
  return Number.isFinite(value) ? value : 0;
}

export function portfolioStats(
  policies: Policy[],
  today: Date,
): PortfolioStats {
  let totalPremium = 0;
  let renewingWithin30 = 0;
  let renewingWithin90 = 0;
  let premiumUpYoY = 0;
  for (const policy of policies) {
    totalPremium += premiumAmount(policy);
    if (policy.yoy_flagged) {
      premiumUpYoY += 1;
    }
    const days = daysUntil(policy.renewal_date, today);
    if (days === null) {
      continue;
    }
    if (days <= 30) {
      renewingWithin30 += 1;
    } else if (days <= 90) {
      renewingWithin90 += 1;
    }
  }
  return { totalPremium, renewingWithin30, renewingWithin90, premiumUpYoY };
}

export function groupPolicies(
  policies: Policy[],
  today: Date,
): Record<UrgencyKey, Policy[]> {
  const groups: Record<UrgencyKey, Policy[]> = {
    urgent: [],
    soon: [],
    on_track: [],
    unknown: [],
  };
  const enriched = policies.map((policy) => ({
    policy,
    days: daysUntil(policy.renewal_date, today),
  }));
  enriched.sort((a, b) => {
    if (a.days === null && b.days === null) {
      return 0;
    }
    if (a.days === null) {
      return 1;
    }
    if (b.days === null) {
      return -1;
    }
    return a.days - b.days;
  });
  for (const item of enriched) {
    groups[urgencyOf(item.days)].push(item.policy);
  }
  return groups;
}

export { formatMoney } from "./money";
