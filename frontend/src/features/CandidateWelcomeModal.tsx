import { Bot, FileText, Laptop, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { useSession } from "../auth/session";
import { Modal } from "../components/Modal";
import { Button } from "../components/ui";
import { dismissCandidateWelcomeForSession, isCandidateWelcomeDismissed } from "../lib/candidateWelcome";

const STEPS = [
  {
    icon: FileText,
    title: "Upload your resume",
    text: "Start with a PDF or DOCX. We read it (including scanned PDFs with OCR) to pre-fill your profile and cover letter.",
  },
  {
    icon: SlidersHorizontal,
    title: "Set job preferences & answers",
    text: "Choose titles, locations, and LinkedIn filters, then save screening answers the automation can reuse.",
  },
  {
    icon: Laptop,
    title: "Install the desktop agent",
    text: "After setup, download ApplyXAI Agent for Windows from the header in your dashboard. Runs happen in Chrome on your PC.",
  },
  {
    icon: Bot,
    title: "Connect & start a run",
    text: "Open Automation, connect this computer, and start a run. Sign in to LinkedIn in the agent's browser — we never see your password.",
  },
  {
    icon: ShieldCheck,
    title: "Stay in control",
    text: "Use practice runs, pause or stop anytime, and review every application on your dashboard.",
  },
] as const;

export function CandidateWelcomeModal() {
  const { data: user } = useSession();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!user?.id) return;
    if (user.workspace && user.workspace !== "app") return;
    if (isCandidateWelcomeDismissed(user.id)) return;
    setOpen(true);
  }, [user?.id, user?.workspace]);

  const close = () => {
    if (user?.id) dismissCandidateWelcomeForSession(user.id);
    setOpen(false);
  };

  if (!open) return null;

  return (
    <Modal
      open={open}
      onClose={close}
      wide
      title="Welcome — how ApplyXAI works"
      footer={
        <>
          <Button variant="secondary" onClick={close}>Remind me later</Button>
          <Button onClick={close}>Start setup</Button>
        </>
      }
    >
      <p className="mb-4 text-slate-600">
        You're almost ready to automate LinkedIn Easy Apply. Follow the steps on this page, then use the desktop agent to run
        applications from your own browser.
      </p>
      <ol className="space-y-4">
        {STEPS.map((step, i) => (
          <li key={step.title} className="flex gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100">
              <step.icon className="h-4 w-4" aria-hidden />
            </span>
            <div>
              <p className="font-medium text-slate-900">
                {i + 1}. {step.title}
              </p>
              <p className="mt-0.5 text-slate-600">{step.text}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-4 text-xs text-slate-500">
        After you finish these setup steps, open <strong>Automation</strong> in the sidebar to connect your computer and start applying.
      </p>
    </Modal>
  );
}
