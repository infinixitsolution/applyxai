interface Point {
  date: string;
  applied: number;
  failed: number;
}

/** Stacked daily bars (applied + failed). Plain SVG, no chart library. */
export function DailyChart({ data }: { data: Point[] }) {
  const max = Math.max(1, ...data.map((d) => d.applied + d.failed));
  const width = 600;
  const height = 160;
  const gap = 4;
  const bar = (width - gap * (data.length - 1)) / data.length;
  const total = data.reduce((sum, d) => sum + d.applied, 0);

  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height + 20}`} className="h-48 w-full" role="img"
           aria-label={`Applications over the last ${data.length} days: ${total} applied`}>
        {data.map((d, i) => {
          const x = i * (bar + gap);
          const appliedH = (d.applied / max) * height;
          const failedH = (d.failed / max) * height;
          return (
            <g key={d.date}>
              <title>{`${d.date}: ${d.applied} applied, ${d.failed} failed`}</title>
              <rect x={x} y={0} width={bar} height={height} fill="transparent" />
              <rect x={x} y={height - appliedH} width={bar} height={appliedH} rx={2} className="fill-brand-600" />
              <rect x={x} y={height - appliedH - failedH} width={bar} height={failedH} rx={2} className="fill-red-300" />
            </g>
          );
        })}
        <line x1={0} x2={width} y1={height} y2={height} className="stroke-slate-200" />
        {data.length > 0 && (
          <>
            <text x={0} y={height + 15} className="fill-slate-400 text-[11px]">{data[0].date.slice(5)}</text>
            <text x={width} y={height + 15} textAnchor="end" className="fill-slate-400 text-[11px]">
              {data[data.length - 1].date.slice(5)}
            </text>
          </>
        )}
      </svg>
      <figcaption className="mt-2 flex gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-brand-600" /> Applied</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-red-300" /> Failed</span>
      </figcaption>
    </figure>
  );
}
