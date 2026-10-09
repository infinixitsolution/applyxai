import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { DynamicField, fromDraft, sameValue, toDraft, type DraftValue } from "../components/DynamicField";
import { useToast } from "../components/Toast";
import { TextInput } from "../components/form";
import { Alert, Button, Card, Spinner } from "../components/ui";
import { errorMessage, fieldErrors } from "../services/api";
import { preferences } from "../services/endpoints";
import type { ApplicationPreferencesOut, FieldMeta, HumanQuestion } from "../types";
import { LinkedInCapturedQuestions } from "./LinkedInCapturedQuestions";

const SECTION_TITLES: Record<string, string> = {
  Profile: "Screening answers",
  "Run settings": "How the automation behaves",
};

function emptyQuestion(): HumanQuestion {
  return { id: crypto.randomUUID(), match: "contains", pattern: "", answer: "", field_types: ["text", "textarea", "select", "radio"] };
}

export function ApplicationPreferencesForm({ onSaved, submitLabel = "Save answers" }: { onSaved?: () => void; submitLabel?: string }) {
  const options = useQuery({ queryKey: ["preferences", "options"], queryFn: preferences.options, staleTime: Infinity });
  const answers = useQuery({ queryKey: ["preferences", "application"], queryFn: preferences.application });
  if (options.isLoading || answers.isLoading) return <Spinner />;
  if (!options.data || !answers.data) return <Alert kind="error">{errorMessage(options.error ?? answers.error)}</Alert>;
  return (
    <Inner
      fields={options.data.application_fields}
      initial={answers.data}
      onSaved={onSaved}
      submitLabel={submitLabel}
    />
  );
}

function Inner({
  fields,
  initial,
  onSaved,
  submitLabel,
}: {
  fields: FieldMeta[];
  initial: ApplicationPreferencesOut;
  onSaved?: () => void;
  submitLabel: string;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const engineInitial = initial.answers as Record<string, unknown>;
  const [draft, setDraft] = useState<Record<string, DraftValue>>(
    () => Object.fromEntries(fields.map((f) => [f.key, toDraft(f, engineInitial[f.key])])),
  );
  const [humanQuestions, setHumanQuestions] = useState<HumanQuestion[]>(() => [...(initial.human_questions ?? [])]);
  const [aiEnabled, setAiEnabled] = useState(initial.ai_applications_enabled);
  const [userInfoAll, setUserInfoAll] = useState(initial.user_information_all ?? "");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const sections = useMemo(() => {
    const grouped = new Map<string, FieldMeta[]>();
    for (const f of fields) grouped.set(f.section, [...(grouped.get(f.section) ?? []), f]);
    return [...grouped.entries()];
  }, [fields]);

  const save = useMutation({
    mutationFn: (changes: Record<string, unknown>) => preferences.patchApplication(changes),
    onSuccess: (saved) => {
      client.setQueryData(["preferences", "application"], saved);
      toast.success("Answers saved");
      onSaved?.();
    },
    onError: (e) => setErrors(fieldErrors(e)),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const problems: Record<string, string> = {};
    const changes: Record<string, unknown> = {};
    for (const field of fields) {
      try {
        const value = fromDraft(field, draft[field.key]);
        if (!sameValue(value, engineInitial[field.key])) changes[field.key] = value;
      } catch (err) {
        problems[field.key] = (err as Error).message;
      }
    }
    for (const q of humanQuestions) {
      if (!q.pattern.trim() || !q.answer.trim()) {
        problems.human_questions = "Each custom question needs a pattern and an answer.";
        break;
      }
    }
    setErrors(problems);
    if (Object.keys(problems).length) return;

    if (JSON.stringify(humanQuestions) !== JSON.stringify(initial.human_questions ?? [])) {
      changes.human_questions = humanQuestions;
    }
    if (aiEnabled !== initial.ai_applications_enabled) changes.ai_applications_enabled = aiEnabled;
    if (userInfoAll !== (initial.user_information_all ?? "")) changes.user_information_all = userInfoAll;

    if (!Object.keys(changes).length) {
      toast.success("No changes to save");
      onSaved?.();
      return;
    }
    save.mutate(changes);
  };

  const aiOff = !initial.ai_available;

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      <Alert kind="info">
        Fixed screening answers are used first, then saved LinkedIn questions, then AI for anything still empty.
        Your job-site password is never stored here.
      </Alert>

      <LinkedInCapturedQuestions items={initial.pending_form_questions ?? []} />
      {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}

      {sections.map(([section, sectionFields]) => (
        <Card key={section} title={`${SECTION_TITLES[section] ?? section} · Always used`}>
          <div className="grid gap-4 sm:grid-cols-2">
            {sectionFields.map((field) => (
              <div key={field.key} className={field.type === "textarea" ? "sm:col-span-2" : ""}>
                <DynamicField
                  field={field}
                  value={draft[field.key]}
                  error={errors[field.key]}
                  onChange={(v) => setDraft((d) => ({ ...d, [field.key]: v }))}
                />
              </div>
            ))}
          </div>
        </Card>
      ))}

      <Card title="Custom questions (your answers)">
        <p className="mb-4 text-sm text-muted">
          When a form label matches your pattern, this exact answer is used (before AI).
        </p>
        {errors.human_questions && <Alert kind="error">{errors.human_questions}</Alert>}
        <div className="space-y-3">
          {humanQuestions.map((q, idx) => (
            <div key={q.id} className="grid gap-2 rounded-lg border border-border p-3 sm:grid-cols-12">
              <div className="sm:col-span-2">
                <label className="text-xs font-medium text-muted">Match</label>
                <select
                  className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                  value={q.match}
                  onChange={(e) =>
                    setHumanQuestions((rows) =>
                      rows.map((r, i) => (i === idx ? { ...r, match: e.target.value as HumanQuestion["match"] } : r)),
                    )
                  }
                >
                  <option value="contains">Contains</option>
                  <option value="exact">Exact</option>
                </select>
              </div>
              <div className="sm:col-span-4">
                <label className="text-xs font-medium text-muted">Label pattern</label>
                <TextInput
                  label=""
                  value={q.pattern}
                  onChange={(v) =>
                    setHumanQuestions((rows) => rows.map((r, i) => (i === idx ? { ...r, pattern: v } : r)))
                  }
                  placeholder="e.g. referral code"
                />
              </div>
              <div className="sm:col-span-5">
                <label className="text-xs font-medium text-muted">Your answer</label>
                <TextInput
                  label=""
                  value={q.answer}
                  onChange={(v) =>
                    setHumanQuestions((rows) => rows.map((r, i) => (i === idx ? { ...r, answer: v } : r)))
                  }
                />
              </div>
              <div className="flex items-end sm:col-span-1">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setHumanQuestions((rows) => rows.filter((_, i) => i !== idx))}
                >
                  Remove
                </Button>
              </div>
            </div>
          ))}
        </div>
        <Button type="button" variant="secondary" className="mt-3" onClick={() => setHumanQuestions((r) => [...r, emptyQuestion()])}>
          Add custom question
        </Button>
      </Card>

      <Card title="AI assistance">
        {aiOff ? (
          <Alert kind="info">Platform AI is not configured yet. Ask an admin to enable it under Settings → AI.</Alert>
        ) : (
          <>
            {!aiEnabled && (
              <Alert kind="info">
                Recommended: turn this on so auto apply uses AI for questions that are not in your screening answers or
                saved LinkedIn list above.
              </Alert>
            )}
            <p className="mb-3 text-sm text-slate-600">
              When enabled, questions that are not covered by your screening answers or saved LinkedIn rules are filled
              using platform AI (profile + job description + extra context below). Review applications — AI can be wrong.
            </p>
          </>
        )}
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={aiEnabled}
            disabled={aiOff}
            onChange={(e) => setAiEnabled(e.target.checked)}
          />
          Use AI for eligible application questions during auto apply
        </label>
        <div className="mt-4">
          <label className="text-sm font-medium">Extra context for AI</label>
          <textarea
            className="mt-1 min-h-[120px] w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={userInfoAll}
            disabled={aiOff}
            onChange={(e) => setUserInfoAll(e.target.value)}
            placeholder="Certifications, portfolio links, relocation notes, etc."
          />
        </div>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" loading={save.isPending}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
