import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

// Real extracted data from an actual Harbor Cove Condominium Association policy PDF (2020-2021 term).
// Years 2022-2025 are illustrative — modeled to demonstrate the trend feature, since no
// multi-year history exists for this particular document.
const harborCoveExtraction = {
  property: "Harbor Cove Condominium (3 buildings)",
  address: "27282 Canal Road, Orange Beach, AL 36561",
  namedInsured: "Harbor Cove Condominium Association, Inc",
  policyNumber: "01-7590121387-S-02",
  carrier: "ICAT (Lloyd's syndicates + Indian Harbor Insurance Co.)",
  broker: "Risk Placement Services GA",
  effectiveDate: "2020-02-22",
  renewalDate: "2021-02-22",
  termPremium: 54809,
  policyFee: 270,
  totalPremium: 55079,
  limitOfInsurance: 15612455,
  deductibles: [
    { peril: "Named Hurricane", amount: "3.00% Cal. Yr. Aggregate (min $50,000)" },
    { peril: "All Other Windstorm/Hail", amount: "$25,000 per occurrence" },
    { peril: "Earthquake", amount: "$25,000 per occurrence" },
    { peril: "All Other Peril", amount: "$5,000 per occurrence" },
  ],
  history: [
    { year: 2021, premium: 55079, note: "From source PDF" },
    { year: 2022, premium: 61400, note: "Illustrative" },
    { year: 2023, premium: 74200, note: "Illustrative" },
    { year: 2024, premium: 89600, note: "Illustrative" },
    { year: 2025, premium: 97100, note: "Illustrative" },
  ],
};

const existingPolicies = [
  { id: 1, property: "214 Harbor Ave — Retail Strip", type: "Property", carrier: "Liberty Mutual", premium: 18400, renewal: "2026-09-14",
    history: [{ year: 2021, premium: 12100 }, { year: 2022, premium: 12900 }, { year: 2023, premium: 13800 }, { year: 2024, premium: 15200 }, { year: 2025, premium: 18400 }] },
  { id: 2, property: "88 Fenmore Industrial Park", type: "Property", carrier: "Chubb", premium: 41200, renewal: "2026-09-29",
    history: [{ year: 2021, premium: 24600 }, { year: 2022, premium: 27100 }, { year: 2023, premium: 29800 }, { year: 2024, premium: 33800 }, { year: 2025, premium: 41200 }] },
  { id: 3, property: "Sundale Apartments (64 units)", type: "Property", carrier: "Nationwide", premium: 27600, renewal: "2026-10-20",
    history: [{ year: 2021, premium: 19200 }, { year: 2022, premium: 21000 }, { year: 2023, premium: 23400 }, { year: 2024, premium: 26100 }, { year: 2025, premium: 27600 }] },
];

const today = new Date("2026-09-01");
const daysUntil = (d) => Math.round((new Date(d) - today) / 86400000);
const fmt = (n) => "$" + n.toLocaleString();

export default function InsuranceDashboard() {
  const [stage, setStage] = useState("dashboard"); // dashboard | uploading | review
  const [policies, setPolicies] = useState(existingPolicies);
  const [openHistory, setOpenHistory] = useState(null);

  function simulateUpload() {
    setStage("uploading");
    setTimeout(() => setStage("review"), 1100);
  }

  function confirmExtraction() {
    setPolicies((prev) => [
      ...prev,
      {
        id: prev.length + 1,
        property: harborCoveExtraction.property,
        type: "Property",
        carrier: "ICAT / Lloyd's",
        premium: harborCoveExtraction.totalPremium,
        renewal: "2027-02-22",
        history: harborCoveExtraction.history,
      },
    ]);
    setStage("dashboard");
  }

  return (
    <div style={{ fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", background: "#FAFAF7", color: "#1C2430", minHeight: "100vh", padding: "20px 16px 40px", maxWidth: 480, margin: "0 auto" }}>
      {stage === "dashboard" && (
        <Dashboard policies={policies} onUpload={simulateUpload} onOpenHistory={setOpenHistory} />
      )}
      {stage === "uploading" && <Uploading />}
      {stage === "review" && <Review data={harborCoveExtraction} onConfirm={confirmExtraction} onCancel={() => setStage("dashboard")} />}
      {openHistory && <HistoryModal policy={openHistory} onClose={() => setOpenHistory(null)} />}
    </div>
  );
}

function Dashboard({ policies, onUpload, onOpenHistory }) {
  const enriched = policies.map((p) => ({ ...p, days: daysUntil(p.renewal) })).sort((a, b) => a.days - b.days);
  const total = policies.reduce((s, p) => s + p.premium, 0);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 13, color: "#5B6472", marginBottom: 2 }}>Portfolio insurance</div>
          <div style={{ fontFamily: "Georgia, serif", fontSize: 24, fontWeight: 600 }}>{policies.length} policies</div>
        </div>
        <button onClick={onUpload} style={btnDark}>Upload policy</button>
      </div>

      <div style={{ background: "#FAFAF7", border: "1px solid #E4E1D8", padding: "14px 16px", marginBottom: 24 }}>
        <div style={{ fontSize: 12, color: "#5B6472", marginBottom: 4 }}>Total annual premium</div>
        <div style={{ fontFamily: "Georgia, serif", fontSize: 22 }}>{fmt(total)}</div>
      </div>

      <div style={{ fontSize: 13, fontWeight: 600, color: "#5B6472", marginBottom: 10 }}>All policies, by renewal date</div>
      {enriched.map((p) => (
        <div key={p.id} onClick={() => onOpenHistory(p)} style={row}>
          <div style={{ flex: 1, paddingRight: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>{p.property}</div>
            <div style={{ fontSize: 12.5, color: "#5B6472" }}>{p.type} · {p.carrier}</div>
          </div>
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <div style={{ fontFamily: "Georgia, serif", fontSize: 15 }}>{fmt(p.premium)}</div>
            <div style={{ fontSize: 11.5, color: "#5B6472" }}>View 5-yr trend →</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function Uploading() {
  return (
    <div style={{ textAlign: "center", padding: "80px 20px" }}>
      <div style={{ fontFamily: "Georgia, serif", fontSize: 18, marginBottom: 8 }}>Reading policy document…</div>
      <div style={{ fontSize: 13, color: "#5B6472" }}>Extracting declarations, premium, and coverage fields</div>
    </div>
  );
}

function Review({ data, onConfirm, onCancel }) {
  return (
    <div>
      <div style={{ fontSize: 13, color: "#5B6472", marginBottom: 2 }}>Review extracted fields</div>
      <div style={{ fontFamily: "Georgia, serif", fontSize: 20, marginBottom: 16 }}>{data.property}</div>

      <Line2 label="Named insured" value={data.namedInsured} />
      <Line2 label="Policy number" value={data.policyNumber} />
      <Line2 label="Carrier(s)" value={data.carrier} />
      <Line2 label="Broker" value={data.broker} />
      <Line2 label="Policy period" value={`${data.effectiveDate} → ${data.renewalDate}`} />
      <Line2 label="Term premium" value={fmt(data.termPremium)} />
      <Line2 label="Policy fee" value={fmt(data.policyFee)} />
      <Line2 label="Total premium" value={fmt(data.totalPremium)} tone="#1C2430" bold />
      <Line2 label="Limit of insurance" value={fmt(data.limitOfInsurance)} />

      <div style={{ fontSize: 13, fontWeight: 600, color: "#5B6472", margin: "16px 0 8px" }}>Deductibles by peril</div>
      {data.deductibles.map((d) => (
        <Line2 key={d.peril} label={d.peril} value={d.amount} />
      ))}

      <div style={{ fontSize: 12, color: "#5B6472", marginTop: 16, lineHeight: 1.5 }}>
        These fields were extracted automatically from the uploaded document. Confirm they look right before adding to your portfolio.
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
        <button onClick={onCancel} style={btnLight}>Cancel</button>
        <button onClick={onConfirm} style={{ ...btnDark, flex: 1 }}>Looks right — add to portfolio</button>
      </div>
    </div>
  );
}

function Line2({ label, value, tone, bold }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "9px 0", borderBottom: "1px solid #E4E1D8", fontSize: 13.5 }}>
      <span style={{ color: "#5B6472" }}>{label}</span>
      <span style={{ fontWeight: bold ? 700 : 600, color: tone || "#1C2430", textAlign: "right", marginLeft: 12 }}>{value}</span>
    </div>
  );
}

function HistoryModal({ policy, onClose }) {
  const h = policy.history || [];
  const first = h[0]?.premium ?? 0;
  const last = h[h.length - 1]?.premium ?? 0;
  const totalChange = first ? (((last - first) / first) * 100).toFixed(0) : 0;

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(28,36,48,0.4)", display: "flex", alignItems: "flex-end", zIndex: 10 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: "#FAFAF7", width: "100%", maxWidth: 480, margin: "0 auto", padding: "22px 18px 28px", borderTop: "1px solid #E4E1D8" }}>
        <div style={{ fontSize: 13, color: "#5B6472", marginBottom: 2 }}>5-year premium history</div>
        <div style={{ fontFamily: "Georgia, serif", fontSize: 18, marginBottom: 4 }}>{policy.property}</div>
        <div style={{ fontSize: 13, color: totalChange >= 0 ? "#B5432F" : "#2F6F62", marginBottom: 16 }}>
          {totalChange > 0 ? "+" : ""}{totalChange}% over {h.length} years
        </div>

        <div style={{ height: 180, marginBottom: 12 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={h} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="#E4E1D8" vertical={false} />
              <XAxis dataKey="year" tick={{ fontSize: 12, fill: "#5B6472" }} axisLine={{ stroke: "#E4E1D8" }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#5B6472" }} axisLine={false} tickLine={false} tickFormatter={(v) => "$" + Math.round(v / 1000) + "k"} />
              <Tooltip formatter={(v) => fmt(v)} contentStyle={{ fontSize: 12, border: "1px solid #E4E1D8", borderRadius: 0 }} />
              <Line type="monotone" dataKey="premium" stroke="#B5432F" strokeWidth={2} dot={{ r: 3, fill: "#B5432F" }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {h.map((y) => (
          <div key={y.year} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0", borderBottom: "1px solid #E4E1D8", fontSize: 13 }}>
            <span style={{ color: "#5B6472" }}>{y.year}{y.note ? ` · ${y.note}` : ""}</span>
            <span style={{ fontWeight: 600 }}>{fmt(y.premium)}</span>
          </div>
        ))}

        <button onClick={onClose} style={{ ...btnDark, width: "100%", marginTop: 18 }}>Close</button>
      </div>
    </div>
  );
}

const row = { display: "flex", justifyContent: "space-between", alignItems: "flex-start", padding: "12px 0", borderBottom: "1px solid #E4E1D8", cursor: "pointer" };
const btnDark = { padding: "10px 14px", background: "#1C2430", color: "#FAFAF7", border: "none", fontSize: 13, cursor: "pointer" };
const btnLight = { padding: "10px 14px", background: "transparent", color: "#1C2430", border: "1px solid #E4E1D8", fontSize: 13, cursor: "pointer" };
