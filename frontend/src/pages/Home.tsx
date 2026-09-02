import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type ReactNode,
} from "react";
import { Link, Navigate } from "react-router-dom";
import {
  ApiError,
  getDocument,
  listDocuments,
  uploadDocuments,
  type DocumentJob,
  type ExtractedPolicy,
} from "../api";
import { useAuth } from "../auth";

const POLL_MS = 2000;

function Shell({
  children,
  onLogout,
}: {
  children: ReactNode;
  onLogout?: () => void;
}) {
  return (
    <div className="app-shell">
      <aside className="app-nav">
        <p className="app-brand">Insurance Tracker</p>
        <nav aria-label="Main">
          <ul className="app-nav-list">
            <li>
              <Link to="/" aria-current="page">
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

function mergeJobs(
  current: DocumentJob[],
  incoming: DocumentJob[],
): DocumentJob[] {
  const byId = new Map(current.map((job) => [job.id, job]));
  for (const job of incoming) {
    byId.set(job.id, job);
  }
  return [...byId.values()].sort((a, b) =>
    a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : 0,
  );
}

function formatConfidence(value: number | undefined): string {
  if (value === undefined) {
    return "";
  }
  return `${Math.round(value * 100)}%`;
}

function ScalarField({
  label,
  value,
  confidence,
}: {
  label: string;
  value: string | null | undefined;
  confidence: number | undefined;
}) {
  return (
    <div className="extracted-field">
      <dt>
        {label}
        <span className="confidence">{formatConfidence(confidence)}</span>
      </dt>
      <dd>{value ?? "—"}</dd>
    </div>
  );
}

function ExtractedFields({ extracted }: { extracted: ExtractedPolicy }) {
  return (
    <div className="extracted">
      <dl className="extracted-grid">
        <ScalarField
          label="Policy number"
          value={extracted.policy_number}
          confidence={extracted.confidence.policy_number}
        />
        <ScalarField
          label="Named insured"
          value={extracted.named_insured}
          confidence={extracted.confidence.named_insured}
        />
        <ScalarField
          label="Broker"
          value={extracted.broker}
          confidence={extracted.confidence.broker}
        />
        <ScalarField
          label="Effective"
          value={extracted.effective_date}
          confidence={extracted.confidence.effective_date}
        />
        <ScalarField
          label="Renewal"
          value={extracted.renewal_date}
          confidence={extracted.confidence.renewal_date}
        />
        <ScalarField
          label="Term premium"
          value={extracted.term_premium}
          confidence={extracted.confidence.term_premium}
        />
        <ScalarField
          label="Policy fee"
          value={extracted.policy_fee}
          confidence={extracted.confidence.policy_fee}
        />
        <ScalarField
          label="Total premium"
          value={extracted.total_premium}
          confidence={extracted.confidence.total_premium}
        />
        <ScalarField
          label="Limit"
          value={extracted.limit_of_insurance}
          confidence={extracted.confidence.limit_of_insurance}
        />
        <ScalarField
          label="Coverage"
          value={extracted.coverage_type}
          confidence={extracted.confidence.coverage_type}
        />
      </dl>
      <h3>
        Carriers
        <span className="confidence">
          {formatConfidence(extracted.confidence.carriers)}
        </span>
      </h3>
      {extracted.carriers.length === 0 ? (
        <p className="muted">None extracted</p>
      ) : (
        <ul>
          {extracted.carriers.map((carrier) => (
            <li key={carrier}>{carrier}</li>
          ))}
        </ul>
      )}
      <h3>
        Deductibles
        <span className="confidence">
          {formatConfidence(extracted.confidence.deductibles)}
        </span>
      </h3>
      {extracted.deductibles.length === 0 ? (
        <p className="muted">None extracted</p>
      ) : (
        <ul>
          {extracted.deductibles.map((item, index) => (
            <li key={`${item.peril ?? "peril"}-${index}`}>
              {item.peril ?? "Peril"}: {item.amount ?? "—"}
            </li>
          ))}
        </ul>
      )}
      <h3>
        Locations
        <span className="confidence">
          {formatConfidence(extracted.confidence.locations)}
        </span>
      </h3>
      {extracted.locations.length === 0 ? (
        <p className="muted">None extracted</p>
      ) : (
        <ul>
          {extracted.locations.map((item, index) => (
            <li key={`${item.label ?? "location"}-${index}`}>
              {item.label ?? "Location"}
              {item.address ? ` — ${item.address}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function JobCard({ job }: { job: DocumentJob }) {
  return (
    <article className="job-card">
      <header className="job-card-header">
        <h2>{job.original_filename}</h2>
        <p className={`job-status job-status-${job.status}`}>{job.status}</p>
      </header>
      {job.status === "failed" ? (
        <p className="error">{job.error_message ?? "Extraction failed."}</p>
      ) : null}
      {job.status === "completed" && job.extracted ? (
        <ExtractedFields extracted={job.extracted} />
      ) : null}
      {job.status === "pending" || job.status === "processing" ? (
        <p className="muted">Extracting policy fields…</p>
      ) : null}
    </article>
  );
}

export function Home() {
  const { user, loading, logout } = useAuth();
  const [jobs, setJobs] = useState<DocumentJob[]>([]);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;
    void listDocuments()
      .then((data) => {
        if (!cancelled) {
          setJobs(data.items);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "Unable to load documents.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const inflightIds = jobs
    .filter((job) => job.status === "pending" || job.status === "processing")
    .map((job) => job.id)
    .sort()
    .join(",");

  useEffect(() => {
    if (!inflightIds) {
      return;
    }
    const ids = inflightIds.split(",");
    let cancelled = false;
    const poll = async () => {
      try {
        const updated = await Promise.all(ids.map((id) => getDocument(id)));
        if (!cancelled) {
          setJobs((current) => mergeJobs(current, updated));
        }
      } catch {
        // Keep showing the last known job state; the next tick retries.
      }
    };
    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [inflightIds]);

  async function handleFiles(fileList: FileList | File[]): Promise<void> {
    const files = [...fileList].filter(
      (file) => file.type === "application/pdf",
    );
    if (files.length === 0) {
      setError("Upload a PDF file.");
      return;
    }
    setError("");
    setUploading(true);
    try {
      const data = await uploadDocuments(files);
      setJobs((current) => mergeJobs(current, data.items));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to upload.");
    } finally {
      setUploading(false);
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>): void {
    event.preventDefault();
    setDragOver(false);
    if (event.dataTransfer.files.length > 0) {
      void handleFiles(event.dataTransfer.files);
    }
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>): void {
    if (event.target.files && event.target.files.length > 0) {
      void handleFiles(event.target.files);
      event.target.value = "";
    }
  }

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

  return (
    <Shell onLogout={logout}>
      <h1>Your insurance portfolio</h1>
      <p className="lede">
        Drop in a policy PDF to extract structured fields. Confirming into the
        portfolio comes next.
      </p>
      <p className="muted">{user.email}</p>
      <label
        className={dragOver ? "dropzone dropzone-active" : "dropzone"}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          className="file-input"
          type="file"
          accept="application/pdf"
          multiple
          aria-label="Drop PDFs here or choose files"
          onChange={onInputChange}
        />
        <span>
          {uploading ? "Uploading…" : "Drop PDFs here or choose files"}
        </span>
      </label>
      {error ? <p className="error">{error}</p> : null}
      {jobs.length === 0 ? (
        <p className="muted">No documents uploaded yet.</p>
      ) : (
        <section aria-label="Uploaded documents" className="job-list">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </section>
      )}
    </Shell>
  );
}
