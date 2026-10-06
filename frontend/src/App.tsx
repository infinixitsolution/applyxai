import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { GuestOnly, RequireAuth, RequireOnboarded } from "./auth/session";
import { AppShell } from "./layouts/AppShell";
import { PublicLayout } from "./layouts/PublicLayout";
import { ApplicationsPage } from "./pages/app/Applications";
import { AutomationPage } from "./pages/app/Automation";
import { DashboardPage } from "./pages/app/Dashboard";
import { JobsPage } from "./pages/app/Jobs";
import {
  BillingPage, NotFoundPage, NotificationsPage, PreferencesPage, ProfilePage, ResumesPage, SettingsPage,
} from "./pages/app/Pages";
import {
  CheckEmailPage, ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage, VerifyEmailPage,
} from "./pages/auth";
import { LandingPage } from "./pages/Landing";
import { PrivacyPage, RefundPage, TermsPage } from "./pages/Legal";
import { OnboardingPage } from "./pages/Onboarding";

function ScrollToTop() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) {
      window.scrollTo(0, 0);
      return;
    }
    const frame = requestAnimationFrame(() => document.getElementById(hash.slice(1))?.scrollIntoView());
    return () => cancelAnimationFrame(frame);
  }, [pathname, hash]);
  return null;
}

export function App() {
  return (
    <>
    <ScrollToTop />
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<LandingPage />} />
        <Route path="login" element={<GuestOnly><LoginPage /></GuestOnly>} />
        <Route path="register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
        <Route path="check-email" element={<CheckEmailPage />} />
        <Route path="verify-email" element={<VerifyEmailPage />} />
        <Route path="forgot-password" element={<ForgotPasswordPage />} />
        <Route path="reset-password" element={<ResetPasswordPage />} />
        <Route path="privacy" element={<PrivacyPage />} />
        <Route path="terms" element={<TermsPage />} />
        <Route path="refund-policy" element={<RefundPage />} />
        <Route path="pricing" element={<Navigate to="/#pricing" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route path="onboarding" element={<RequireAuth><OnboardingPage /></RequireAuth>} />

      <Route path="app" element={<RequireAuth><RequireOnboarded><AppShell /></RequireOnboarded></RequireAuth>}>
        <Route index element={<DashboardPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="applications" element={<ApplicationsPage />} />
        <Route path="automation" element={<AutomationPage />} />
        <Route path="resumes" element={<ResumesPage />} />
        <Route path="preferences" element={<PreferencesPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="billing" element={<BillingPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
    </>
  );
}
