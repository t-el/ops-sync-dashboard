import { money } from "@/lib/format";

/** Dependency-free bar chart (SVG) of daily revenue. */
export function RevenueChart({ data }: { data: { day: string; cents: number }[] }) {
  if (!data.length) return <p className="muted">No revenue synced yet.</p>;
  const max = Math.max(...data.map((d) => d.cents));
  const w = 720, h = 170, gap = 4;
  const bw = (w - gap * (data.length - 1)) / data.length;
  return (
    <svg viewBox={`0 0 ${w} ${h + 22}`} className="chart" role="img" aria-label="Daily revenue, last 30 days">
      {data.map((d, i) => {
        const bh = Math.max(2, (d.cents / max) * h);
        return (
          <g key={d.day}>
            <rect x={i * (bw + gap)} y={h - bh} width={bw} height={bh} rx={3} className="bar">
              <title>{`${d.day}: ${money(d.cents)}`}</title>
            </rect>
            {i % 5 === 0 && <text x={i * (bw + gap)} y={h + 16} className="axis">{d.day.slice(5)}</text>}
          </g>
        );
      })}
    </svg>
  );
}
