import { useEffect, useState } from "react";
import { Spinner } from "../components/ui";
import { ANALYSIS_PIPELINE_STEPS } from "./mockInterviewReportMetrics";

export function MockInterviewAnalysisProgress({ title = "Generating your interview report" }: { title?: string }) {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setStepIndex((i) => (i + 1) % ANALYSIS_PIPELINE_STEPS.length);
    }, 2800);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="mx-auto flex max-w-lg flex-col items-center px-4 py-16 text-center">
      <Spinner />
      <h2 className="mt-6 text-xl font-semibold text-slate-900">{title}</h2>
      <p className="mt-2 text-sm text-slate-600">
        This usually takes 30–90 seconds. We analyze your full transcript, 100 answer rubric parameters, and up to 12
        camera snapshots for on-camera behavior.
      </p>
      <ol className="mt-8 w-full space-y-2 text-left text-sm">
        {ANALYSIS_PIPELINE_STEPS.map((label, i) => (
          <li
            key={label}
            className={
              i === stepIndex
                ? "rounded-lg bg-brand-50 px-3 py-2 font-medium text-brand-900 ring-1 ring-brand-200"
                : i < stepIndex
                  ? "px-3 py-2 text-slate-500 line-through decoration-slate-300"
                  : "px-3 py-2 text-slate-600"
            }
          >
            {label}
          </li>
        ))}
      </ol>
    </div>
  );
}
