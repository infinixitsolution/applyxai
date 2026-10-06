import { useMutation } from "@tanstack/react-query";
import { MailCheck } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { safeNext, useSetSession } from "../auth/session";
import { TextInput } from "../components/form";
import { Alert, Button, ButtonLink, Spinner } from "../components/ui";
import { AuthCard } from "../layouts/PublicLayout";
import { ApiError, errorMessage, fieldErrors } from "../services/api";
import { auth } from "../services/endpoints";

const MIN_PASSWORD = 10;

function passwordProblem(password: string, confirm: string): Record<string, string> {
  const errors: Record<string, string> = {};
  if (password.length < MIN_PASSWORD) errors.password = `Use at least ${MIN_PASSWORD} characters.`;
  else if (password !== password.trim()) errors.password = "Remove spaces at the start or end.";
  if (confirm !== password) errors.confirm = "Passwords don't match.";
  return errors;
}

export function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const setSession = useSetSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [resent, setResent] = useState(false);

  const login = useMutation({
    mutationFn: () => auth.login(email, password),
    onSuccess: (user) => { setSession(user); navigate(safeNext(params.get("next")), { replace: true }); },
  });
  const resend = useMutation({ mutationFn: () => auth.resendVerification(email), onSuccess: () => setResent(true) });
  const notVerified = login.error instanceof ApiError && login.error.code === "EMAIL_NOT_VERIFIED";

  const submit = (e: FormEvent) => { e.preventDefault(); setResent(false); login.mutate(); };

  return (
    <AuthCard title="Welcome back" subtitle={<>New here? <Link to="/register" className="font-medium text-brand-600 hover:underline">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {params.get("reset") === "1" && <Alert kind="success">Password updated. Log in with your new password.</Alert>}
        {params.get("verified") === "1" && <Alert kind="success">Email verified. You can log in now.</Alert>}
        {login.error && !notVerified && <Alert kind="error">{errorMessage(login.error)}</Alert>}
        {notVerified && (
          <Alert kind="info">
            Please verify your email first. Check your inbox for the link.{" "}
            {resent ? <strong>We've sent a new link.</strong> : (
              <button type="button" className="font-medium underline" onClick={() => resend.mutate()} disabled={resend.isPending}>
                Send a new link
              </button>
            )}
          </Alert>
        )}
        <TextInput label="Email" type="email" autoComplete="email" required value={email} onChange={setEmail} />
        <TextInput label="Password" type="password" autoComplete="current-password" required value={password} onChange={setPassword} />
        <div className="flex justify-end text-sm">
          <Link to="/forgot-password" className="font-medium text-brand-600 hover:underline">Forgot password?</Link>
        </div>
        <Button type="submit" className="w-full" loading={login.isPending} disabled={!email || !password}>Log in</Button>
      </form>
    </AuthCard>
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  const register = useMutation({
    mutationFn: () => auth.register({ email: form.email, password: form.password, first_name: form.first_name, last_name: form.last_name }),
    onSuccess: () => navigate(`/check-email?email=${encodeURIComponent(form.email)}`),
    onError: (error) => setErrors(fieldErrors(error)),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const problems = passwordProblem(form.password, form.confirm);
    if (!form.email.includes("@")) problems.email = "Enter a valid email address.";
    setErrors(problems);
    if (Object.keys(problems).length === 0) register.mutate();
  };

  return (
    <AuthCard title="Create your account" subtitle={<>Already have one? <Link to="/login" className="font-medium text-brand-600 hover:underline">Log in</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {register.error && !Object.keys(fieldErrors(register.error)).length && <Alert kind="error">{errorMessage(register.error)}</Alert>}
        <div className="grid grid-cols-2 gap-3">
          <TextInput label="First name" autoComplete="given-name" value={form.first_name} onChange={set("first_name")} maxLength={100} />
          <TextInput label="Last name" autoComplete="family-name" value={form.last_name} onChange={set("last_name")} maxLength={100} />
        </div>
        <TextInput label="Email" type="email" autoComplete="email" required value={form.email} onChange={set("email")} error={errors.email} />
        <TextInput label="Password" type="password" autoComplete="new-password" required value={form.password}
                   onChange={set("password")} error={errors.password} hint={`At least ${MIN_PASSWORD} characters. A short phrase works well.`} />
        <TextInput label="Confirm password" type="password" autoComplete="new-password" required value={form.confirm}
                   onChange={set("confirm")} error={errors.confirm} />
        <Button type="submit" className="w-full" loading={register.isPending}>Create account</Button>
        <p className="text-center text-xs text-slate-500">
          By creating an account you agree to our <Link to="/terms" className="underline">Terms</Link> and{" "}
          <Link to="/privacy" className="underline">Privacy Policy</Link>.
        </p>
      </form>
    </AuthCard>
  );
}

export function CheckEmailPage() {
  const [params] = useSearchParams();
  const email = params.get("email") ?? "";
  const resend = useMutation({ mutationFn: () => auth.resendVerification(email) });
  return (
    <AuthCard title="Check your email">
      <div className="space-y-4 text-center text-sm text-slate-600">
        <MailCheck className="mx-auto h-12 w-12 text-brand-600" aria-hidden />
        <p>If <strong className="text-slate-900">{email || "your address"}</strong> can receive email, a verification link is on its way. It expires in 24 hours.</p>
        {resend.isSuccess && <Alert kind="success">We've sent another link.</Alert>}
        {email && (
          <Button variant="secondary" onClick={() => resend.mutate()} loading={resend.isPending} disabled={resend.isSuccess}>
            Resend the link
          </Button>
        )}
        <p><Link to="/login" className="font-medium text-brand-600 hover:underline">Back to log in</Link></p>
      </div>
    </AuthCard>
  );
}

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const started = useRef(false);                 // tokens are single-use; StrictMode runs effects twice
  const verify = useMutation({ mutationFn: () => auth.verifyEmail(token) });

  useEffect(() => {
    if (token && !started.current) {
      started.current = true;
      verify.mutate();
    }
  }, [token, verify]);

  return (
    <AuthCard title="Verify your email">
      {!token ? <Alert kind="error">This link is incomplete. Open the link from your email again.</Alert>
        : verify.isPending || verify.isIdle ? <Spinner label="Verifying…" />
        : verify.isSuccess ? (
          <div className="space-y-4 text-center">
            <Alert kind="success">Your email is verified.</Alert>
            <ButtonLink to="/login?verified=1" className="w-full">Log in</ButtonLink>
          </div>
        ) : (
          <div className="space-y-4">
            <Alert kind="error">{errorMessage(verify.error)}</Alert>
            <p className="text-sm text-slate-600">Links expire after 24 hours and work once. Log in to request a new one.</p>
            <ButtonLink to="/login" variant="secondary" className="w-full">Go to log in</ButtonLink>
          </div>
        )}
    </AuthCard>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const forgot = useMutation({ mutationFn: () => auth.forgotPassword(email) });
  return (
    <AuthCard title="Reset your password" subtitle="We'll email you a link to choose a new password.">
      {forgot.isSuccess ? (
        <div className="space-y-4">
          <Alert kind="success">If an account exists for {email}, a reset link is on its way. It expires in 60 minutes.</Alert>
          <ButtonLink to="/login" variant="secondary" className="w-full">Back to log in</ButtonLink>
        </div>
      ) : (
        <form onSubmit={(e) => { e.preventDefault(); forgot.mutate(); }} className="space-y-4" noValidate>
          {forgot.error && <Alert kind="error">{errorMessage(forgot.error)}</Alert>}
          <TextInput label="Email" type="email" autoComplete="email" required value={email} onChange={setEmail} />
          <Button type="submit" className="w-full" loading={forgot.isPending} disabled={!email.includes("@")}>Send reset link</Button>
          <p className="text-center text-sm"><Link to="/login" className="font-medium text-brand-600 hover:underline">Back to log in</Link></p>
        </form>
      )}
    </AuthCard>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const setSession = useSetSession();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const reset = useMutation({
    mutationFn: () => auth.resetPassword(token, password),
    onSuccess: () => { setSession(null); navigate("/login?reset=1", { replace: true }); },
    onError: (error) => setErrors({ ...fieldErrors(error), password: fieldErrors(error).new_password ?? "" }),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const problems = passwordProblem(password, confirm);
    setErrors(problems);
    if (!Object.keys(problems).length) reset.mutate();
  };

  if (!token) {
    return <AuthCard title="Reset your password"><Alert kind="error">This link is incomplete. <Link to="/forgot-password" className="underline">Request a new one</Link>.</Alert></AuthCard>;
  }
  return (
    <AuthCard title="Choose a new password" subtitle="This signs you out on every device.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        {reset.error && <Alert kind="error">{errorMessage(reset.error)}{" "}
          {reset.error instanceof ApiError && reset.error.code === "INVALID_TOKEN" && <Link to="/forgot-password" className="underline">Request a new link</Link>}
        </Alert>}
        <TextInput label="New password" type="password" autoComplete="new-password" value={password} onChange={setPassword}
                   error={errors.password || undefined} hint={`At least ${MIN_PASSWORD} characters.`} />
        <TextInput label="Confirm new password" type="password" autoComplete="new-password" value={confirm} onChange={setConfirm} error={errors.confirm} />
        <Button type="submit" className="w-full" loading={reset.isPending}>Update password</Button>
      </form>
    </AuthCard>
  );
}
