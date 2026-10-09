import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { GuestOnly, RequireAdmin, RequireAuth, RequireInstitute, RequireOnboarded, RequirePartner } from "./auth/session";
import { AppShell } from "./layouts/AppShell";
import { PublicLayout } from "./layouts/PublicLayout";
import { AdminApplicationsPage, AdminRunsPage, AdminSubscriptionsPage } from "./pages/admin/Lists";
import { AdminOverviewPage } from "./pages/admin/Overview";
import { AdminPlansPage } from "./pages/admin/Plans";
import { AdminSystemPage } from "./pages/admin/System";
import { AdminInstitutePage, AdminInstitutesPage, AdminPartnerPage, AdminPartnersPage } from "./pages/admin/Orgs";
import { AdminUserPage, AdminUsersPage } from "./pages/admin/Users";
import {
  InstituteDashboardPage, InstituteInvitationsPage, InstituteProfilePage, InstituteReportsPage,
  InstituteSeatsPage, InstituteSettingsPage, InstituteStudentsPage, InstituteSubscriptionPage,
} from "./pages/institute/Pages";
import {
  PartnerCampaignsPage, PartnerCommissionsPage, PartnerDashboardPage, PartnerInstitutesPage,
  PartnerKycPage, PartnerLinksPage, PartnerMarketingPage, PartnerPayoutsPage, PartnerProfilePage,
  PartnerReferralsPage, PartnerSettingsPage, PartnerTaxPage,
} from "./pages/partner/Pages";
import { InstituteRegisterPage, PartnerRegisterPage } from "./pages/RegisterWorkspaces";
import { InvitePage } from "./pages/Invite";
import { ReferralPage } from "./pages/Referral";
import { ApplicationsPage } from "./pages/app/Applications";
import { AgentConnectPage } from "./pages/app/AgentConnect";
import { AutomationPage } from "./pages/app/Automation";
import { BillingPage } from "./pages/app/Billing";
import { DashboardPage } from "./pages/app/Dashboard";
import { JobsPage } from "./pages/app/Jobs";
import {
  NotFoundPage, NotificationsPage, PreferencesPage, ProfilePage, ResumesPage, SettingsPage,
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
        <Route path="register/institute" element={<GuestOnly><InstituteRegisterPage /></GuestOnly>} />
        <Route path="register/partner" element={<GuestOnly><PartnerRegisterPage /></GuestOnly>} />
        <Route path="r/:code" element={<ReferralPage />} />
        <Route path="invite/:token" element={<InvitePage />} />
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
        <Route path="automation/connect" element={<AgentConnectPage />} />
        <Route path="resumes" element={<ResumesPage />} />
        <Route path="preferences" element={<PreferencesPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="billing" element={<BillingPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route path="admin" element={<RequireAuth><RequireAdmin><AppShell variant="admin" /></RequireAdmin></RequireAuth>}>
        <Route index element={<AdminOverviewPage />} />
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="users/:id" element={<AdminUserPage />} />
        <Route path="institutes" element={<AdminInstitutesPage />} />
        <Route path="institutes/:id" element={<AdminInstitutePage />} />
        <Route path="partners" element={<AdminPartnersPage />} />
        <Route path="partners/:id" element={<AdminPartnerPage />} />
        <Route path="subscriptions" element={<AdminSubscriptionsPage />} />
        <Route path="runs" element={<AdminRunsPage />} />
        <Route path="applications" element={<AdminApplicationsPage />} />
        <Route path="plans" element={<AdminPlansPage />} />
        <Route path="system" element={<AdminSystemPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route path="institute" element={<RequireAuth><RequireInstitute><AppShell variant="institute" /></RequireInstitute></RequireAuth>}>
        <Route index element={<InstituteDashboardPage />} />
        <Route path="students" element={<InstituteStudentsPage />} />
        <Route path="invitations" element={<InstituteInvitationsPage />} />
        <Route path="seats" element={<InstituteSeatsPage />} />
        <Route path="subscription" element={<InstituteSubscriptionPage />} />
        <Route path="reports" element={<InstituteReportsPage />} />
        <Route path="profile" element={<InstituteProfilePage />} />
        <Route path="settings" element={<InstituteSettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route path="partner" element={<RequireAuth><RequirePartner><AppShell variant="partner" /></RequirePartner></RequireAuth>}>
        <Route index element={<PartnerDashboardPage />} />
        <Route path="institutes" element={<PartnerInstitutesPage />} />
        <Route path="referrals" element={<PartnerReferralsPage />} />
        <Route path="campaigns" element={<PartnerCampaignsPage />} />
        <Route path="commissions" element={<PartnerCommissionsPage />} />
        <Route path="payouts" element={<PartnerPayoutsPage />} />
        <Route path="marketing" element={<PartnerMarketingPage />} />
        <Route path="links" element={<PartnerLinksPage />} />
        <Route path="profile" element={<PartnerProfilePage />} />
        <Route path="kyc" element={<PartnerKycPage />} />
        <Route path="tax" element={<PartnerTaxPage />} />
        <Route path="settings" element={<PartnerSettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
    </>
  );
}
