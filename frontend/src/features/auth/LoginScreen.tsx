import { Eye, EyeOff, Lock, Mail, Sparkles } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Alert, Button } from "../../components/ui";
import { AuthLegalLinks, AuthPageLayout } from "./AuthPageLayout";

export type LoginScreenProps = {
  email: string;
  onEmailChange: (value: string) => void;
  password: string;
  onPasswordChange: (value: string) => void;
  onSubmit: (e: FormEvent) => void;
  loading: boolean;
  registerTo: string;
  showResetSuccess: boolean;
  showVerifiedSuccess: boolean;
  showRegisteredSuccess: boolean;
  errorMessage: ReactNode;
  notVerified: boolean;
  resent: boolean;
  onResendVerification: () => void;
  resendPending: boolean;
  twoFactorStep?: boolean;
  totpCode?: string;
  onTotpCodeChange?: (value: string) => void;
  onBackFromTwoFactor?: () => void;
  twoFactorError?: ReactNode;
};

export function LoginScreen(props: LoginScreenProps) {
  const {
    email,
    onEmailChange,
    password,
    onPasswordChange,
    onSubmit,
    loading,
    registerTo,
    showResetSuccess,
    showVerifiedSuccess,
    showRegisteredSuccess,
    errorMessage,
    notVerified,
    resent,
    onResendVerification,
    resendPending,
    twoFactorStep = false,
    totpCode = "",
    onTotpCodeChange,
    onBackFromTwoFactor,
    twoFactorError,
  } = props;
  const [showPassword, setShowPassword] = useState(false);
  const canSubmit = twoFactorStep ? totpCode.trim().length >= 6 : Boolean(email.trim() && password);

  return (
    <AuthPageLayout
      storyAriaLabel="Why ApplyXAI"
      kicker={
        <>
          <Sparkles size={14} aria-hidden />
          Your workspace
        </>
      }
      storyTitle="Sign in and pick up where you left off."
      storyLead="Run LinkedIn Easy Apply from your PC, track every submission, and optional AI resume tailoring — we never see your LinkedIn password."
      highlights={[
        { title: "Desktop agent", description: "You sign in to LinkedIn locally in Chrome" },
        { title: "Application history", description: "Applied, skipped, and external jobs in one place" },
        { title: "Smart screening", description: "Saved answers plus optional AI for new questions" },
      ]}
      cardHeadingId="ax-login-heading"
      cardTitle="Welcome back"
      cardSubtitle={
        <>
          New here?{" "}
          <Link to={registerTo} className="ax-login__link">
            Start free
          </Link>
        </>
      }
      footer={
        <div className="ax-login__alt">
          <span>Other accounts</span>
          <Link to="/register/institute">Institute</Link>
          <Link to="/register/partner">Partner</Link>
        </div>
      }
    >
      <form className="ax-login__form" onSubmit={onSubmit} noValidate>
        {showResetSuccess && <Alert kind="success">Password updated. Log in with your new password.</Alert>}
        {showVerifiedSuccess && <Alert kind="success">Email verified. You can log in now.</Alert>}
        {showRegisteredSuccess && <Alert kind="success">Your account is ready. Log in to get started.</Alert>}
        {twoFactorError && <Alert kind="error">{twoFactorError}</Alert>}
        {errorMessage && !notVerified && !twoFactorStep && <Alert kind="error">{errorMessage}</Alert>}
        {twoFactorStep && <Alert kind="info">Enter the 6-digit code from your authenticator app.</Alert>}
        {notVerified && (
          <Alert kind="info">
            Please verify your email first. Check your inbox for the link.{" "}
            {resent ? (
              <strong>We&apos;ve sent a new link.</strong>
            ) : (
              <button
                type="button"
                className="ax-login__link ax-login__link-btn"
                onClick={onResendVerification}
                disabled={resendPending}
              >
                Send a new link
              </button>
            )}
          </Alert>
        )}

        {twoFactorStep ? (
          <label className="ax-login__field">
            <span className="ax-login__label">Authenticator code</span>
            <input
              type="text"
              name="totp"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              value={totpCode}
              onChange={(e) => onTotpCodeChange?.(e.target.value)}
              placeholder="123456"
              className="ax-login__input"
            />
          </label>
        ) : (
          <>
            <label className="ax-login__field">
              <span className="ax-login__label">Email</span>
              <span className="ax-login__input-wrap">
                <Mail className="ax-login__input-icon" size={18} aria-hidden />
                <input
                  type="email"
                  name="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => onEmailChange(e.target.value)}
                  placeholder="you@company.com"
                  className="ax-login__input"
                />
              </span>
            </label>

            <label className="ax-login__field">
              <span className="ax-login__label-row">
                <span className="ax-login__label">Password</span>
                <Link to="/forgot-password" className="ax-login__link ax-login__forgot">
                  Forgot?
                </Link>
              </span>
              <span className="ax-login__input-wrap">
                <Lock className="ax-login__input-icon" size={18} aria-hidden />
                <input
                  type={showPassword ? "text" : "password"}
                  name="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => onPasswordChange(e.target.value)}
                  placeholder="Your password"
                  className="ax-login__input ax-login__input-password"
                />
                <button
                  type="button"
                  className="ax-login__reveal"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </span>
            </label>
          </>
        )}

        {twoFactorStep && onBackFromTwoFactor ? (
          <button type="button" className="ax-login__link ax-login__link-btn text-sm" onClick={onBackFromTwoFactor}>
            Back to password
          </button>
        ) : null}

        <Button type="submit" className="ax-login__submit w-full" loading={loading} disabled={!canSubmit}>
          {twoFactorStep ? "Verify and log in" : "Log in to workspace"}
        </Button>

        <AuthLegalLinks />
      </form>
    </AuthPageLayout>
  );
}
