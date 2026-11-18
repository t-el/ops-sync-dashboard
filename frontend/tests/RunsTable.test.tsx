import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RunsTable } from "@/components/RunsTable";
import type { SyncRun } from "@/lib/types";

const base: SyncRun = {
  id: 1, source: "stripe", trigger: "scheduled", status: "success", attempts: 1, records: 140, error: null, retry_of: null,
  started_at: "2026-11-18T10:00:00Z", finished_at: "2026-11-18T10:00:01Z",
};

describe("RunsTable", () => {
  it("shows a Retry button only on failed runs and calls onRetry with the run id", () => {
    const onRetry = vi.fn();
    render(
      <RunsTable
        runs={[base, { ...base, id: 2, source: "helpdesk", status: "failed", attempts: 3, error: "helpdesk HTTP 503 (after 3 attempts)" }]}
        onRetry={onRetry}
        retrying={null}
      />,
    );
    const buttons = screen.getAllByRole("button", { name: "Retry" });
    expect(buttons).toHaveLength(1);
    fireEvent.click(buttons[0]);
    expect(onRetry).toHaveBeenCalledWith(2);
    expect(screen.getByText("helpdesk HTTP 503 (after 3 attempts)")).toBeInTheDocument();
    expect(screen.getByTestId("badge-failed")).toBeInTheDocument();
  });

  it("disables the button while a retry is in flight", () => {
    render(<RunsTable runs={[{ ...base, status: "failed" }]} onRetry={() => {}} retrying={1} />);
    expect(screen.getByRole("button", { name: "Retrying…" })).toBeDisabled();
  });

  it("replaces Retry with a link once a retry succeeded", () => {
    render(
      <RunsTable
        runs={[{ ...base, id: 5, trigger: "retry", retry_of: 4 }, { ...base, id: 4, status: "failed", error: "503" }]}
        onRetry={() => {}}
        retrying={null}
      />,
    );
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.getByText("✓ fixed by #5")).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<RunsTable runs={[]} onRetry={() => {}} retrying={null} />);
    expect(screen.getByText(/No sync runs yet/)).toBeInTheDocument();
  });
});
