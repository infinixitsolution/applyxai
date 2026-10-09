import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { homeFor, useSession } from "../auth/session";
import { Logo } from "../components/Logo";
import { Button, Card, cx, Spinner } from "../components/ui";
import { ApplicationPreferencesForm } from "../features/ApplicationPreferencesForm";
import { ProfileForm } from "../features/ProfileForm";
import { CandidateWelcomeModal } from "../features/CandidateWelcomeModal";
import { ResumeManager } from "../features/ResumeManager";
import { SearchPreferencesForm } from "../features/SearchPreferencesForm";
import { profile as profileApi, resumes as resumesApi } from "../services/endpoints";

const STEPS = [
  { id: "resume", title: "Resume", description: "Upload your resume first — we use it to pre-fill your profile and cover letter." },
  { id: "profile", title: "Your profile", description: "Check and edit what we pulled from your resume." },
  { id: "search", title: "Job preferences", description: "Which jobs the automation should look for." },
  { id: "answers", title: "Application answers", description: "Screening answers and your default cover letter. You can skip and fill these in later." },
] as const;

export function OnboardingPage() {
  const { data: user } = useSession();
  const [step, setStep] = useState(0);
  const navigate = useNavigate();
  const client = useQueryClient();
  const { data: resumeList, isLoading: resumesLoading } = useQuery({
    queryKey: ["resumes"],
    queryFn: resumesApi.list,
  });
  const hasResume = (resumeList?.resumes.length ?? 0) > 0;
  if (user && user.workspace && user.workspace !== "app") {
    return <Navigate to={homeFor(user)} replace />;
  }

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const finish = () => {
    client.invalidateQueries({ queryKey: ["dashboard"] });
    navigate("/app", { replace: true });
  };
  const current = STEPS[step];

  const continueFromResume = async () => {
    if (!hasResume || !resumeList) return;
    const pick = resumeList.resumes.find((r) => r.is_default) ?? resumeList.resumes[0];
    const profile = await profileApi.get();
    const needsIntake = !profile.phone?.trim() && !profile.summary?.trim();
    if (needsIntake) {
      await resumesApi.intake(pick.id, true);
      client.invalidateQueries({ queryKey: ["profile"] });
      client.invalidateQueries({ queryKey: ["preferences", "application"] });
    }
    next();
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <CandidateWelcomeModal />
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-3xl items-center px-3 sm:px-4"><Logo to="/onboarding" /></div>
      </header>
      <main className="mx-auto max-w-3xl px-3 py-8 sm:px-4 sm:py-10">
        <ol className="mb-8 grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Setup progress">
          {STEPS.map((s, i) => (
            <li key={s.id} aria-current={i === step ? "step" : undefined}>
              <button
                type="button"
                disabled={i > step || (i > 0 && !hasResume)}
                onClick={() => setStep(i)}
                className="w-full text-left disabled:cursor-default"
              >
                <span className={cx("block h-1.5 rounded-full", i <= step ? "bg-brand-600" : "bg-slate-200")} />
                <span className={cx("mt-2 flex items-center gap-1 text-xs font-medium", i <= step ? "text-brand-700" : "text-slate-400")}>
                  {i < step && <Check className="h-3.5 w-3.5" aria-hidden />}
                  <span className="hidden sm:inline">{s.title}</span>
                  <span className="sm:hidden">{i + 1}</span>
                </span>
              </button>
            </li>
          ))}
        </ol>

        <h1 className="text-2xl font-semibold tracking-tight">{current.title}</h1>
        <p className="mt-1 text-sm text-slate-500">Step {step + 1} of {STEPS.length} · {current.description}</p>

        <div className="mt-6">
          {current.id === "resume" && (
            <Card>
              {resumesLoading ? (
                <Spinner />
              ) : (
                <>
                  <ResumeManager onboarding onIntakeDone={next} />
                  <div className="mt-6 flex justify-end gap-2 border-t border-slate-100 pt-4">
                    <Button onClick={() => void continueFromResume()} disabled={!hasResume}>
                      Continue
                    </Button>
                  </div>
                </>
              )}
            </Card>
          )}
          {current.id === "profile" && (
            <Card>
              <ProfileForm onSaved={next} submitLabel="Save and continue" />
            </Card>
          )}
          {current.id === "search" && <Card><SearchPreferencesForm onSaved={next} submitLabel="Save and continue" /></Card>}
          {current.id === "answers" && (
            <>
              <ApplicationPreferencesForm onSaved={finish} submitLabel="Finish setup" />
              <div className="mt-2 flex justify-end"><Button variant="ghost" onClick={finish}>Skip and go to dashboard</Button></div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
