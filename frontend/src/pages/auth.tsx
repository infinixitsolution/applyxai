import { useMutation } from "@tanstack/react-query";
import { MailCheck, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { consumeNext, homeFor, rememberNext, safeNext, storedNext, useSetSession, withNext } from "../auth/session";
import { TextInput } from "../components/form";
import { Alert, Button, ButtonLink, Spinner } from "../components/ui";
import { AuthShell, CheckEmailAside, PasswordAside } from "../features/auth";
import { AuthLegalLinks, AuthPageLayout } from "../features/auth/AuthPageLayout";
import { LoginScreen } from "../features/auth/LoginScreen";
import { REGISTER_STORY } from "../features/auth/registerStories";
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
    onSuccess: (user) => {
      const next = params.get("next") ?? consumeNext();
      consumeNext();
      setSession(user);
      navigate(safeNext(next, homeFor(user)), { replace: true });
    },
  });
  const resend = useMutation({ mutationFn: () => auth.resendVerification(email), onSuccess: () => setResent(true) });
  const notVerified = login.error instanceof ApiError && login.error.code === "EMAIL_NOT_VERIFIED";

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setResent(false);
    login.mutate();
  };

  const registerTo = withNext("/register", params.get("next"));

  return (
    <LoginScreen
      email={email}
      onEmailChange={setEmail}
      password={password}
      onPasswordChange={setPassword}
      onSubmit={submit}
      loading={login.isPending}
      registerTo={registerTo}
      showResetSuccess={params.get("reset") === "1"}
      showVerifiedSuccess={params.get("verified") === "1"}
      showRegisteredSuccess={params.get("registered") === "1"}
      errorMessage={login.error && !notVerified ? errorMessage(login.error) : null}
      notVerified={notVerified}
      resent={resent}
      onResendVerification={() => resend.mutate()}
      resendPending={resend.isPending}
    />
  );
}

export function RegisterPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = params.get("next");
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  const register = useMutation({
    mutationFn: () =>
      auth.register({
        email: form.email,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
      }),
    onSuccess: (result) => {
      rememberNext(next);
      navigate(
        result.verification_required === false
          ? withNext("/login?registered=1", next)
          : withNext(`/check-email?email=${encodeURIComponent(form.email)}`, next),
      );
    },
    onError: (error) => setErrors(fieldErrors(error)),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const problems = passwordProblem(form.password, form.confirm);
    if (!form.email.includes("@")) problems.email = "Enter a valid email address.";
    setErrors(problems);
    if (Object.keys(problems).length === 0) register.mutate();
  };

  const story = REGISTER_STORY.candidate;

  return (
    <AuthPageLayout
      storyAriaLabel="Candidate signup"
      kicker={story.kicker}
      storyTitle={story.title}
      storyLead={story.lead}
      highlights={story.highlights}
      trustSub={story.trustSub}
      registerTabs="candidate"
      cardHeadingId="ax-register-candidate"
      cardTitle="Apply smarter on LinkedIn"
      cardSubtitle={
        <>
          Already registered?{" "}
          <Link to={withNext("/login", next)} className="ax-login__link">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="ax-login__form ax-login__form--register" noValidate>
        {register.error && !Object.keys(fieldErrors(register.error)).length && (
          <Alert kind="error">{errorMessage(register.error)}</Alert>
        )}
        <fieldset className="ax-login__section">
          <legend>About you</legend>
          <div className="ax-login__fields">
            <div className="ax-login__row-2">
              <TextInput label="First name" autoComplete="given-name" value={form.first_name} onChange={set("first_name")} maxLength={100} />
              <TextInput label="Last name" autoComplete="family-name" value={form.last_name} onChange={set("last_name")} maxLength={100} />
            </div>
            <TextInput label="Email" type="email" autoComplete="email" required value={form.email} onChange={set("email")} error={errors.email} />
          </div>
        </fieldset>
        <fieldset className="ax-login__section">
          <legend>Password</legend>
          <div className="ax-login__fields">
            <TextInput
              label="Password"
              type="password"
              autoComplete="new-password"
              required
              value={form.password}
              onChange={set("password")}
              error={errors.password}
              hint={`At least ${MIN_PASSWORD} characters. A short phrase works well.`}
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
          Create account
        </Button>
        <AuthLegalLinks />
      </form>
    </AuthPageLayout>
  );
}

export function CheckEmailPage() {
  const [params] = useSearchParams();
  const email = params.get("email") ?? "";
  const resend = useMutation({ mutationFn: () => auth.resendVerification(email) });
  return (
    <AuthShell
      brandTagline="Verify your email"
      kicker="Check your inbox"
      title="We sent you a link"
      aside={<CheckEmailAside />}
    >
      <div className="auth-flow">
        <div className="auth-status-icon auth-status-icon-mail" aria-hidden>
          <MailCheck strokeWidth={1.75} />
        </div>
        <p className="auth-flow-lead">
          If <strong>{email || "your address"}</strong> can receive mail, tap the verification link we sent. It expires in{" "}
          <strong>24 hours</strong>.
        </p>
        {resend.isSuccess && <Alert kind="success">We've sent another link.</Alert>}
        {email && (
          <Button
            variant="secondary"
            className="auth-secondary w-full"
            onClick={() => resend.mutate()}
            loading={resend.isPending}
            disabled={resend.isSuccess}
          >
            Resend verification email
          </Button>
        )}
        <p className="auth-flow-foot">
          <Link to={withNext("/login", params.get("next") ?? storedNext())} className="auth-text-link">
            Back to log in
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const started = useRef(false);
  const verify = useMutation({ mutationFn: () => auth.verifyEmail(token) });

  useEffect(() => {
    if (token && !started.current) {
      started.current = true;
      verify.mutate();
    }
  }, [token, verify]);

  return (
    <AuthShell brandTagline="Email verification" kicker="One quick step" title="Verify your email" aside={<CheckEmailAside />}>
      {!token ? (
        <Alert kind="error">This link is incomplete. Open the link from your email again.</Alert>
      ) : verify.isPending || verify.isIdle ? (
        <div className="auth-flow">
          <Spinner label="Verifying your email…" />
        </div>
      ) : verify.isSuccess ? (
        <div className="auth-flow">
          <div className="auth-status-icon auth-status-icon-ok" aria-hidden>
            <ShieldCheck strokeWidth={1.75} />
          </div>
          <Alert kind="success">Your email is verified. You're ready to log in.</Alert>
          <ButtonLink to={withNext("/login?verified=1", storedNext())} className="auth-primary w-full">
            Continue to log in
          </ButtonLink>
        </div>
      ) : (
        <div className="auth-flow">
          <Alert kind="error">{errorMessage(verify.error)}</Alert>
          <p className="auth-flow-lead">Links expire after 24 hours and work once. Log in to request a new one.</p>
          <ButtonLink to="/login" variant="secondary" className="auth-secondary w-full">
            Go to log in
          </ButtonLink>
        </div>
      )}
    </AuthShell>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const forgot = useMutation({ mutationFn: () => auth.forgotPassword(email) });
  return (
    <AuthShell
      brandTagline="Password recovery"
      kicker="Forgot password"
      title="We'll email you a reset link"
      subtitle="Enter the address on your account. If we find a match, you'll get instructions within a minute."
      aside={<PasswordAside />}
    >
      {forgot.isSuccess ? (
        <div className="auth-flow">
          <Alert kind="success">
            If an account exists for <strong>{email}</strong>, a reset link is on its way. It expires in 60 minutes.
          </Alert>
          <ButtonLink to="/login" variant="secondary" className="auth-secondary w-full">
            Back to log in
          </ButtonLink>
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            forgot.mutate();
          }}
          className="auth-form"
          noValidate
        >
          {forgot.error && <Alert kind="error">{errorMessage(forgot.error)}</Alert>}
          <TextInput label="Email" type="email" autoComplete="email" required value={email} onChange={setEmail} />
          <Button type="submit" className="auth-primary w-full" loading={forgot.isPending} disabled={!email.includes("@")}>
            Send reset link
          </Button>
          <p className="auth-flow-foot">
            <Link to="/login" className="auth-text-link">
              Back to log in
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
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
    onSuccess: () => {
      setSession(null);
      navigate("/login?reset=1", { replace: true });
    },
    onError: (error) => setErrors({ ...fieldErrors(error), password: fieldErrors(error).new_password ?? "" }),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const problems = passwordProblem(password, confirm);
    setErrors(problems);
    if (!Object.keys(problems).length) reset.mutate();
  };

  if (!token) {
    return (
      <AuthShell brandTagline="Password reset" title="Reset your password" aside={<PasswordAside />}>
        <Alert kind="error">
          This link is incomplete.{" "}
          <Link to="/forgot-password" className="auth-text-link">
            Request a new one
          </Link>
          .
        </Alert>
      </AuthShell>
    );
  }
  return (
    <AuthShell
      brandTagline="New password"
      kicker="Almost done"
      title="Choose a new password"
      subtitle="You'll be signed out on every device after this change."
      aside={<PasswordAside />}
    >
      <form onSubmit={submit} className="auth-form" noValidate>
        {reset.error && (
          <Alert kind="error">
            {errorMessage(reset.error)}{" "}
            {reset.error instanceof ApiError && reset.error.code === "INVALID_TOKEN" && (
              <Link to="/forgot-password" className="auth-text-link">
                Request a new link
              </Link>
            )}
          </Alert>
        )}
        <TextInput
          label="New password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
          error={errors.password || undefined}
          hint={`At least ${MIN_PASSWORD} characters.`}
        />
        <TextInput
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={setConfirm}
          error={errors.confirm}
        />
        <Button type="submit" className="auth-primary w-full" loading={reset.isPending}>
          Update password
        </Button>
      </form>
    </AuthShell>
  );
}