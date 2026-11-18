import { SOURCE_LABELS, sourceHealth, successRate, timeAgo } from "@/lib/format";
import type { SourceStatus } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

export function SourceCard({ source, onSync, busy }: { source: SourceStatus; onSync: (name: string) => void; busy: boolean }) {
  const health = sourceHealth(source.last_run, source.last_success_at);
  return (
    <div className="card source">
      <div className="source-head">
        <div>
          <div className="source-name">{SOURCE_LABELS[source.name] ?? source.name}</div>
          <div className="muted small">Last success {timeAgo(source.last_success_at)}</div>
        </div>
        <StatusBadge status={health} />
      </div>
      <div className="source-stats">
        <div><span className="muted small">Success rate</span><b>{successRate(source.success_count, source.failure_count)}</b></div>
        <div><span className="muted small">Runs OK / failed</span><b>{source.success_count} / {source.failure_count}</b></div>
        <div><span className="muted small">Last run records</span><b>{source.last_run?.records ?? "–"}</b></div>
      </div>
      {source.last_run?.status === "failed" && <div className="error-line" title={source.last_run.error ?? ""}>{source.last_run.error}</div>}
      <button className="btn btn-ghost" disabled={busy || health === "syncing"} onClick={() => onSync(source.name)}>
        Sync {source.name} now
      </button>
    </div>
  );
}
