import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { ME_KEY } from "../auth/session";
import { TagInput, TextArea, TextInput } from "../components/form";
import { useToast } from "../components/Toast";
import { Alert, Button, Spinner } from "../components/ui";
import { errorMessage, fieldErrors } from "../services/api";
import { profile as profileApi } from "../services/endpoints";
import type { EducationEntry, Profile, ProfileInput, WorkEntry } from "../types";

const emptyEducation = (): EducationEntry => ({
  school: "",
  degree: "",
  field: "",
  start_year: "",
  end_year: "",
});

const emptyWork = (): WorkEntry => ({
  title: "",
  company: "",
  location: "",
  start: "",
  end: "",
  summary: "",
});

export function ProfileForm({ onSaved, submitLabel = "Save profile" }: { onSaved?: () => void; submitLabel?: string }) {
  const { data, isLoading, error } = useQuery({ queryKey: ["profile"], queryFn: profileApi.get });
  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  return (
    <ProfileFormInner
      key={`${data.email}-${(data.work_history ?? []).length}-${(data.education ?? []).length}-${data.phone ?? ""}`}
      initial={data}
      onSaved={onSaved}
      submitLabel={submitLabel}
    />
  );
}

function ProfileFormInner({ initial, onSaved, submitLabel }: { initial: Profile; onSaved?: () => void; submitLabel: string }) {
  const client = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState({
    first_name: initial.first_name,
    last_name: initial.last_name,
    phone: initial.phone ?? "",
    headline: initial.headline ?? "",
    summary: initial.summary ?? "",
    current_title: initial.current_title ?? "",
    current_company: initial.current_company ?? "",
    experience_years: initial.experience_years?.toString() ?? "",
    skills: initial.skills,
    preferred_roles: initial.preferred_roles,
    preferred_locations: initial.preferred_locations,
    preferred_resume_template: initial.preferred_resume_template ?? "modern",
    education: [...(initial.education ?? [])],
    work_history: [...(initial.work_history ?? [])],
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = <K extends keyof typeof form>(key: K) => (value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));

  useEffect(() => {
    setForm({
      first_name: initial.first_name,
      last_name: initial.last_name,
      phone: initial.phone ?? "",
      headline: initial.headline ?? "",
      summary: initial.summary ?? "",
      current_title: initial.current_title ?? "",
      current_company: initial.current_company ?? "",
      experience_years: initial.experience_years?.toString() ?? "",
      skills: initial.skills,
      preferred_roles: initial.preferred_roles,
      preferred_locations: initial.preferred_locations,
      preferred_resume_template: initial.preferred_resume_template ?? "modern",
      education: [...(initial.education ?? [])],
      work_history: [...(initial.work_history ?? [])],
    });
  }, [initial]);

  const save = useMutation({
    mutationFn: (body: ProfileInput) => profileApi.update(body),
    onSuccess: (saved) => {
      client.setQueryData(["profile"], saved);
      client.invalidateQueries({ queryKey: ME_KEY });
      toast.success("Profile saved");
      onSaved?.();
    },
    onError: (e) => setErrors(fieldErrors(e)),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const years = form.experience_years.trim();
    if (years && !/^\d+$/.test(years)) {
      setErrors({ experience_years: "Enter a whole number of years." });
      return;
    }
    setErrors({});
    save.mutate({
      ...form,
      phone: form.phone.trim() || null,
      headline: form.headline.trim() || null,
      summary: form.summary.trim() || null,
      current_title: form.current_title.trim() || null,
      current_company: form.current_company.trim() || null,
      experience_years: years ? Number.parseInt(years, 10) : null,
      preferred_resume_template: form.preferred_resume_template,
      education: form.education.filter((e) => e.school.trim() || e.degree.trim()),
      work_history: form.work_history.filter((w) => w.title.trim() || w.company.trim()),
    });
  };

  const patchWork = (index: number, patch: Partial<WorkEntry>) => {
    setForm((f) => ({
      ...f,
      work_history: f.work_history.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    }));
  };

  const patchEducation = (index: number, patch: Partial<EducationEntry>) => {
    setForm((f) => ({
      ...f,
      education: f.education.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    }));
  };

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}
      <p className="text-sm text-slate-600">
        These details are used for Easy Apply and AI answers. Upload or re-run intake from{" "}
        <strong>Resumes</strong> to refresh from your CV.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput label="First name" value={form.first_name} onChange={set("first_name")} error={errors.first_name} maxLength={100} autoComplete="given-name" />
        <TextInput label="Last name" value={form.last_name} onChange={set("last_name")} error={errors.last_name} maxLength={100} autoComplete="family-name" />
        <TextInput label="Phone" type="tel" value={form.phone} onChange={set("phone")} error={errors.phone} maxLength={32} autoComplete="tel"
                   hint="Used to fill in application forms." />
        <TextInput label="Years of experience" inputMode="numeric" value={form.experience_years} onChange={set("experience_years")} error={errors.experience_years} />
        <TextInput label="Current title" value={form.current_title} onChange={set("current_title")} error={errors.current_title} maxLength={255} />
        <TextInput label="Current company" value={form.current_company} onChange={set("current_company")} error={errors.current_company} maxLength={255} />
      </div>
      <TextInput label="Headline" value={form.headline} onChange={set("headline")} error={errors.headline} maxLength={255}
                 placeholder="e.g. Backend engineer · Python, Django, AWS" />
      <TextArea label="Summary" value={form.summary} onChange={set("summary")} error={errors.summary} maxLength={5000} rows={5}
                hint="A short professional summary. Some application forms ask for one." />
      <TagInput label="Skills" value={form.skills} onChange={set("skills")} error={errors.skills} placeholder="Python, SQL, …" />

      <section className="space-y-3 rounded-lg border border-slate-200 bg-slate-50/80 p-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-900">Work experience</h3>
          <Button type="button" variant="ghost" size="sm" onClick={() => setForm((f) => ({ ...f, work_history: [...f.work_history, emptyWork()] }))}>
            <Plus className="h-4 w-4" aria-hidden /> Add role
          </Button>
        </div>
        {form.work_history.length === 0 ? (
          <p className="text-xs text-slate-500">No roles yet — they are filled when you upload a resume.</p>
        ) : (
          form.work_history.map((job, i) => (
            <div key={i} className="space-y-2 rounded-lg bg-white p-3 ring-1 ring-slate-200">
              <div className="flex justify-end">
                <button type="button" className="text-slate-400 hover:text-red-600" aria-label="Remove role"
                        onClick={() => setForm((f) => ({ ...f, work_history: f.work_history.filter((_, j) => j !== i) }))}>
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <TextInput label="Job title" value={job.title} onChange={(v) => patchWork(i, { title: v })} maxLength={255} />
                <TextInput label="Company" value={job.company} onChange={(v) => patchWork(i, { company: v })} maxLength={255} />
                <TextInput label="Location" value={job.location} onChange={(v) => patchWork(i, { location: v })} maxLength={255} />
                <TextInput label="Start" value={job.start} onChange={(v) => patchWork(i, { start: v })} maxLength={32} placeholder="2020 or Jan 2020" />
                <TextInput label="End" value={job.end} onChange={(v) => patchWork(i, { end: v })} maxLength={32} placeholder="Present" />
              </div>
              <TextArea label="Highlights" value={job.summary} onChange={(v) => patchWork(i, { summary: v })} maxLength={2000} rows={3} />
            </div>
          ))
        )}
      </section>

      <section className="space-y-3 rounded-lg border border-slate-200 bg-slate-50/80 p-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-900">Education</h3>
          <Button type="button" variant="ghost" size="sm" onClick={() => setForm((f) => ({ ...f, education: [...f.education, emptyEducation()] }))}>
            <Plus className="h-4 w-4" aria-hidden /> Add school
          </Button>
        </div>
        {form.education.length === 0 ? (
          <p className="text-xs text-slate-500">No education entries yet — they are filled when you upload a resume.</p>
        ) : (
          form.education.map((ed, i) => (
            <div key={i} className="space-y-2 rounded-lg bg-white p-3 ring-1 ring-slate-200">
              <div className="flex justify-end">
                <button type="button" className="text-slate-400 hover:text-red-600" aria-label="Remove education"
                        onClick={() => setForm((f) => ({ ...f, education: f.education.filter((_, j) => j !== i) }))}>
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <TextInput label="School" value={ed.school} onChange={(v) => patchEducation(i, { school: v })} maxLength={255} />
                <TextInput label="Degree" value={ed.degree} onChange={(v) => patchEducation(i, { degree: v })} maxLength={255} />
                <TextInput label="Field of study" value={ed.field} onChange={(v) => patchEducation(i, { field: v })} maxLength={255} />
                <TextInput label="Graduation year" value={ed.end_year} onChange={(v) => patchEducation(i, { end_year: v })} maxLength={16} />
              </div>
            </div>
          ))
        )}
      </section>

      <div className="grid gap-4 sm:grid-cols-2">
        <TagInput label="Preferred roles" value={form.preferred_roles} onChange={set("preferred_roles")} error={errors.preferred_roles} maxItems={20} />
        <TagInput label="Preferred locations" value={form.preferred_locations} onChange={set("preferred_locations")} error={errors.preferred_locations} maxItems={20} />
      </div>
      <div className="flex justify-end">
        <Button type="submit" loading={save.isPending}>{submitLabel}</Button>
      </div>
    </form>
  );
}
