import { ChevronDown, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge, cx } from "../components/ui";
import type { MockInterviewBehaviorParameter, MockInterviewFeedback } from "../types";

function StatusBadge({ row }: { row: MockInterviewBehaviorParameter }) {
  if (row.status === "concern" || row.detected) {
    return <Badge tone="red">Concern</Badge>;
  }
  if (row.status === "not_observable" || row.status === "na") {
    return <Badge tone="slate">Not observable</Badge>;
  }
  if (row.score != null) {
    const tone = row.score >= 70 ? "green" : row.score >= 45 ? "blue" : row.score >= 20 ? "amber" : "red";
    return <Badge tone={tone}>{`${row.score}/100`}</Badge>;
  }
  return <Badge tone="slate">—</Badge>;
}

function CategoryBlock({
  label,
  average,
  concerns,
  parameters,
  defaultOpen,
}: {
  label: string;
  average: number | null | undefined;
  concerns: number;
  parameters: MockInterviewBehaviorParameter[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  return (
    <div className="rounded-xl border border-slate-100">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          {open ? <ChevronDown className="h-4 w-4" aria-hidden /> : <ChevronRight className="h-4 w-4" aria-hidden />}
          {label}
        </span>
        <span className="flex items-center gap-2 text-xs text-slate-500">
          {concerns > 0 && <Badge tone="red">{concerns} concern{concerns === 1 ? "" : "s"}</Badge>}
          {average != null && <span className="font-mono font-medium text-slate-700">avg {average}</span>}
        </span>
      </button>
      {open && (
        <div className="overflow-x-auto border-t border-slate-100">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 font-semibold">#</th>
                <th className="px-3 py-2 font-semibold">Parameter</th>
                <th className="px-3 py-2 font-semibold">Status</th>
                <th className="px-3 py-2 font-semibold">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {parameters.map((p) => (
                <tr key={p.id} className={cx(p.detected || p.status === "concern" ? "bg-red-50/40" : undefined)}>
                  <td className="px-3 py-2 font-mono text-slate-400">{p.id}</td>
                  <td className="px-3 py-2 font-medium text-slate-800">{p.label}</td>
                  <td className="px-3 py-2">
                    <StatusBadge row={p} />
                  </td>
                  <td className="max-w-md px-3 py-2 text-slate-600">{p.notes || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function MockInterviewBehaviorReport({ feedback }: { feedback: MockInterviewFeedback }) {
  const presentation = feedback.presentation;
  const scores = presentation?.behavioral_parameters ?? [];
  const categories = presentation?.behavior_categories ?? [];

  const byCategory = useMemo(() => {
    const map = new Map<string, MockInterviewBehaviorParameter[]>();
    for (const row of scores) {
      const list = map.get(row.category_id) ?? [];
      list.push(row);
      map.set(row.category_id, list);
    }
    for (const [, list] of map) {
      list.sort((a, b) => a.id - b.id);
    }
    return map;
  }, [scores]);

  if (!scores.length) {
    return (
      <p className="text-sm text-slate-500">
        No on-camera behavioral analysis yet. Complete a session with your camera enabled, then end the interview to
        analyze snapshots.
      </p>
    );
  }

  const concernCount = scores.filter((r) => r.detected || r.status === "concern").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
        {presentation?.behavior_overall != null && (
          <span>
            Behavioral average:{" "}
            <strong className="font-mono text-slate-900">{presentation.behavior_overall}/100</strong>
          </span>
        )}
        {concernCount > 0 && (
          <Badge tone="red">
            {concernCount} parameter{concernCount === 1 ? "" : "s"} flagged
          </Badge>
        )}
        <span className="text-xs text-slate-400">From periodic camera snapshots (not continuous video).</span>
      </div>
      {categories.map((cat, i) => {
        const params = byCategory.get(cat.category_id) ?? [];
        if (!params.length) return null;
        return (
          <CategoryBlock
            key={cat.category_id}
            label={cat.category_label}
            average={cat.average_score}
            concerns={cat.concerns_detected ?? 0}
            parameters={params}
            defaultOpen={i < 2 || (cat.concerns_detected ?? 0) > 0}
          />
        );
      })}
    </div>
  );
}
