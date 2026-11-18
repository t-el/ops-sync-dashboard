"use client";

import { useCallback, useEffect, useState } from "react";
import { KpiCard } from "@/components/KpiCard";
import { AtRiskList, TicketsList } from "@/components/Lists";
import { RevenueChart } from "@/components/RevenueChart";
import { RunsTable } from "@/components/RunsTable";
import { SourceCard } from "@/components/SourceCard";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import type { AtRisk, Summary, SyncRun, Ticket } from "@/lib/types";

const POLL_MS = 4000;

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [atRisk, setAtRisk] = useState<AtRisk[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [retrying, setRetrying] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, r, t, a] = await Promise.all([api.summary(), api.runs(), api.tickets(), api.atRisk()]);
      setSummary(s); setRuns(r); setTickets(t); setAtRisk(a); setError(null);
    } catch (e) {
      setError(`Backend unreachable: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  const flash = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  const syncNow = async (source?: string) => {
    setBusy(true);
    try {
      const r = await api.syncNow(source);
      flash(`Started ${r.started.map((s) => s.source).join(" + ")} sync`);
    } catch (e) {
      flash((e as Error).message);
    } finally {
      setBusy(false);
      setTimeout(load, 600);
    }
  };

  const retry = async (id: number) => {
    setRetrying(id);
    try {
      const r = await api.retry(id);
      flash(`Retry started as run #${r.run_id}`);
    } catch (e) {
      flash((e as Error).message);
    } finally {
      setRetrying(null);
      setTimeout(load, 600);
    }
  };

  const anyRunning = runs.some((r) => r.status === "running");
  const recovered = new Set(runs.filter((r) => r.retry_of && r.status === "success").map((r) => r.retry_of));
  const failedRuns = runs.filter((r) => r.status === "failed" && !recovered.has(r.id)).length;

  return (
    <main className="wrap">
      <header className="top">
        <div>
          <h1>Ops Sync</h1>
          <p className="muted">Payments and support in one view, synced every 15 minutes, with every run accounted for.</p>
        </div>
        <button className="btn" onClick={() => syncNow()} disabled={busy || anyRunning}>
          {anyRunning ? "Syncing…" : "⟳ Sync now"}
        </button>
      </header>

      {error && <div className="banner banner-bad">{error}</div>}
      {toast && <div className="toast">{toast}</div>}

      {summary && (
        <>
          <section className="grid kpis">
            <KpiCard label="Revenue (30d)" value={money(summary.revenue_30d_cents)} hint={`${summary.payments_30d} successful payments`} tone="good" />
            <KpiCard label="Failed payments (30d)" value={String(summary.failed_payments_30d)} hint={`${money(summary.failed_amount_30d_cents)} at risk`} tone={summary.failed_payments_30d ? "bad" : "neutral"} />
            <KpiCard label="Open tickets" value={String(summary.open_tickets + summary.pending_tickets)} hint={`${summary.urgent_tickets} urgent · ${summary.pending_tickets} pending`} tone={summary.urgent_tickets ? "warn" : "neutral"} />
            <KpiCard label="Sync health" value={failedRuns ? `${failedRuns} failed` : "All good"} hint={`last ${runs.length} runs · failures needing action`} tone={failedRuns ? "bad" : "good"} />
          </section>

          <section className="grid sources">
            {summary.sources.map((s) => <SourceCard key={s.name} source={s} onSync={syncNow} busy={busy} />)}
          </section>

          <section className="grid two">
            <div className="card">
              <h2>Daily revenue</h2>
              <RevenueChart data={summary.daily_revenue} />
            </div>
            <div className="card">
              <h2>At-risk customers <span className="muted small">failed payment + open ticket</span></h2>
              <AtRiskList items={atRisk} />
            </div>
          </section>
        </>
      )}

      <section className="grid two-wide">
        <div className="card">
          <h2>Sync runs</h2>
          <RunsTable runs={runs} onRetry={retry} retrying={retrying} />
        </div>
        <div className="card">
          <h2>Open tickets</h2>
          <TicketsList tickets={tickets} />
        </div>
      </section>
      <footer className="muted small">Ops Sync v1.0 · data refreshes every {POLL_MS / 1000}s</footer>
    </main>
  );
}
