import { useMutation } from "@tanstack/react-query";
import { Building2, Handshake } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { TextInput } from "../components/form";
import { Alert, Button } from "../components/ui";
import { AuthLegalLinks, AuthPageLayout } from "../features/auth/AuthPageLayout";
import { REGISTER_STORY } from "../features/auth/registerStories";
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
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    confirm: "",
    institute_name: "",
    contact_name: "",
    phone: "",
    gstin: "",
    pan_number: "",
    referral_code: params.get("r") ?? "",
    agreed: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const register = useMutation({
    mutationFn: () =>
      auth.register({
        ...form,
        account_type: "institute",
        agreed: true,
      }),
    onSuccess: (result) =>
      navigate(
        result.verification_required === false
          ? "/login?registered=1"
          : `/check-email?email=${encodeURIComponent(form.email)}`,
      ),
    onError: (error) => setErrors(fieldErrors(error)),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const p = problems(form.password, form.confirm);
    if (!form.institute_name.trim()) p.institute_name = "Enter the institute name.";
    if (!form.email.includes("@")) p.email = "Enter a valid email address.";
    setErrors(p);
    if (!Object.keys(p).length) register.mutate();
  };

  const story = REGISTER_STORY.institute;

  return (
    <AuthPageLayout
      tone="institute"
      storyAriaLabel="Institute program"
      kicker={
        <>
          <Building2 size={14} aria-hidden />
          {story.kicker}
        </>
      }
      storyTitle={story.title}
      storyLead={story.lead}
      highlights={story.highlights}
      showLinkedInTrust={story.showLinkedInTrust}
      trustLabel={story.trustLabel}
      trustSub={story.trustSub}
      registerTabs="institute"
      wideCard
      cardHeadingId="ax-register-institute"
      cardTitle="Register your institute"
      cardSubtitle={
        <>
          Already have an account?{" "}
          <Link to="/login" className="ax-login__link">
            Log in
          </Link>
        </>
      }
      footer={
        <p className="ax-login__alt-note">
          Looking for a job?{" "}
          <Link to="/register" className="ax-login__link">
            Create a candidate account
          </Link>
        </p>
      }
    >
      <form onSubmit={submit} className="ax-login__form ax-login__form--register" noValidate>
        {register.error && !Object.keys(fieldErrors(register.error)).length && (
          <Alert kind="error">{errorMessage(register.error)}</Alert>
        )}
        <fieldset className="ax-login__section">
          <legend>Organisation</legend>
          <div className="ax-login__fields">
            <TextInput
              label="Institute name"
              required
              value={form.institute_name}
              onChange={set("institute_name")}
              error={errors.institute_name}
            />
            <TextInput label="Primary contact name" value={form.contact_name} onChange={set("contact_name")} />
            <div className="ax-login__row-2">
              <TextInput label="GSTIN (optional)" value={form.gstin} onChange={set("gstin")} />
              <TextInput label="PAN (optional)" value={form.pan_number} onChange={set("pan_number")} />
            </div>
          </div>
        </fieldset>
        <fieldset className="ax-login__section">
          <legend>Admin account</legend>
          <div className="ax-login__fields">
            <div className="ax-login__row-2">
              <TextInput label="First name" value={form.first_name} onChange={set("first_name")} />
              <TextInput label="Last name" value={form.last_name} onChange={set("last_name")} />
            </div>
            <TextInput label="Work email" type="email" required value={form.email} onChange={set("email")} error={errors.email} />
            <TextInput label="Phone" type="tel" autoComplete="tel" value={form.phone} onChange={set("phone")} />
          </div>
        </fieldset>
        <fieldset className="ax-login__section">
          <legend>Security</legend>
          <div className="ax-login__fields">
            <TextInput
              label="Password"
              type="password"
              autoComplete="new-password"
              required
              value={form.password}
              onChange={set("password")}
              error={errors.password}
              hint={`At least ${MIN_PASSWORD} characters.`}
            />
            <TextInput
              label="Confirm password"
              type="password"
              autoComplete="new-password"
              required
              value={form.confirm}
              onChange={set("confirm")}
              error={errors.confirm}
            />
          </div>
        </fieldset>
        <TextInput
          label="Partner referral code (optional)"
          value={form.referral_code}
          onChange={set("referral_code")}
          hint="Include this if a partner referred your institute."
        />
        <Button type="submit" className="ax-login__submit w-full" loading={register.isPending}>
          Submit institute application
        </Button>
        <AuthLegalLinks />
      </form>
    </AuthPageLayout>
  );
}

export function PartnerRegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    confirm: "",
    organization: "",
    contact_name: "",
    phone: "",
    agreed: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const register = useMutation({
    mutationFn: () => auth.register({ ...form, account_type: "partner", agreed: true }),
    onSuccess: (result) =>
      navigate(
        result.verification_required === false
          ? "/login?registered=1"
          : `/check-email?email=${encodeURIComponent(form.email)}`,
      ),
    onError: (error) => setErrors(fieldErrors(error)),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const p = problems(form.password, form.confirm);
    if (!form.organization.trim()) p.organization = "Enter the organisation name.";
    if (!form.email.includes("@")) p.email = "Enter a valid email address.";
    setErrors(p);
    if (!Object.keys(p).length) register.mutate();
  };

  const story = REGISTER_STORY.partner;

  return (
    <AuthPageLayout
      tone="partner"
      storyAriaLabel="Partner program"
      kicker={
        <>
          <Handshake size={14} aria-hidden />
          {story.kicker}
        </>
      }
      storyTitle={story.title}
      storyLead={story.lead}
      highlights={story.highlights}
      showLinkedInTrust={story.showLinkedInTrust}
      trustLabel={story.trustLabel}
      trustSub={story.trustSub}
      registerTabs="partner"
      wideCard
      cardHeadingId="ax-register-partner"
      cardTitle="Become an ApplyXAI partner"
      cardSubtitle={
        <>
          Already have an account?{" "}
          <Link to="/login" className="ax-login__link">
            Log in
          </Link>
        </>
      }
      footer={
        <p className="ax-login__alt-note">
          Looking for a job?{" "}
          <Link to="/register" className="ax-login__link">
            Create a candidate account
          </Link>
        </p>
      }
    >
      <form onSubmit={submit} className="ax-login__form ax-login__form--register" noValidate>
        {register.error && !Object.keys(fieldErrors(register.error)).length && (
          <Alert kind="error">{errorMessage(register.error)}</Alert>
        )}
        <fieldset className="ax-login__section">
          <legend>Organisation</legend>
          <div className="ax-login__fields">
            <TextInput
              label="Organisation name"
              required
              value={form.organization}
              onChange={set("organization")}
              error={errors.organization}
            />
            <TextInput label="Primary contact name" value={form.contact_name} onChange={set("contact_name")} />
            <TextInput label="Phone" type="tel" autoComplete="tel" value={form.phone} onChange={set("phone")} />
          </div>
        </fieldset>
        <fieldset className="ax-login__section">
          <legend>Your account</legend>
          <div className="ax-login__fields">
            <div className="ax-login__row-2">
              <TextInput label="First name" value={form.first_name} onChange={set("first_name")} />
              <TextInput label="Last name" value={form.last_name} onChange={set("last_name")} />
            </div>
            <TextInput label="Work email" type="email" required value={form.email} onChange={set("email")} error={errors.email} />
          </div>
        </fieldset>
        <fieldset className="ax-login__section">
          <legend>Security</legend>
          <div className="ax-login__fields">
            <TextInput
              label="Password"
              type="password"
              autoComplete="new-password"
              required
              value={form.password}
              onChange={set("password")}
              error={errors.password}
              hint={`At least ${MIN_PASSWORD} characters.`}
            />
            <TextInput
              label="Confirm password"
              type="password"
              autoComplete="new-password"
              required
              value={form.confirm}
              onChange={set("confirm")}
              error={errors.confirm}
            />
          </div>
        </fieldset>
        <Button type="submit" className="ax-login__submit w-full" loading={register.isPending}>
          Submit partner application
        </Button>
        <AuthLegalLinks />
      </form>
    </AuthPageLayout>
  );
}
