import type { ReactNode } from "react";
import { Badge, cx } from "../../components/ui";
import type { InstituteAssignment } from "../../types";

export function prettyStatus(status: string): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export const ASSIGNMENT_STATUS: Record<string, { label: string; tone: "green" | "red" | "amber" | "blue" | "slate" | "brand" }> = {
  invited: { label: "Invited", tone: "blue" },
  pending_candidate_acceptance: { label: "Waiting", tone: "amber" },
  active: { label: "Active", tone: "green" },
  suspended: { label: "Suspended", tone: "amber" },
  released: { label: "Released", tone: "slate" },
  rejected: { label: "Rejected", tone: "red" },
  expired: { label: "Expired", tone: "slate" },
  cancelled: { label: "Cancelled", tone: "slate" },
};

export function assignmentStatus(status: string) {
  return ASSIGNMENT_STATUS[status] ?? { label: prettyStatus(status), tone: "slate" as const };
}

export const RELEASE_CANDIDATE_TITLE = "Release this candidate?";
export const RELEASE_CANDIDATE_TOAST = "Candidate released. They must buy a personal plan to apply.";

export function releaseCandidateMessage(who: string): string {
  return (
    `${who} will no longer be bound to this campus. Their campus package is cancelled and personal billing starts. `
    + "They must buy a candidate plan to apply. Your seats stay with the institute."
  );
}

export function AssignmentBadge({ status }: { status: string }) {
  const meta = assignmentStatus(status);
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function FilterChips({
  options,
  value,
  onChange,
  className,
}: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <div className={cx("flex flex-wrap gap-1.5", className)} role="tablist" aria-label="Filter">
      {options.map((f) => (
        <button
          key={f.value}
          type="button"
          role="tab"
          aria-pressed={value === f.value}
          onClick={() => onChange(f.value)}
          className={cx(
            "rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset transition-colors",
            value === f.value
              ? "bg-brand-600 text-white ring-brand-600"
              : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50",
          )}
        >
          {f.label}
        </button>
      ))}
    </div>
  );
}

export function studentPrimary(row: InstituteAssignment): string {
  return row.candidate_name || row.candidate_email;
}

export function studentSecondary(row: InstituteAssignment): string {
  const bits = [
    row.candidate_name ? row.candidate_email : "",
    row.candidate_phone || "",
  ].filter(Boolean);
  return bits.join(" · ");
}

export function InstitutePending({ children }: { children?: ReactNode }) {
  return (
    <div className="mb-6 rounded-xl bg-amber-50 p-4 ring-1 ring-amber-200">
      <p className="text-sm font-medium text-amber-950">Waiting for ApplyXAI review</p>
      <p className="mt-1 text-sm text-amber-900/80">
        {children ??
          "You can look around. Inviting students and buying seats unlock after approval."}
      </p>
    </div>
  );
}
