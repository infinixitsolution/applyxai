import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { TextInput } from "../components/form";
import { useToast } from "../components/Toast";
import { Alert, Badge, Button, Card } from "../components/ui";
import { errorMessage } from "../services/api";
import { preferences } from "../services/endpoints";
import type { PendingFormQuestion } from "../types";

export function LinkedInCapturedQuestions({ items }: { items: PendingFormQuestion[] }) {
  const toast = useToast();
  const client = useQueryClient();
  const sorted = useMemo(
    () =>
      [...items].sort((a, b) => {
        if (a.needs_answer !== b.needs_answer) return a.needs_answer ? -1 : 1;
        return (b.last_seen_at ?? "").localeCompare(a.last_seen_at ?? "");
      }),
    [items],
  );
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const save = useMutation({
    mutationFn: () =>
      preferences.resolvePending({
        answers: sorted
          .filter((q) => q.needs_answer && (answers[q.id] ?? "").trim())
          .map((q) => ({ id: q.id, answer: (answers[q.id] ?? "").trim() })),
      }),
    onSuccess: () => {
      toast.success("Saved — these answers are used as custom rules on the next run.");
      setAnswers({});
      void client.invalidateQueries({ queryKey: ["preferences", "application"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!sorted.length) {
    return (
      <Card title="LinkedIn questions from auto apply">
        <p className="text-sm text-slate-600">
          When you run automation, every form question LinkedIn shows is recorded here so you can answer once and reuse
          it next time.
        </p>
      </Card>
    );
  }

  const needCount = sorted.filter((q) => q.needs_answer).length;
  const canSave = sorted.some((q) => q.needs_answer && (answers[q.id] ?? "").trim().length > 0);

  return (
    <Card
      title="LinkedIn questions from auto apply"
      actions={
        needCount > 0 ? (
          <Badge tone="amber">{needCount} need an answer</Badge>
        ) : (
          <Badge tone="green">All caught up</Badge>
        )
      }
    >
      <p className="mb-4 text-sm text-slate-600">
        Questions seen during past runs. Save an answer to add a custom rule (used before AI). Fixed screening answers
        still take priority.
      </p>
      {needCount > 0 && (
        <Alert kind="info">
          Turn on <strong>AI assistance</strong> below to auto-fill one-off questions; save answers here for ones you
          want to reuse every time.
        </Alert>
      )}
      <ul className="mt-4 max-h-[min(520px,55vh)] space-y-3 overflow-y-auto pr-1">
        {sorted.map((q) => (
          <li
            key={q.id}
            className={`rounded-lg border p-4 ${q.needs_answer ? "border-amber-200 bg-amber-50/50" : "border-slate-200 bg-slate-50/80"}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="font-medium text-slate-900">{q.label}</p>
              {q.needs_answer ? (
                <Badge tone="amber">Needs answer</Badge>
              ) : q.has_saved_rule ? (
                <Badge tone="green">Saved rule</Badge>
              ) : (
                <Badge tone="slate">Seen</Badge>
              )}
            </div>
            {(q.job_title || q.company) && (
              <p className="mt-1 text-xs text-slate-500">{[q.job_title, q.company].filter(Boolean).join(" · ")}</p>
            )}
            {q.options.length > 0 && (
              <p className="mt-1 text-xs text-slate-500">Options: {q.options.join(", ")}</p>
            )}
            <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">
              {q.question_type}
              {q.times_seen && q.times_seen > 1 ? ` · seen ${q.times_seen}×` : ""}
            </p>
            {q.needs_answer && (
              <TextInput
                className="mt-3"
                label="Your answer for next time"
                value={answers[q.id] ?? ""}
                onChange={(v) => setAnswers((prev) => ({ ...prev, [q.id]: v }))}
                placeholder={q.options[0] ? `e.g. ${q.options[0]}` : "Type your answer"}
              />
            )}
          </li>
        ))}
      </ul>
      {needCount > 0 && (
        <div className="mt-4 flex justify-end">
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!canSave}>
            Save answers for next run
          </Button>
        </div>
      )}
    </Card>
  );
}
