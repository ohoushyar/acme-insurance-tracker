import { describe, expect, it } from "vitest";
import type { Policy } from "./api";
import {
  daysUntil,
  groupPolicies,
  portfolioStats,
  urgencyOf,
} from "./urgency";

const today = new Date("2026-09-01T12:00:00Z");

function policy(overrides: Partial<Policy> = {}): Policy {
  return {
    id: "pol-1",
    user_id: "user-a",
    source_document_id: "doc-1",
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    property_ids: [],
    policy_number: null,
    named_insured: "Test",
    broker: null,
    effective_date: null,
    renewal_date: null,
    term_premium: null,
    policy_fee: null,
    total_premium: null,
    limit_of_insurance: null,
    coverage_type: null,
    carriers: [],
    deductibles: [],
    locations: [],
    confidence: {
      policy_number: 0,
      named_insured: 0,
      broker: 0,
      effective_date: 0,
      renewal_date: 0,
      term_premium: 0,
      policy_fee: 0,
      total_premium: 0,
      limit_of_insurance: 0,
      coverage_type: 0,
      carriers: 0,
      deductibles: 0,
      locations: 0,
    },
    ...overrides,
  };
}

describe("urgency helpers", () => {
  it("computes whole-day deltas at bucket boundaries", () => {
    expect(daysUntil("2026-09-01", today)).toBe(0);
    expect(daysUntil("2026-10-01", today)).toBe(30);
    expect(daysUntil("2026-10-02", today)).toBe(31);
    expect(daysUntil("2026-11-30", today)).toBe(90);
    expect(daysUntil("2026-12-01", today)).toBe(91);
    expect(daysUntil(null, today)).toBeNull();
  });

  it("maps days into urgency buckets", () => {
    expect(urgencyOf(0)).toBe("urgent");
    expect(urgencyOf(30)).toBe("urgent");
    expect(urgencyOf(31)).toBe("soon");
    expect(urgencyOf(90)).toBe("soon");
    expect(urgencyOf(91)).toBe("on_track");
    expect(urgencyOf(null)).toBe("unknown");
  });

  it("sums premiums and counts renewing buckets", () => {
    const stats = portfolioStats(
      [
        policy({
          id: "a",
          renewal_date: "2026-09-14",
          total_premium: "18400.00",
        }),
        policy({
          id: "b",
          renewal_date: "2026-10-20",
          total_premium: "27600",
        }),
        policy({
          id: "c",
          renewal_date: "2026-12-02",
          total_premium: "52300",
        }),
        policy({ id: "d", renewal_date: null, total_premium: "100" }),
      ],
      today,
    );
    expect(stats.totalPremium).toBe(98400);
    expect(stats.renewingWithin30).toBe(1);
    expect(stats.renewingWithin90).toBe(1);
    expect(stats.premiumUpYoY).toBe(0);
  });

  it("groups policies and omits empty groups when filtered", () => {
    const groups = groupPolicies(
      [
        policy({ id: "urgent", renewal_date: "2026-09-14" }),
        policy({ id: "soon", renewal_date: "2026-10-20" }),
        policy({ id: "track", renewal_date: "2027-01-18" }),
        policy({ id: "none", renewal_date: null }),
      ],
      today,
    );
    expect(groups.urgent.map((p) => p.id)).toEqual(["urgent"]);
    expect(groups.soon.map((p) => p.id)).toEqual(["soon"]);
    expect(groups.on_track.map((p) => p.id)).toEqual(["track"]);
    expect(groups.unknown.map((p) => p.id)).toEqual(["none"]);
  });
});
