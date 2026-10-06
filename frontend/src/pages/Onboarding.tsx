import { useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import { Button, Card, cx } from "../components/ui";
import { ApplicationPreferencesForm } from "../features/ApplicationPreferencesForm";
import { ProfileForm } from "../features/ProfileForm";
import { ResumeManager } from "../features/ResumeManager";
import { SearchPreferencesForm } from "../features/SearchPreferencesForm";

const STEPS = [
  { id: "profile", title: "Your profile", description: "The basics employers see on your applications." },
  { id: "resume", title: "Resume", description: "Upload the resume to attach to applications. You can add more later." },
  { id: "search", title: "Job preferences", description: "Which jobs the automation should look for." },
  { id: "answers", title: "Application answers", description: "Answers to common screening questions. You can skip this and fill it in later." },
] as const;

export function OnboardingPage() {
  const [step, setStep] = useState(0);
  const navigate = useNavigate();
  const client = useQueryClient();
  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const finish = () => {
    client.invalidateQueries({ queryKey: ["dashboard"] });
    navigate("/app", { replace: true });
  };
  const current = STEPS[step];

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-3xl items-center px-4"><Logo to="/onboarding" /></div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10">
        <ol className="mb-8 grid grid-cols-4 gap-2" aria-label="Setup progress">
          {STEPS.map((s, i) => (
            <li key={s.id} aria-current={i === step ? "step" : undefined}>
              <button type="button" disabled={i > step} onClick={() => setStep(i)} className="w-full text-left disabled:cursor-default">
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
          {current.id === "profile" && <Card><ProfileForm onSaved={next} submitLabel="Save and continue" /></Card>}
          {current.id === "resume" && (
            <Card>
              <ResumeManager />
              <div className="mt-6 flex justify-end gap-2 border-t border-slate-100 pt-4">
                <Button variant="ghost" onClick={next}>Skip for now</Button>
                <Button onClick={next}>Continue</Button>
              </div>
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
