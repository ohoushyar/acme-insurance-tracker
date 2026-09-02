# PRD: CRE Insurance Renewal Tracker (V1 — with accounts)

## 1. Problem

Mid-market commercial real estate owners/operators (roughly 15–150
properties) manage property and liability insurance renewals manually —
typically in a spreadsheet someone updates by hand after each renewal.
This breaks down in a specific, predictable way: nobody has dedicated
staff for insurance tracking, so upkeep is the first thing to slip. A
renewal date is missed, or a premium increase isn't noticed until the
invoice arrives.

This is distinct from adjacent CRE pain points (debt maturity tracking,
compliance/energy reporting) which already have entrenched, if
imperfect, incumbents (TreasuryView, LoanBoss, Cherre/RealPage,
Re-Leased). Insurance renewal tracking for the *owner* side (not the
broker or insurer side) has no clear dedicated tool at the mid-market
tier — existing options are either broker-side software, generic
insurance/ERM platforms, or a minor feature bolted onto broader
property-management suites (e.g. STRATAFOLIO).

## 2. Target user

An owner, asset manager, or the one person wearing multiple hats at a
firm with roughly 15–150 properties, who currently tracks insurance
renewals in a spreadsheet or in their head, and is also often the same
person tracking debt and compliance deadlines.

**Explicitly not the target:** an owner with 1–3 properties. That
person should keep calling their broker directly — building software
for them adds overhead nobody wants at that scale.

## 3. What's new in this revision

This moves beyond a click-through prototype: users can **register,
log in, and manage their own portfolio** persistently. This changes
the project from "a UI that proves the concept" to "a small
multi-tenant application" — every policy and property belongs to an
authenticated user, and data must persist between sessions. Section 6
(data model), Section 5 (scope), and Section 7 (build order) are
updated accordingly. Sections 1, 2, 4, 8, and 9 are unchanged from the
prototype phase and still apply as-is.

## 4. Core value proposition

Not "insurance shopping" or benchmarking against the market (no
accessible data source for that at prototype stage — see
Non-Goals). The value is **removing the manual maintenance step**:
drop in a policy PDF, get structured data and a portfolio-wide,
date-sorted view automatically, instead of someone having to
transcribe it and remember to check it.

## 5. Validated technical approach

Tested against a real, filled-in commercial property insurance policy
PDF (ICAT/Harbor Cove Condominium Association, ~35 pages). Findings
that shape the design:

- The declarations data (premium, dates, limits, deductibles) lives on
  a small fraction of pages; the rest is standard ISO boilerplate
  policy language, identical across most policies and irrelevant to
  extraction.
- Rule-based/regex parsing is not viable — field position and format
  vary by carrier. **LLM-based extraction against a fixed JSON schema
  is the right approach**, not a rigid template parser.
- Real policies commonly have: multiple properties/locations under one
  policy number, multiple co-insurers sharing one policy (e.g. several
  Lloyd's syndicates + a standard insurer), and **multiple deductibles
  by peril** (hurricane vs. all-other-windstorm vs. earthquake vs. all
  other peril) rather than one clean deductible value. The data model
  must support all three, or it will silently drop real data.
- Premium and date fields extract cleanly once the declarations page
  is correctly located — this is the highest-confidence, highest-value
  part of the extraction.

## 6. Scope

### 6.1 In scope (V1)

**Accounts & authentication**
- User registration (email + password at minimum; social/SSO login is
  a nice-to-have, not required for V1).
- Login/logout, password reset flow.
- Each user has exactly one portfolio in V1 (see Non-Goals re:
  multi-user/team accounts on one portfolio).
- Session handling (standard token/session-based auth — specific
  library/approach is an implementation decision).
- All portfolio data (properties, policies, uploaded documents) is
  scoped to the authenticated user; no user can see another user's
  data.

**Upload & extraction**
- Manual upload of one or more policy PDFs (drag-and-drop or file
  picker).
- LLM-based extraction into a fixed schema (see Section 6).
- Extraction returns `null`/"not found" for missing fields rather than
  guessing.

**Review step (required before saving)**
- Show all extracted fields to the user next to/alongside confidence
  in each field, before committing to the portfolio.
- User can edit any field before confirming.
- This is a hard requirement, not a nice-to-have — the data feeds
  financial decisions, and silent extraction errors are worse than no
  data.

**Portfolio dashboard**
- List view of all policies, grouped by renewal urgency (e.g. ≤30
  days, ≤90 days, on track) and sorted by renewal date within each
  group.
- Portfolio summary stats: total annual premium, count renewing soon,
  count with a significant YoY premium increase.
- Policy detail view: all extracted fields for one policy.

**Multi-year trend (per property/policy)**
- If more than one year of the same policy has been uploaded, show a
  line chart of premium over time and the % change over the tracked
  period.
- Flag a YoY premium increase above a threshold (suggest 10%+ as
  configurable default) at both the portfolio-summary level and the
  individual-policy level.

**Reminders**
- Flag/notify at 60/30/10 days before a renewal date. (Notification
  delivery mechanism — email vs. in-app — is an implementation
  decision, not fixed by this PRD.)

**Portfolio management**
- User can add/remove properties from their portfolio independent of
  uploading a policy (e.g. add a property first, attach policies to
  it later).
- User can edit property-level details (name/label, address) after
  creation.
- User can delete a policy or a property (with confirmation).

### 6.2 Explicitly out of scope (V1)

- **Multi-user / team accounts.** One login = one portfolio owner. No
  shared portfolios, roles, or permissions (e.g. an owner inviting an
  assistant with limited access) in V1. This is a reasonable
  fast-follow but adds real design surface (roles, invitations,
  permission scoping) that shouldn't block getting a working
  single-user version out first.
- **Billing/subscription/payment.** Registration is free in V1; no
  payment flow, plan tiers, or usage limits are in scope yet.
- **Email inbox integration** (auto-pulling renewal docs from email).
  Manual upload only for V1.
- **Broker or carrier API integration.** Carriers/brokers generally do
  not expose policyholder-facing APIs; this would require direct
  partnership agreements, which is a business-development effort, not
  an engineering task for the prototype.
- **Cross-customer premium benchmarking** ("is my rate competitive
  vs. similar properties"). This requires an aggregated dataset across
  many customers that a prototype won't have. Revisit once there's
  real usage/scale.
- **Any live/external data feeds** of any kind. All data in V1 comes
  from documents the user uploads.
- **Debt maturity tracking, compliance tracking, or any other pain
  point.** This PRD is scoped to insurance only. Do not bundle in
  adjacent features — the mid-market gap analysis showed a
  four-in-one bundle multiplies integration/maintenance surface
  without validating any one piece first.

## 7. Data model (draft schema)

Design constraint from Section 5: one policy may cover multiple
properties, multiple co-insurers, and multiple peril-specific
deductibles. Now also scoped per-user, since portfolios are no longer
shared/anonymous. Sketch:

```
User
├── id
├── email
├── passwordHash               // or auth-provider reference if using SSO
├── createdAt
└── properties[]               // owned via Property.userId, not embedded

Property
├── id
├── userId                     // owner — every property belongs to exactly one user
├── label                      // user-facing name, e.g. "Sundale Apartments"
├── address
├── statedValue                // optional
└── policies[]                 // owned via Policy.propertyId(s), not embedded

Policy
├── id
├── userId                     // denormalized owner ref for query/auth convenience
├── policyNumber
├── namedInsured
├── carrier[]                  // supports multiple co-insurers
├── broker
├── effectiveDate
├── renewalDate
├── termPremium
├── policyFee
├── totalPremium
├── limitOfInsurance
├── coverageType               // Property | General Liability | Umbrella | Flood | etc.
├── deductibles[]              // { peril, amount } — NOT a single value
├── propertyIds[]              // one policy may cover multiple properties
├── sourceDocument              // reference to the uploaded PDF (stored per-user)
└── extractionConfidence       // per-field or overall flag for review step

PolicyHistory                  // links policies across years for the same coverage
├── userId
├── propertyId / policyGroup
└── entries[]  { year, premium, policyId }
```

**Note on auth boundary:** every query for properties, policies, or
history must filter by the authenticated user's id at the data-access
layer, not just hide data in the UI. This is a security requirement,
not a display preference.

## 8. Build order

1. **Auth foundation first**: registration, login, session handling,
   and the user-scoped data access pattern (Section 7's auth
   boundary). Building this after the data layer exists means
   retrofitting ownership onto every table/query — cheaper to start
   with it in place.
2. Upload + extraction pipeline (prove PDF → structured JSON works
   reliably on real documents, not just clean synthetic ones).
3. Review/confirm screen.
4. Storage of confirmed policies, scoped to the logged-in user
   (structure per Section 7).
5. Portfolio management (add/edit/delete properties and policies).
6. Dashboard list view + summary stats.
7. Policy detail view.
8. Multi-year trend chart + YoY change flagging.
9. Renewal reminders.

## 9. Design reference

A working front-end mockup with sample data already exists
(React component, ink/paper color palette, Georgia serif for
numeric/headline treatment, urgency-grouped list, slide-up detail
panels, recharts line chart for trend view). Use it as the UI
reference point when wiring up real data — the visual design is
considered validated for the prototype stage; focus engineering
effort on the extraction pipeline and data model instead.

## 10. Open questions / risks to test next

- **Extraction reliability at scale**: tested on one real policy
  document so far. Needs testing against a wider variety of carriers
  and document formats (scanned/image-based PDFs, non-ISO-standard
  layouts, renewal notices vs. full policy jackets) before trusting
  the extraction pipeline.
- **Multi-year linking**: how does the system know two uploaded
  documents (a year apart) represent the "same" policy/coverage for
  trend purposes? Likely needs a matching heuristic (same property +
  same coverage type + same or successor carrier) with a manual
  override, not pure automation.
- **Notification delivery**: not yet decided whether V1 reminders are
  in-app only or also emailed — email requires a verified address at
  minimum, which the registration flow should capture regardless.
- **Password reset delivery**: implies email sending is needed for
  account recovery even if renewal reminders end up in-app-only —
  worth setting up email infrastructure once, for both uses.
- **Document storage**: uploaded PDFs need to persist per-user (for
  re-review/audit later), which means choosing a file storage
  approach (not just extracted JSON) as part of the auth-scoped data
  layer in Section 7.

## 11. Success criteria for this phase

- A user can register, log in, and see only their own data — verified
  by testing that one user's session cannot access another user's
  properties or policies via the API, not just that the UI doesn't
  show them.
- Extraction pipeline correctly pulls all core fields (premium, dates,
  limits, deductibles-by-peril, property address) from a handful of
  real (not synthetic) policy documents from different carriers,
  without silently dropping multi-property or multi-deductible data.
- A logged-in user can go from "upload PDF" to "see it correctly
  reflected in their dashboard" without manual data entry beyond the
  review/confirm step, and the data is still there the next time they
  log in.
