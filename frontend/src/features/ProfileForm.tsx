import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ME_KEY } from "../auth/session";
import { TagInput, TextArea, TextInput } from "../components/form";
import { useToast } from "../components/Toast";
import { Alert, Button, Spinner } from "../components/ui";
import { errorMessage, fieldErrors } from "../services/api";
import { profile as profileApi } from "../services/endpoints";
import type { Profile, ProfileInput } from "../types";

export function ProfileForm({ onSaved, submitLabel = "Save profile" }: { onSaved?: () => void; submitLabel?: string }) {
  const { data, isLoading, error } = useQuery({ queryKey: ["profile"], queryFn: profileApi.get });
  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  return <ProfileFormInner initial={data} onSaved={onSaved} submitLabel={submitLabel} />;
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
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = <K extends keyof typeof form>(key: K) => (value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));

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
    });
  };

  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}
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
