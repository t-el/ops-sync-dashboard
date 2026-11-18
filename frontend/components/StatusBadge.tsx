const LABELS: Record<string, string> = {
  success: "Success", failed: "Failed", running: "Running", healthy: "Healthy", degraded: "Stale", down: "Failing",
  syncing: "Syncing", unknown: "No runs yet",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge badge-${status}`} data-testid={`badge-${status}`}>
      <span className="dot" />
      {LABELS[status] ?? status}
    </span>
  );
}
