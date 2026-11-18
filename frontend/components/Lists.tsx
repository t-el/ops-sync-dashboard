import { timeAgo } from "@/lib/format";
import type { AtRisk, Ticket } from "@/lib/types";

export function TicketsList({ tickets }: { tickets: Ticket[] }) {
  if (!tickets.length) return <p className="muted">No open tickets 🎉</p>;
  return (
    <ul className="list">
      {tickets.map((t) => (
        <li key={t.id}>
          <span className={`prio prio-${t.priority}`}>{t.priority}</span>
          <span className="grow">{t.subject}<span className="muted small"> · {t.requester_email}</span></span>
          <span className="muted small">{timeAgo(new Date(t.updated_at * 1000).toISOString())}</span>
        </li>
      ))}
    </ul>
  );
}

export function AtRiskList({ items }: { items: AtRisk[] }) {
  if (!items.length) return <p className="muted">No customers at risk right now.</p>;
  return (
    <ul className="list">
      {items.map((c) => (
        <li key={c.email}>
          <span className="grow"><b>{c.email}</b></span>
          <span className="chip chip-bad">{c.failed_payments} failed payment{c.failed_payments > 1 ? "s" : ""}</span>
          <span className={`chip ${c.has_urgent ? "chip-bad" : ""}`}>{c.open_tickets} open ticket{c.open_tickets > 1 ? "s" : ""}{c.has_urgent ? " · urgent" : ""}</span>
        </li>
      ))}
    </ul>
  );
}
