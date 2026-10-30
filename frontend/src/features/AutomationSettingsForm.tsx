import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { DynamicField, fromDraft, sameValue, toDraft, type DraftValue } from "../components/DynamicField";
import { ConfirmDialog } from "../components/Modal";
import { useToast } from "../components/Toast";
import { Alert, Button, Card, Spinner } from "../components/ui";
import { errorMessage, fieldErrors } from "../services/api";
import { automationSettings } from "../services/endpoints";

export function AutomationSettingsForm() {
  const client = useQueryClient();
  const toast = useToast();
  const [confirmReset, setConfirmReset] = useState(false);
  const { data, isLoading, error } = useQuery({ queryKey: ["automation-settings"], queryFn: automationSettings.get });

  const [draft, setDraft] = useState<Record<string, DraftValue>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!data) return;
    setDraft(Object.fromEntries(data.fields.map((f) => [f.key, toDraft(f, data.values[f.key])])));
  }, [data]);

  const save = useMutation({
    mutationFn: (changes: Record<string, unknown>) => automationSettings.patch(changes),
    onSuccess: (saved) => {
      client.setQueryData(["automation-settings"], saved);
      setDraft(Object.fromEntries(saved.fields.map((f) => [f.key, toDraft(f, saved.values[f.key])])));
      toast.success("Automation settings saved");
    },
    onError: (e) => setErrors(fieldErrors(e)),
  });

  const reset = useMutation({
    mutationFn: () => automationSettings.reset(),
    onSuccess: (saved) => {
      client.setQueryData(["automation-settings"], saved);
      setDraft(Object.fromEntries(saved.fields.map((f) => [f.key, toDraft(f, saved.values[f.key])])));
      setConfirmReset(false);
      toast.success("Reset to defaults");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (isLoading || !data) return isLoading ? <Spinner /> : <Alert kind="error">{errorMessage(error)}</Alert>;

  const submit = () => {
    const changes: Record<string, unknown> = {};
    const problems: Record<string, string> = {};
    for (const field of data.fields) {
      try {
        const value = fromDraft(field, draft[field.key]);
        if (!sameValue(value, data.values[field.key])) changes[field.key] = value;
      } catch (err) {
        problems[field.key] = (err as Error).message;
      }
    }
    setErrors(problems);
    if (Object.keys(problems).length) return;
    if (!Object.keys(changes).length) {
      toast.success("No changes to save");
      return;
    }
    save.mutate(changes);
  };

  return (
    <div className="space-y-6">
      {data.warnings.map((w) => (
        <Alert key={w} kind="info">{w}</Alert>
      ))}
      <Card title="Execution">
        <div className="grid gap-4 sm:grid-cols-2">
          {data.fields.map((field) => (
            <div key={field.key} className={field.type === "textarea" ? "sm:col-span-2" : ""}>
              <DynamicField
                field={field}
                value={draft[field.key]}
                error={errors[field.key]}
                onChange={(v) => setDraft((d) => ({ ...d, [field.key]: v }))}
              />
              {data.defaults[field.key] !== undefined && draft[field.key] === toDraft(field, data.defaults[field.key]) && (
                <p className="mt-1 text-xs text-slate-500">Using default</p>
              )}
            </div>
          ))}
        </div>
      </Card>
      <div className="flex flex-wrap justify-between gap-3">
        <Button type="button" variant="secondary" onClick={() => setConfirmReset(true)}>
          Reset to defaults
        </Button>
        <Button type="button" onClick={submit} loading={save.isPending}>
          Save settings
        </Button>
      </div>
      <ConfirmDialog
        open={confirmReset}
        onClose={() => setConfirmReset(false)}
        title="Reset automation settings?"
        danger
        confirmLabel="Reset"
        loading={reset.isPending}
        onConfirm={() => reset.mutate()}
        message="Run behavior returns to platform defaults. Your profile and custom questions are not changed."
      />
    </div>
  );
}
