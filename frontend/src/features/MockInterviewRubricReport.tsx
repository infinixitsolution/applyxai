import { ChevronDown, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge, cx } from "../components/ui";
import type { MockInterviewFeedback, MockInterviewRubricScore } from "../types";

function ScoreMini({ score }: { score: number | null | undefined }) {
  if (score == null) {
    return <Badge tone="slate">N/A</Badge>;
  }
  const tone = score >= 70 ? "green" : score >= 45 ? "blue" : score >= 20 ? "amber" : "red";
  return <Badge tone={tone}>{`${score}/100`}</Badge>;
}

function CategoryBlock({
  label,
  average,
  parameters,
  defaultOpen,
}: {
  label: string;
  average: number | null | undefined;
  parameters: MockInterviewRubricScore[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  const scored = parameters.filter((p) => p.score != null).length;

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
          {scored}/10 scored
          {average != null && <span className="font-mono font-medium text-slate-700">avg {average}</span>}
        </span>
      </button>
      {open && (
        <ul className="divide-y divide-slate-100 border-t border-slate-100 px-2 pb-2">
          {parameters.map((p) => (
            <li key={p.id} className="flex flex-col gap-1 px-2 py-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-800">
                  <span className="text-slate-400">{p.id}.</span> {p.label}
                </p>
                {p.notes && <p className="mt-0.5 text-xs text-slate-500">{p.notes}</p>}
              </div>
              <div className="shrink-0 pt-0.5">
                <ScoreMini score={p.score} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function MockInterviewRubricReport({ feedback, embedded }: { feedback: MockInterviewFeedback; embedded?: boolean }) {
  const scores = feedback.rubric_scores ?? [];
  const categories = feedback.rubric_categories ?? [];

  const byCategory = useMemo(() => {
    const map = new Map<string, MockInterviewRubricScore[]>();
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

  if (!scores.length) return null;

  return (
    <div className={embedded ? "space-y-3" : "mb-6 space-y-3"}>
      {!embedded && (
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold text-slate-900">100-parameter analysis</h2>
            <p className="text-sm text-slate-600">
              Evidence-based scores from your transcript. N/A means the interview did not cover that signal.
            </p>
          </div>
          {feedback.rubric_overall != null && (
            <p className={cx("rounded-lg bg-brand-50 px-3 py-1.5 text-sm font-semibold text-brand-800")}>
              Rubric average (scored items): {feedback.rubric_overall}/100
            </p>
          )}
        </div>
      )}
      {embedded && feedback.rubric_overall != null && (
        <p className="text-sm text-slate-600">
          Rubric average (scored items):{" "}
          <span className="font-semibold text-brand-800">{feedback.rubric_overall}/100</span>. N/A = not evidenced in
          this session.
        </p>
      )}
      <div className="space-y-2">
        {categories.map((cat, i) => (
          <CategoryBlock
            key={cat.category_id}
            label={cat.category_label}
            average={cat.average_score}
            parameters={byCategory.get(cat.category_id) ?? []}
            defaultOpen={i === 0}
          />
        ))}
      </div>
    </div>
  );
}
