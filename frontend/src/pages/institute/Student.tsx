import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Briefcase, CheckCircle2, MinusCircle, XCircle } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ConfirmDialog } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { Alert, Button, PageHeader, Spinner, StatCard } from "../../components/ui";
import {
  ApplicationsChart,
  CandidateHeader,
  CandidateJourney,
  CandidateProfile,
  CandidateStats,
  RecentApplications,
} from "../admin/UserCandidate";
import { errorMessage } from "../../services/api";
import { institute } from "../../services/endpoints";
import type { AdminUser } from "../../types";
import { AssignmentBadge, RELEASE_CANDIDATE_TITLE, RELEASE_CANDIDATE_TOAST, releaseCandidateMessage } from "./campusUi";

export function InstituteStudentPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const client = useQueryClient();
  const [confirm, setConfirm] = useState<{ title: string; message: string; confirm: string; danger: boolean; run: () => void } | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ["institute", "student", id],
    queryFn: () => institute.student(id),
    enabled: Boolean(id),
  });
  const release = useMutation({
    mutationFn: () => institute.release(id),
    onSuccess: () => {
      setConfirm(null);
      void client.invalidateQueries({ queryKey: ["institute"] });
      toast.success(RELEASE_CANDIDATE_TOAST);
      navigate("/institute/students");
    },
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });
  const suspend = useMutation({
    mutationFn: () => institute.suspend(id),
    onSuccess: () => {
      setConfirm(null);
      void client.invalidateQueries({ queryKey: ["institute"] });
      toast.success("Student suspended.");
    },
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });

  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;

  const { assignment, user, activity, candidate } = data;
  const name = [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim() || assignment.candidate_name || assignment.candidate_email;
  const headerUser: AdminUser | null = user ? {
    id: user.id,
    email: user.email,
    first_name: user.first_name,
    last_name: user.last_name,
    is_active: user.is_active,
    is_verified: user.is_verified,
    is_admin: false,
    created_at: user.created_at || assignment.created_at,
    last_login_at: user.last_login_at,
    plan: "campus",
    plan_name: "Campus",
    applications_this_month: activity.applied,
  } : null;
  const canSuspend = assignment.status === "active";
  const canRelease = ["active", "invited", "pending_candidate_acceptance", "suspended"].includes(assignment.status);
  const busy = release.isPending || suspend.isPending;

  return (
    <>
      <Link to="/institute/students" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700">
        <ArrowLeft className="h-4 w-4" aria-hidden /> All students
      </Link>
      <PageHeader
        title={name}
        description={assignment.candidate_email}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <AssignmentBadge status={assignment.status} />
            {canSuspend && (
              <Button size="sm" variant="ghost" onClick={() => setConfirm({
                title: "Suspend this student?", confirm: "Suspend", danger: true,
                message: `${assignment.candidate_email} loses this campus seat until you invite them again or they are reassigned.`,
                run: () => suspend.mutate(),
              })}>Suspend</Button>
            )}
            {canRelease && (
              <Button size="sm" variant="secondary" onClick={() => setConfirm({
                title: RELEASE_CANDIDATE_TITLE, confirm: "Release", danger: true,
                message: releaseCandidateMessage(assignment.candidate_email),
                run: () => release.mutate(),
              })}>Release</Button>
            )}
          </div>
        }
      />

      {headerUser && <CandidateHeader user={headerUser} candidate={candidate ?? undefined} />}
      {candidate?.journey && <CandidateJourney journey={candidate.journey} />}

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={<Briefcase className="h-4 w-4" aria-hidden />} label="Jobs searched" value={activity.searched.toLocaleString()} sub="Jobs found for this student" />
        <StatCard icon={<CheckCircle2 className="h-4 w-4" aria-hidden />} label="Applied" value={activity.applied.toLocaleString()}
                  sub={activity.success_rate == null ? "Easy Apply submitted" : `${Math.round(activity.success_rate * 100)}% of applied + failed`} />
        <StatCard icon={<MinusCircle className="h-4 w-4" aria-hidden />} label="Skipped" value={activity.skipped.toLocaleString()} sub="Passed over during runs" />
        <StatCard icon={<XCircle className="h-4 w-4" aria-hidden />} label="Failed" value={activity.failed.toLocaleString()} sub="Apply attempts that did not go through" />
      </div>

      {candidate && (
        <div className="space-y-6">
          <CandidateStats candidate={candidate} />
          {candidate.applications_daily.some((d) => d.applied || d.failed) && (
            <ApplicationsChart days={candidate.applications_daily} />
          )}
          <CandidateProfile candidate={candidate} />
          <RecentApplications items={candidate.recent_applications} />
        </div>
      )}

      {confirm && (
        <ConfirmDialog open title={confirm.title} message={confirm.message} confirmLabel={confirm.confirm}
                       danger={confirm.danger} loading={busy} onConfirm={confirm.run} onClose={() => setConfirm(null)} />
      )}
    </>
  );
}
