import type { AtRisk, Summary, SyncRun, Ticket } from "./types";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { cache: "no-store", ...init });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  summary: () => json<Summary>("/api/summary"),
  runs: () => json<SyncRun[]>("/api/runs?limit=25"),
  tickets: () => json<Ticket[]>("/api/tickets?open_only=true&limit=8"),
  atRisk: () => json<AtRisk[]>("/api/insights/at-risk"),
  syncNow: (source?: string) => json<{ started: { source: string; run_id: number }[] }>(`/api/sync${source ? `?source=${source}` : ""}`, { method: "POST" }),
  retry: (runId: number) => json<{ run_id: number }>(`/api/runs/${runId}/retry`, { method: "POST" }),
};
