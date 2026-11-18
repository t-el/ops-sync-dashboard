import type { SyncRun } from "./types";

export function money(cents: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(cents / 100);
}

/** Backend timestamps are UTC ISO strings ("...Z"); SQLite CURRENT_TIMESTAMP lacks the Z, so add it. */
export function parseUtc(ts: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(ts) ? ts : ts.replace(" ", "T") + "Z");
}

export function timeAgo(ts: string | null, now: Date = new Date()): string {
  if (!ts) return "never";
  const s = Math.max(0, Math.round((now.getTime() - parseUtc(ts).getTime()) / 1000));
  if (s < 10) return "just now";
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

export function duration(run: Pick<SyncRun, "started_at" | "finished_at">): string {
  if (!run.finished_at) return "…";
  const ms = parseUtc(run.finished_at).getTime() - parseUtc(run.started_at).getTime();
  return ms < 1000 ? `${Math.max(0, ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function successRate(ok: number, failed: number): string {
  const total = ok + failed;
  return total === 0 ? "–" : `${Math.round((ok / total) * 100)}%`;
}

export type Health = "healthy" | "degraded" | "down" | "syncing" | "unknown";

/** A source is "down" if its last run failed, "degraded" if the last success is stale. */
export function sourceHealth(lastRun: SyncRun | null, lastSuccessAt: string | null, staleAfterMs = 2 * 3600_000, now = new Date()): Health {
  if (!lastRun) return "unknown";
  if (lastRun.status === "running") return "syncing";
  if (lastRun.status === "failed") return "down";
  if (lastSuccessAt && now.getTime() - parseUtc(lastSuccessAt).getTime() > staleAfterMs) return "degraded";
  return "healthy";
}

export const SOURCE_LABELS: Record<string, string> = { stripe: "Stripe payments", helpdesk: "Help desk tickets" };
