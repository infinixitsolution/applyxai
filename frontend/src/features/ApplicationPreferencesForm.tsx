import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { DynamicField, fromDraft, sameValue, toDraft, type DraftValue } from "../components/DynamicField";
import { useToast } from "../components/Toast";
import { Alert, Button, Card, Spinner } from "../components/ui";
import { errorMessage, fieldErrors } from "../services/api";
import { preferences } from "../services/endpoints";
import type { Answers, FieldMeta } from "../types";

const SECTION_TITLES: Record<string, string> = {
  Profile: "Screening answers",
  "Run settings": "How the automation behaves",
};

export function ApplicationPreferencesForm({ onSaved, submitLabel = "Save answers" }: { onSaved?: () => void; submitLabel?: string }) {
  const options = useQuery({ queryKey: ["preferences", "options"], queryFn: preferences.options, staleTime: Infinity });
  const answers = useQuery({ queryKey: ["preferences", "application"], queryFn: preferences.application });
  if (options.isLoading || answers.isLoading) return <Spinner />;
  if (!options.data || !answers.data) return <Alert kind="error">{errorMessage(options.error ?? answers.error)}</Alert>;
  return <Inner fields={options.data.application_fields} initial={answers.data} onSaved={onSaved} submitLabel={submitLabel} />;
}

function Inner({ fields, initial, onSaved, submitLabel }:
  { fields: FieldMeta[]; initial: Answers; onSaved?: () => void; submitLabel: string }) {
  const client = useQueryClient();
  const toast = useToast();
  const [draft, setDraft] = useState<Record<string, DraftValue>>(
    () => Object.fromEntries(fields.map((f) => [f.key, toDraft(f, initial[f.key])])),
  );
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
        if (!sameValue(value, initial[field.key])) changes[field.key] = value;
      } catch (err) {
        problems[field.key] = (err as Error).message;
      }
    }
    setErrors(problems);
    if (Object.keys(problems).length) return;
    if (!Object.keys(changes).length) {
      toast.success("No changes to save");
      onSaved?.();
      return;
    }
    save.mutate(changes);
  };

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      <Alert kind="info">
        These answers fill in application forms for you. Anything you leave as "Not set" uses the automation's default.
        Your job-site password is never stored here.
      </Alert>
      {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}
      {sections.map(([section, sectionFields]) => (
        <Card key={section} title={SECTION_TITLES[section] ?? section}>
          <div className="grid gap-4 sm:grid-cols-2">
            {sectionFields.map((field) => (
              <div key={field.key} className={field.type === "textarea" ? "sm:col-span-2" : ""}>
                <DynamicField field={field} value={draft[field.key]} error={errors[field.key]}
                              onChange={(v) => setDraft((d) => ({ ...d, [field.key]: v }))} />
              </div>
            ))}
          </div>
        </Card>
      ))}
      <div className="flex justify-end">
        <Button type="submit" loading={save.isPending}>{submitLabel}</Button>
      </div>
    </form>
  );
}
