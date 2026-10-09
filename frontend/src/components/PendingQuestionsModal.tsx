import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Modal } from "./Modal";
import { useToast } from "./Toast";
import { TextInput } from "./form";
import { Button } from "./ui";
import { errorMessage } from "../services/api";
import { preferences } from "../services/endpoints";
import type { PendingFormQuestion } from "../types";

export function PendingQuestionsModal({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: PendingFormQuestion[];
}) {
  const toast = useToast();
  const client = useQueryClient();
  const need = useMemo(() => items.filter((q) => q.needs_answer), [items]);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const save = useMutation({
    mutationFn: () =>
      preferences.resolvePending({
        answers: need
          .map((q) => ({ id: q.id, answer: (answers[q.id] ?? "").trim() }))
          .filter((row) => row.answer.length > 0),
      }),
    onSuccess: () => {
      toast.success("Answers saved for future applications.");
      void client.invalidateQueries({ queryKey: ["preferences", "application"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!open || need.length === 0) return null;

  const allFilled = need.every((q) => (answers[q.id] ?? "").trim().length > 0);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Questions from your last run"
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Later</Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!allFilled}>
            Save answers
          </Button>
        </>
      }
    >
      <p className="mb-4 text-sm text-slate-600">
        LinkedIn asked these during automation. Your answers are saved as custom rules and used on the next run.
      </p>
      <ul className="max-h-[min(60vh,420px)] space-y-4 overflow-y-auto pr-1">
        {need.map((q) => (
          <li key={q.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="flex items-start gap-2 font-medium text-slate-900">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
              {q.label}
            </p>
            {(q.job_title || q.company) && (
              <p className="mt-1 text-xs text-slate-500">
                {[q.job_title, q.company].filter(Boolean).join(" · ")}
              </p>
            )}
            {q.options.length > 0 && (
              <p className="mt-1 text-xs text-slate-500">Options: {q.options.join(", ")}</p>
            )}
            <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">{q.question_type}</p>
            <TextInput
              className="mt-3"
              label="Your answer"
              value={answers[q.id] ?? ""}
              onChange={(v) => setAnswers((prev) => ({ ...prev, [q.id]: v }))}
            />
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-slate-500">
        You can also edit these under{" "}
        <Link to="/app/preferences" className="font-medium text-brand-600 hover:underline">Preferences → Custom questions</Link>.
      </p>
    </Modal>
  );
}
