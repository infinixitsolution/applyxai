import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState, type FormEvent } from "react";
import { DynamicField, fromDraft, toDraft, type DraftValue } from "../components/DynamicField";
import { ChipSelect, Select, TagInput, TextInput, Toggle } from "../components/form";
import { useToast } from "../components/Toast";
import { Alert, Button, Spinner } from "../components/ui";
import { errorMessage, fieldErrors } from "../services/api";
import { preferences } from "../services/endpoints";
import type { PreferenceOptions, SearchConfig, SearchConfigOut } from "../types";

export function SearchPreferencesForm({ onSaved, submitLabel = "Save preferences" }: { onSaved?: () => void; submitLabel?: string }) {
  const options = useQuery({ queryKey: ["preferences", "options"], queryFn: preferences.options, staleTime: Infinity });
  const search = useQuery({ queryKey: ["preferences", "search"], queryFn: preferences.search });
  if (options.isLoading || search.isLoading) return <Spinner />;
  if (!options.data || !search.data) return <Alert kind="error">{errorMessage(options.error ?? search.error)}</Alert>;
  return <Inner options={options.data} initial={search.data} onSaved={onSaved} submitLabel={submitLabel} />;
}

const toOptions = (values: string[], emptyLabel: string) =>
  values.map((v) => ({ value: v, label: v === "" ? emptyLabel : v }));

function Inner({ options, initial, onSaved, submitLabel }:
  { options: PreferenceOptions; initial: SearchConfigOut; onSaved?: () => void; submitLabel: string }) {
  const client = useQueryClient();
  const toast = useToast();
  const extraFields = options.search.extra_fields;
  const [form, setForm] = useState({
    keywords: initial.keywords,
    location: initial.location,
    easy_apply_only: initial.easy_apply_only,
    experience_level: initial.experience_level,
    job_type: initial.job_type,
    on_site: initial.on_site,
    companies: initial.companies,
    date_posted: initial.date_posted,
    sort_by: initial.sort_by,
    salary_min: initial.salary_min?.toString() ?? "",
    salary_max: initial.salary_max?.toString() ?? "",
  });
  const [extra, setExtra] = useState<Record<string, DraftValue>>(
    Object.fromEntries(extraFields.map((f) => [f.key, toDraft(f, initial.extra[f.key])])),
  );
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = <K extends keyof typeof form>(key: K) => (value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));

  const save = useMutation({
    mutationFn: (body: SearchConfig) => preferences.saveSearch(body),
    onSuccess: (saved) => {
      client.setQueryData(["preferences", "search"], saved);
      toast.success("Job preferences saved");
      onSaved?.();
    },
    onError: (e) => {
      const errs = fieldErrors(e);
      setErrors(errs);
      if (errs.extra) setShowAdvanced(true);
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const problems: Record<string, string> = {};
    if (!form.keywords.length) problems.keywords = "Add at least one job title or keyword.";
    const salary = (raw: string, key: string) => {
      const t = raw.trim();
      if (!t) return null;
      if (!/^\d+$/.test(t)) { problems[key] = "Enter a whole number."; return null; }
      return Number.parseInt(t, 10);
    };
    const salary_min = salary(form.salary_min, "salary_min");
    const salary_max = salary(form.salary_max, "salary_max");
    if (salary_min !== null && salary_max !== null && salary_min > salary_max) problems.salary_max = "Must be at least the minimum.";

    const extraOut: Record<string, unknown> = {};
    for (const field of extraFields) {
      try {
        const value = fromDraft(field, extra[field.key]);
        if (value !== null) extraOut[field.key] = value;
      } catch (err) {
        problems[field.key] = (err as Error).message;
        setShowAdvanced(true);
      }
    }
    setErrors(problems);
    if (Object.keys(problems).length) return;
    save.mutate({ ...form, salary_min, salary_max, extra: extraOut });
  };

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      {save.error && <Alert kind="error">{errorMessage(save.error)}</Alert>}
      <TagInput label="Job titles or keywords" value={form.keywords} onChange={set("keywords")} error={errors.keywords}
                placeholder="e.g. Python Developer" maxItems={20}
                hint="Each one is searched separately. Press Enter after each title." />
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput label="Location" value={form.location} onChange={set("location")} error={errors.location} maxLength={255}
                   placeholder="e.g. Bengaluru, India" hint="Leave blank to search everywhere." />
        <Select label="Date posted" value={form.date_posted} onChange={set("date_posted")} error={errors.date_posted}
                options={toOptions(options.search.date_posted, "Any (LinkedIn default)")} />
      </div>
      <ChipSelect label="Experience level" options={options.search.experience_level} value={form.experience_level}
                  onChange={set("experience_level")} error={errors.experience_level} hint="Leave all unselected to include every level." />
      <ChipSelect label="Job type" options={options.search.job_type} value={form.job_type} onChange={set("job_type")} error={errors.job_type} />
      <ChipSelect label="Work setting" options={options.search.on_site} value={form.on_site} onChange={set("on_site")} error={errors.on_site} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Select label="Sort results by" value={form.sort_by} onChange={set("sort_by")} error={errors.sort_by}
                options={toOptions(options.search.sort_by, "LinkedIn default")} />
        <TextInput label="Minimum salary (yearly)" inputMode="numeric" value={form.salary_min} onChange={set("salary_min")} error={errors.salary_min} />
        <TextInput label="Maximum salary (yearly)" inputMode="numeric" value={form.salary_max} onChange={set("salary_max")} error={errors.salary_max} />
      </div>
      <TagInput label="Only these companies (optional)" value={form.companies} onChange={set("companies")} error={errors.companies} maxItems={50} />
      <Toggle label="Easy Apply jobs only" checked={form.easy_apply_only} onChange={set("easy_apply_only")}
              hint="Recommended. Jobs on external sites are recorded so you can apply yourself." />

      <div className="rounded-lg ring-1 ring-slate-200">
        <button type="button" onClick={() => setShowAdvanced((s) => !s)} aria-expanded={showAdvanced}
                className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-slate-700">
          Advanced filters
          <ChevronDown className={`h-4 w-4 transition-transform ${showAdvanced ? "rotate-180" : ""}`} aria-hidden />
        </button>
        {showAdvanced && (
          <div className="grid gap-4 border-t border-slate-200 p-4 sm:grid-cols-2">
            {errors.extra && <div className="sm:col-span-2"><Alert kind="error">{errors.extra}</Alert></div>}
            {extraFields.map((field) => (
              <div key={field.key} className={field.type === "list" ? "sm:col-span-2" : ""}>
                <DynamicField field={field} value={extra[field.key]} error={errors[field.key]}
                              onChange={(v) => setExtra((x) => ({ ...x, [field.key]: v }))} />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex justify-end">
        <Button type="submit" loading={save.isPending}>{submitLabel}</Button>
      </div>
    </form>
  );
}
