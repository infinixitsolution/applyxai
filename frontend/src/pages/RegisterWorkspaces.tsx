import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { TextInput } from "../components/form";
import { Alert, Button } from "../components/ui";
import { AuthCard } from "../layouts/PublicLayout";
import { errorMessage, fieldErrors } from "../services/api";
import { auth } from "../services/endpoints";

const MIN_PASSWORD = 10;

function problems(password: string, confirm: string) {
  const errors: Record<string, string> = {};
  if (password.length < MIN_PASSWORD) errors.password = `Use at least ${MIN_PASSWORD} characters.`;
  if (confirm !== password) errors.confirm = "Passwords don't match.";
  return errors;
}

export function InstituteRegisterPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [form, setForm] = useState({
    first_name: "", last_name: "", email: "", password: "", confirm: "",
    institute_name: "", contact_name: "", phone: "", gstin: "", pan_number: "",
    referral_code: params.get("r") ?? "", agreed: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const register = useMutation({
    mutationFn: () => auth.register({
      ...form, account_type: "institute", agreed: true,
    }),
    onSuccess: (result) => navigate(result.verification_required === false
      ? "/login?registered=1" : `/check-email?email=${encodeURIComponent(form.email)}`),
    onError: (error) => setErrors(fieldErrors(error)),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const p = problems(form.password, form.confirm);
    if (!form.institute_name.trim()) p.institute_name = "Enter the institute name.";
    setErrors(p);
    if (!Object.keys(p).length) register.mutate();
  };
  return (
    <AuthCard title="Register an institute" subtitle={<>Already have an account? <Link to="/login" className="font-medium text-brand-600 hover:underline">Log in</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {register.error && !Object.keys(fieldErrors(register.error)).length && <Alert kind="error">{errorMessage(register.error)}</Alert>}
        <TextInput label="Institute name" required value={form.institute_name} onChange={set("institute_name")} error={errors.institute_name} />
        <TextInput label="Contact name" value={form.contact_name} onChange={set("contact_name")} />
        <div className="grid grid-cols-2 gap-3">
          <TextInput label="First name" value={form.first_name} onChange={set("first_name")} />
          <TextInput label="Last name" value={form.last_name} onChange={set("last_name")} />
        </div>
        <TextInput label="Email" type="email" required value={form.email} onChange={set("email")} error={errors.email} />
        <TextInput label="Phone" value={form.phone} onChange={set("phone")} />
        <TextInput label="Password" type="password" required value={form.password} onChange={set("password")} error={errors.password} />
        <TextInput label="Confirm password" type="password" required value={form.confirm} onChange={set("confirm")} error={errors.confirm} />
        <TextInput label="Referral code" value={form.referral_code} onChange={set("referral_code")} />
        <Button type="submit" className="w-full" loading={register.isPending}>Submit application</Button>
        <p className="text-center text-xs text-slate-500">Looking for a job? <Link to="/register" className="underline">Create a candidate account</Link></p>
      </form>
    </AuthCard>
  );
}

export function PartnerRegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    first_name: "", last_name: "", email: "", password: "", confirm: "",
    organization: "", contact_name: "", phone: "", agreed: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const register = useMutation({
    mutationFn: () => auth.register({ ...form, account_type: "partner", agreed: true }),
    onSuccess: (result) => navigate(result.verification_required === false
      ? "/login?registered=1" : `/check-email?email=${encodeURIComponent(form.email)}`),
    onError: (error) => setErrors(fieldErrors(error)),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const p = problems(form.password, form.confirm);
    if (!form.organization.trim()) p.organization = "Enter the organisation name.";
    setErrors(p);
    if (!Object.keys(p).length) register.mutate();
  };
  return (
    <AuthCard title="Become a partner" subtitle={<>Already have an account? <Link to="/login" className="font-medium text-brand-600 hover:underline">Log in</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {register.error && !Object.keys(fieldErrors(register.error)).length && <Alert kind="error">{errorMessage(register.error)}</Alert>}
        <TextInput label="Organisation" required value={form.organization} onChange={set("organization")} error={errors.organization} />
        <TextInput label="Contact name" value={form.contact_name} onChange={set("contact_name")} />
        <div className="grid grid-cols-2 gap-3">
          <TextInput label="First name" value={form.first_name} onChange={set("first_name")} />
          <TextInput label="Last name" value={form.last_name} onChange={set("last_name")} />
        </div>
        <TextInput label="Email" type="email" required value={form.email} onChange={set("email")} />
        <TextInput label="Phone" value={form.phone} onChange={set("phone")} />
        <TextInput label="Password" type="password" required value={form.password} onChange={set("password")} error={errors.password} />
        <TextInput label="Confirm password" type="password" required value={form.confirm} onChange={set("confirm")} error={errors.confirm} />
        <Button type="submit" className="w-full" loading={register.isPending}>Submit application</Button>
        <p className="text-center text-xs text-slate-500">Looking for a job? <Link to="/register" className="underline">Create a candidate account</Link></p>
      </form>
    </AuthCard>
  );
}
