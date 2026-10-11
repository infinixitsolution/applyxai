import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { PendingQuestionAnswerField } from "./PendingQuestionAnswerField";
import { useToast } from "../components/Toast";
import { Alert, Badge, Button, Card } from "../components/ui";
import { ApiError, errorMessage } from "../services/api";
import { formatForQuestion } from "../lib/questionAnswerFormat";
import { preferences } from "../services/endpoints";
import type { ApplicationPreferencesOut, PendingFormQuestion } from "../types";

const AI_BATCH = 20;

function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

function usableOptions(options: string[]): string[] {
  return options.filter((o) => {
    const t = o.trim().toLowerCase();
    return t.length > 0 && t !== "select an option" && !t.startsWith("select an option");
  });
}

function aiFillErrorToast(e: unknown, toast: ReturnType<typeof useToast>) {
  if (e instanceof ApiError && e.status === 404) {
    toast.error(
      "This server does not have AI fill yet. Deploy or restart the latest API (see docs/DEVELOPMENT.md), then try again.",
    );
    return;
  }
  toast.error(errorMessage(e));
}

function PendingQuestionRow({
  q,
  aiAvailable,
  value,
  onChange,
}: {
  q: PendingFormQuestion;
  aiAvailable: boolean;
  value: string;
  onChange: (v: string) => void;
}) {
  const toast = useToast();
  const client = useQueryClient();
  const choiceOpts = usableOptions(q.options);
  const answerKind = formatForQuestion(q);
  const trimmed = value.trim();
  const canSave = trimmed.length > 0;

  const saveOne = useMutation({
    mutationFn: () =>
      preferences.resolvePending({
        answers: [{ id: q.id, answer: trimmed, label: q.label, question_type: q.question_type }],
      }),
    onSuccess: (data) => {
      const norm = (s: string) => s.trim().toLowerCase();
      const stillOpen = (data.pending_form_questions ?? []).some(
        (p) =>
          p.needs_answer &&
          (p.id === q.id || norm(p.label) === norm(q.label)),
      );
      if (stillOpen) {
        toast.error("Save did not stick — refresh the page or deploy the latest API.");
        void client.invalidateQueries({ queryKey: ["preferences", "application"] });
        return;
      }
      toast.success("Saved for next run.");
      onChange("");
      client.setQueryData<ApplicationPreferencesOut>(["preferences", "application"], data);
    },
    onError: (e) => {
      void client.invalidateQueries({ queryKey: ["preferences", "application"] });
      if (e instanceof ApiError && e.code === "VALIDATION_ERROR" && /custom question/i.test(e.message)) {
        toast.error("Too many saved rules (200 max). Remove some under Custom screening questions, then save again.");
        return;
      }
      toast.error(errorMessage(e));
    },
  });

  const aiOne = useMutation({
    mutationFn: () => preferences.suggestPendingAi({ ids: [q.id] }),
    onSuccess: (data) => {
      const hit = data.suggestions.find((s) => s.id === q.id);
      if (hit?.answer) {
        onChange(hit.answer);
        toast.success("AI suggestion added — review and save.");
        return;
      }
      const skip = data.skipped.find((s) => s.id === q.id);
      if (skip?.reason === "not_eligible") {
        toast.error("This question cannot use AI (type or sensitive topic). Answer manually.");
      } else {
        toast.error("AI could not suggest an answer. Try again or type your own.");
      }
    },
    onError: (e) => aiFillErrorToast(e, toast),
  });

  return (
    <li className="rounded-xl bg-amber-50/60 p-4 ring-1 ring-amber-200">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-medium text-slate-900">{q.label}</p>
        <Badge tone="amber">Needs answer</Badge>
      </div>
      {(q.job_title || q.company) && (
        <p className="mt-1 text-xs text-slate-500">{[q.job_title, q.company].filter(Boolean).join(" · ")}</p>
      )}
      {choiceOpts.length > 0 && (
        <p className="mt-1 text-xs text-slate-500">Options: {choiceOpts.join(", ")}</p>
      )}
      <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">
        {answerKind === "number" ? "number" : answerKind === "choice" ? q.question_type : "text"}
        {q.times_seen && q.times_seen > 1 ? ` · seen ${q.times_seen}×` : ""}
      </p>
      <div className="mt-3">
        <PendingQuestionAnswerField q={q} value={value} onChange={onChange} />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
        {aiAvailable && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            loading={aiOne.isPending}
            disabled={aiOne.isPending || saveOne.isPending}
            onClick={() => aiOne.mutate()}
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            AI
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          loading={saveOne.isPending}
          disabled={!canSave || saveOne.isPending || aiOne.isPending}
          onClick={() => saveOne.mutate()}
        >
          Save
        </Button>
      </div>
    </li>
  );
}

export function LinkedInCapturedQuestions({ aiAvailable }: { aiAvailable: boolean }) {
  const toast = useToast();
  const client = useQueryClient();
  const appPrefs = useQuery({
    queryKey: ["preferences", "application"],
    queryFn: preferences.application,
  });
  const items = appPrefs.data?.pending_form_questions ?? [];

  const openQuestions = useMemo(
    () =>
      items
        .filter((q) => q.needs_answer)
        .sort((a, b) => (b.last_seen_at ?? "").localeCompare(a.last_seen_at ?? "")),
    [items],
  );
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [aiProgress, setAiProgress] = useState<string | null>(null);

  const saveAll = useMutation({
    mutationFn: () =>
      preferences.resolvePending({
        answers: openQuestions
          .filter((q) => (answers[q.id] ?? "").trim())
          .map((q) => ({
            id: q.id,
            answer: (answers[q.id] ?? "").trim(),
            label: q.label,
            question_type: q.question_type,
          })),
      }),
    onSuccess: (data) => {
      toast.success("Saved — these answers are used as custom rules on the next run.");
      setAnswers({});
      client.setQueryData(["preferences", "application"], data);
    },
    onError: (e) => {
      void client.invalidateQueries({ queryKey: ["preferences", "application"] });
      toast.error(errorMessage(e));
    },
  });

  const fillWithAi = useMutation({
    mutationFn: async () => {
      const targets = openQuestions;
      if (!targets.length) return { filled: 0, skipped: 0 };
      const batches = chunk(targets, AI_BATCH);
      let filled = 0;
      let skipped = 0;
      for (let i = 0; i < batches.length; i += 1) {
        setAiProgress(`${Math.min((i + 1) * AI_BATCH, targets.length)} / ${targets.length}`);
        const batch = batches[i];
        const res = await preferences.suggestPendingAi({ ids: batch.map((q) => q.id) });
        for (const row of res.suggestions) {
          setAnswers((prev) => ({ ...prev, [row.id]: row.answer }));
          filled += 1;
        }
        skipped += res.skipped.length;
      }
      return { filled, skipped };
    },
    onSuccess: ({ filled, skipped }) => {
      setAiProgress(null);
      if (filled) {
        toast.success(
          skipped
            ? `Filled ${filled} answer${filled === 1 ? "" : "s"} with AI (${skipped} skipped — review and save each or use Save all).`
            : `Filled ${filled} answer${filled === 1 ? "" : "s"} with AI. Review, then save.`,
        );
      } else {
        toast.error("AI could not draft answers. Check platform AI settings or answer manually.");
      }
    },
    onError: (e) => {
      setAiProgress(null);
      aiFillErrorToast(e, toast);
    },
  });

  if (appPrefs.isLoading) {
    return (
      <Card title="LinkedIn questions from auto apply">
        <p className="text-sm text-slate-600">Loading captured questions…</p>
      </Card>
    );
  }

  if (!items.length && !openQuestions.length) {
    return (
      <Card title="LinkedIn questions from auto apply">
        <p className="text-sm text-slate-600">
          When you run automation, every form question LinkedIn shows is recorded here so you can answer once and reuse
          it next time.
        </p>
      </Card>
    );
  }

  if (!openQuestions.length) {
    return (
      <Card
        title="LinkedIn questions from auto apply"
        actions={<Badge tone="green">All caught up</Badge>}
      >
        <p className="text-sm text-slate-600">
          Every captured question has a saved answer. New questions from the next automation run will appear here. Saved
          rules are listed under <strong>Custom screening questions</strong> below.
        </p>
      </Card>
    );
  }

  const needCount = openQuestions.length;
  const canSaveAll = openQuestions.some((q) => (answers[q.id] ?? "").trim().length > 0);

  return (
    <Card
      title="LinkedIn questions from auto apply"
      actions={<Badge tone="amber">{needCount} need an answer</Badge>}
    >
      <p className="mb-4 text-sm text-slate-600">
        Each question has its own <strong>AI</strong> and <strong>Save</strong> buttons. The count above updates as you
        save. Saved answers become custom rules for the next run.
      </p>
      {needCount > 0 && !aiAvailable && (
        <Alert kind="info" className="mb-4">
          Platform AI is not enabled. An admin must configure AI under Settings, or answer questions manually below.
        </Alert>
      )}
      {needCount > 0 && aiAvailable && (
        <Alert kind="info" className="mb-4">
          AI uses your screening profile, extra context, and default resume. Review every suggestion before saving.
        </Alert>
      )}
      <ul className="mt-4 max-h-[min(520px,55vh)] space-y-3 overflow-y-auto pr-1">
        {openQuestions.map((q) => (
          <PendingQuestionRow
            key={q.id}
            q={q}
            aiAvailable={aiAvailable}
            value={answers[q.id] ?? ""}
            onChange={(v) => setAnswers((prev) => ({ ...prev, [q.id]: v }))}
          />
        ))}
      </ul>
      {needCount > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-slate-200/80 pt-4">
          {aiAvailable && (
            <Button
              type="button"
              variant="secondary"
              loading={fillWithAi.isPending}
              disabled={fillWithAi.isPending}
              onClick={() => fillWithAi.mutate()}
            >
              <Sparkles className="h-4 w-4" aria-hidden />
              {aiProgress ? `Filling all… ${aiProgress}` : "Fill all with AI"}
            </Button>
          )}
          <Button
            type="button"
            onClick={() => saveAll.mutate()}
            loading={saveAll.isPending}
            disabled={!canSaveAll}
          >
            Save all filled answers
          </Button>
        </div>
      )}
    </Card>
  );
}
