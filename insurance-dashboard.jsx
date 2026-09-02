import { useState } from "react";

const policies = [
  { id: 1, property: "214 Harbor Ave — Retail Strip", type: "Property", carrier: "Liberty Mutual", premium: 18400, prevPremium: 15200, renewal: "2026-09-14", limit: "$4.2M" },
  { id: 2, property: "214 Harbor Ave — Retail Strip", type: "General Liability", carrier: "Travelers", premium: 6100, prevPremium: 5950, renewal: "2026-09-14", limit: "$2M/$4M" },
  { id: 3, property: "88 Fenmore Industrial Park", type: "Property", carrier: "Chubb", premium: 41200, prevPremium: 33800, renewal: "2026-09-29", limit: "$11.5M" },
  { id: 4, property: "Sundale Apartments (64 units)", type: "Property", carrier: "Nationwide", premium: 27600, prevPremium: 26100, renewal: "2026-10-20", limit: "$8.9M" },
  { id: 5, property: "Sundale Apartments (64 units)", type: "General Liability", carrier: "Travelers", premium: 8900, prevPremium: 8400, renewal: "2026-10-20", limit: "$1M/$2M" },
  { id: 6, property: "Meridian Office Plaza", type: "Property", carrier: "Zurich", premium: 52300, prevPremium: 51000, renewal: "2026-12-02", limit: "$16M" },
  { id: 7, property: "Meridian Office Plaza", type: "Umbrella", carrier: "AIG", premium: 14700, prevPremium: 13100, renewal: "2026-12-02", limit: "$10M" },
  { id: 8, property: "Coldwater Self-Storage", type: "Property", carrier: "Liberty Mutual", premium: 9800, prevPremium: 9650, renewal: "2027-01-18", limit: "$3.1M" },
  { id: 9, property: "88 Fenmore Industrial Park", type: "Flood", carrier: "NFIP", premium: 5200, prevPremium: 5200, renewal: "2027-02-05", limit: "$500K" },
];

const today = new Date("2026-09-01");

function daysUntil(dateStr) {
  return Math.round((new Date(dateStr) - today) / 86400000);
}

function urgencyOf(days) {
  if (days <= 30) return "urgent";
  if (days <= 90) return "soon";
  return "clear";
}

const urgencyStyle = {
  urgent: { color: "#B5432F", label: "Renews within 30 days" },
  soon: { color: "#C97A2B", label: "Renews within 90 days" },
  clear: { color: "#2F6F62", label: "On track" },
};

function pctChange(curr, prev) {
  if (prev === 0) return 0;
  return ((curr - prev) / prev) * 100;
}

function fmtMoney(n) {
  return "$" + n.toLocaleString();
}

function fmtDate(dateStr) {
  return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function InsuranceDashboard() {
  const [selected, setSelected] = useState(null);

  const enriched = policies
    .map((p) => ({ ...p, days: daysUntil(p.renewal), change: pctChange(p.premium, p.prevPremium) }))
    .sort((a, b) => a.days - b.days);

  const totalPremium = policies.reduce((sum, p) => sum + p.premium, 0);
  const urgentCount = enriched.filter((p) => p.days <= 30).length;
  const soonCount = enriched.filter((p) => p.days > 30 && p.days <= 90).length;
  const flaggedCount = enriched.filter((p) => p.change >= 10).length;

  const groups = { urgent: [], soon: [], clear: [] };
  enriched.forEach((p) => groups[urgencyOf(p.days)].push(p));

  return (
    <div
      style={{
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        background: "#FAFAF7",
        color: "#1C2430",
        minHeight: "100vh",
        padding: "20px 16px 40px",
        maxWidth: 480,
        margin: "0 auto",
      }}
    >
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 13, color: "#5B6472", marginBottom: 2 }}>Portfolio insurance</div>
        <div style={{ fontFamily: "Georgia, serif", fontSize: 26, fontWeight: 600, lineHeight: 1.15 }}>
          9 policies across 5 properties
        </div>
      </div>

      {/* Summary stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 1,
          background: "#E4E1D8",
          border: "1px solid #E4E1D8",
          marginBottom: 28,
        }}
      >
        <Stat label="Total annual premium" value={fmtMoney(totalPremium)} />
        <Stat label="Renewing within 30 days" value={urgentCount} tone={urgentCount > 0 ? "#B5432F" : undefined} />
        <Stat label="Renewing within 90 days" value={soonCount} tone={soonCount > 0 ? "#C97A2B" : undefined} />
        <Stat label="Premium up 10%+ vs last year" value={flaggedCount} tone={flaggedCount > 0 ? "#C97A2B" : undefined} />
      </div>

      {/* Renewal groups */}
      {["urgent", "soon", "clear"].map((key) =>
        groups[key].length ? (
          <div key={key} style={{ marginBottom: 24 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: urgencyStyle[key].color,
                marginBottom: 10,
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: urgencyStyle[key].color,
                  display: "inline-block",
                }}
              />
              {urgencyStyle[key].label}
            </div>
            <div>
              {groups[key].map((p) => (
                <PolicyRow key={p.id} p={p} onClick={() => setSelected(p)} />
              ))}
            </div>
          </div>
        ) : null
      )}

      {selected && <PolicyDetail p={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function Stat({ label, value, tone }) {
  return (
    <div style={{ background: "#FAFAF7", padding: "14px 16px" }}>
      <div style={{ fontSize: 12, color: "#5B6472", marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "Georgia, serif", fontSize: 22, color: tone || "#1C2430" }}>{value}</div>
    </div>
  );
}

function PolicyRow({ p, onClick }) {
  const changeUp = p.change >= 10;
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        padding: "12px 0",
        borderBottom: "1px solid #E4E1D8",
        cursor: "pointer",
      }}
    >
      <div style={{ flex: 1, paddingRight: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>{p.property}</div>
        <div style={{ fontSize: 12.5, color: "#5B6472" }}>
          {p.type} · {p.carrier} · {fmtDate(p.renewal)}
        </div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{ fontFamily: "Georgia, serif", fontSize: 15 }}>{fmtMoney(p.premium)}</div>
        {p.change !== 0 && (
          <div style={{ fontSize: 12, color: changeUp ? "#B5432F" : "#5B6472" }}>
            {p.change > 0 ? "+" : ""}
            {p.change.toFixed(1)}% YoY
          </div>
        )}
      </div>
    </div>
  );
}

function PolicyDetail({ p, onClose }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(28,36,48,0.4)",
        display: "flex",
        alignItems: "flex-end",
        zIndex: 10,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#FAFAF7",
          width: "100%",
          maxWidth: 480,
          margin: "0 auto",
          padding: "24px 20px 32px",
          borderTop: "1px solid #E4E1D8",
        }}
      >
        <div style={{ fontSize: 13, color: "#5B6472", marginBottom: 4 }}>{p.type} insurance</div>
        <div style={{ fontFamily: "Georgia, serif", fontSize: 20, marginBottom: 18 }}>{p.property}</div>

        <DetailLine label="Carrier" value={p.carrier} />
        <DetailLine label="Coverage limit" value={p.limit} />
        <DetailLine label="Current premium" value={fmtMoney(p.premium)} />
        <DetailLine label="Last year's premium" value={fmtMoney(p.prevPremium)} />
        <DetailLine
          label="Year-over-year change"
          value={`${p.change > 0 ? "+" : ""}${p.change.toFixed(1)}%`}
          tone={p.change >= 10 ? "#B5432F" : "#1C2430"}
        />
        <DetailLine label="Renewal date" value={fmtDate(p.renewal)} />
        <DetailLine label="Days until renewal" value={p.days} />

        <button
          onClick={onClose}
          style={{
            marginTop: 20,
            width: "100%",
            padding: "12px 0",
            background: "#1C2430",
            color: "#FAFAF7",
            border: "none",
            fontSize: 14,
            cursor: "pointer",
          }}
        >
          Close
        </button>
      </div>
    </div>
  );
}

function DetailLine({ label, value, tone }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        padding: "9px 0",
        borderBottom: "1px solid #E4E1D8",
        fontSize: 14,
      }}
    >
      <span style={{ color: "#5B6472" }}>{label}</span>
      <span style={{ fontWeight: 600, color: tone || "#1C2430" }}>{value}</span>
    </div>
  );
}
