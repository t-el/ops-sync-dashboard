export type RunStatus = "running" | "success" | "failed";

export interface SyncRun {
  id: number;
  source: string;
  trigger: "manual" | "scheduled" | "retry";
  status: RunStatus;
  attempts: number;
  records: number;
  error: string | null;
  retry_of: number | null;
  started_at: string;
  finished_at: string | null;
}

export interface SourceStatus {
  name: string;
  last_run: SyncRun | null;
  last_success_at: string | null;
  success_count: number;
  failure_count: number;
}

export interface Summary {
  revenue_30d_cents: number;
  payments_30d: number;
  failed_payments_30d: number;
  failed_amount_30d_cents: number;
  refunds_30d: number;
  open_tickets: number;
  pending_tickets: number;
  urgent_tickets: number;
  total_tickets: number;
  daily_revenue: { day: string; cents: number }[];
  sources: SourceStatus[];
}

export interface Ticket {
  id: number;
  subject: string;
  status: string;
  priority: "low" | "normal" | "high" | "urgent";
  requester_email: string;
  updated_at: number;
}

export interface AtRisk {
  email: string;
  failed_payments: number;
  open_tickets: number;
  has_urgent: number;
}
