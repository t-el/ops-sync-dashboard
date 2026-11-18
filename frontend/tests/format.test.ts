import { describe, expect, it } from "vitest";
import { duration, money, parseUtc, sourceHealth, successRate, timeAgo } from "@/lib/format";
import type { SyncRun } from "@/lib/types";

const run = (o: Partial<SyncRun>): SyncRun => ({
  id: 1, source: "stripe", trigger: "manual", status: "success", attempts: 1, records: 10, error: null, retry_of: null,
  started_at: "2026-11-18T10:00:00Z", finished_at: "2026-11-18T10:00:02.500Z", ...o,
});

describe("format", () => {
  it("formats money from cents", () => expect(money(1234500)).toBe("$12,345"));
  it("parses SQLite timestamps as UTC", () => expect(parseUtc("2026-11-18 10:00:00").toISOString()).toBe("2026-11-18T10:00:00.000Z"));
  it("renders relative times", () => {
    const now = new Date("2026-11-18T12:00:00Z");
    expect(timeAgo("2026-11-18T11:58:00Z", now)).toBe("2 min ago");
    expect(timeAgo("2026-11-18T09:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo(null, now)).toBe("never");
  });
  it("computes run duration", () => {
    expect(duration(run({}))).toBe("2.5 s");
    expect(duration(run({ finished_at: null }))).toBe("…");
  });
  it("computes success rate", () => {
    expect(successRate(3, 1)).toBe("75%");
    expect(successRate(0, 0)).toBe("–");
  });
});

describe("sourceHealth", () => {
  const now = new Date("2026-11-18T12:00:00Z");
  it("is down when the last run failed", () => expect(sourceHealth(run({ status: "failed" }), "2026-11-18T11:00:00Z", undefined, now)).toBe("down"));
  it("is syncing while running", () => expect(sourceHealth(run({ status: "running" }), null, undefined, now)).toBe("syncing"));
  it("is degraded when the last success is stale", () => expect(sourceHealth(run({}), "2026-11-18T06:00:00Z", undefined, now)).toBe("degraded"));
  it("is healthy otherwise", () => expect(sourceHealth(run({}), "2026-11-18T11:50:00Z", undefined, now)).toBe("healthy"));
  it("is unknown before the first run", () => expect(sourceHealth(null, null)).toBe("unknown"));
});
