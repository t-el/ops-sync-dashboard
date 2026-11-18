import { duration, timeAgo } from "@/lib/format";

const SHORT: Record<string, string> = { stripe: "Stripe", helpdesk: "Help desk" };
import type { SyncRun } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

export function RunsTable({ runs, onRetry, retrying }: { runs: SyncRun[]; onRetry: (id: number) => void; retrying: number | null }) {
  if (!runs.length) return <p className="muted">No sync runs yet. Click “Sync now”.</p>;
  // a failed run that already has a successful retry shows a link to it instead of another Retry button
  const recoveredBy = new Map(runs.filter((r) => r.retry_of && r.status === "success").map((r) => [r.retry_of as number, r.id]));
  return (
    <table className="runs">
      <thead>
        <tr>
          <th>#</th><th>Source</th><th>Status</th><th>Trigger</th><th>Records</th><th>Attempts</th><th>Duration</th><th>Started</th><th>Details</th><th />
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.id} className={r.status === "failed" ? "row-failed" : undefined}>
            <td className="muted">{r.id}</td>
            <td>{SHORT[r.source] ?? r.source}</td>
            <td><StatusBadge status={r.status} /></td>
            <td><span className="chip">{r.trigger}{r.retry_of ? ` of #${r.retry_of}` : ""}</span></td>
            <td>{r.records}</td>
            <td className={r.attempts > 1 ? "warn-text" : undefined}>{r.attempts}</td>
            <td>{duration(r)}</td>
            <td className="muted">{timeAgo(r.started_at)}</td>
            <td className="error-cell" title={r.error ?? ""}>{r.error ?? ""}</td>
            <td>
              {r.status === "failed" && recoveredBy.has(r.id) && <span className="chip">✓ fixed by #{recoveredBy.get(r.id)}</span>}
              {r.status === "failed" && !recoveredBy.has(r.id) && (
                <button className="btn btn-small" disabled={retrying === r.id} onClick={() => onRetry(r.id)}>
                  {retrying === r.id ? "Retrying…" : "Retry"}
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
