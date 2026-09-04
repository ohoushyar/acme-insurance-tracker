import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { Link, Navigate } from "react-router-dom";
import {
  ApiError,
  getDocument,
  listDocuments,
  uploadDocuments,
  type DocumentJob,
} from "../api";
import { useAuth } from "../auth";
import { Shell } from "../components/Shell";

const POLL_MS = 2000;

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

function jobSummary(job: DocumentJob): {
  namedInsured: string | null;
  policyNumber: string | null;
} {
  return {
    namedInsured: job.extracted?.named_insured ?? null,
    policyNumber: job.extracted?.policy_number ?? null,
  };
}

function JobCard({ job }: { job: DocumentJob }) {
  const canReview =
    (job.status === "completed" || job.status === "reviewed") &&
    job.extracted !== null;
  const summary = jobSummary(job);
  return (
    <article className="job-card">
      <header className="job-card-header">
        <h2>{job.original_filename}</h2>
        <p className={`job-status job-status-${job.status}`}>{job.status}</p>
      </header>
      {job.status === "failed" ? (
        <p className="error">{job.error_message ?? "Extraction failed."}</p>
      ) : null}
      {job.status === "pending" || job.status === "processing" ? (
        <p className="muted">Extracting policy fields…</p>
      ) : null}
      {canReview ? (
        <>
          {summary.namedInsured || summary.policyNumber ? (
            <p className="job-summary">
              {summary.namedInsured ? (
                <span>{summary.namedInsured}</span>
              ) : null}
              {summary.namedInsured && summary.policyNumber ? " · " : null}
              {summary.policyNumber ? (
                <span>{summary.policyNumber}</span>
              ) : null}
            </p>
          ) : null}
          <Link to={`/documents/${job.id}/review`}>
            Review extracted fields
          </Link>
        </>
      ) : null}
    </article>
  );
}

export function Uploads() {
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
      .then((documents) => {
        if (!cancelled) {
          setJobs(documents.items);
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
      <h1>Uploads</h1>
      <p className="lede">
        Drop in a policy PDF to extract structured fields. Confirm a review to
        save the policy into your portfolio.
      </p>
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
      {jobs.length === 0 && !error ? (
        <p className="muted">No documents uploaded yet.</p>
      ) : null}
      {jobs.length > 0 ? (
        <section aria-label="Uploaded documents" className="job-list">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </section>
      ) : null}
    </Shell>
  );
}
