import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GraduationCap } from "lucide-react";
import { useState } from "react";
import { TextInput, Toggle } from "../../components/form";
import { Modal } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { formatMoney } from "../../lib/format";
import { errorMessage, fieldErrors } from "../../services/api";
import { admin } from "../../services/endpoints";
import type { AdminPlan, PlanUpdate } from "../../types";

function isInstitutePlan(plan: AdminPlan) {
  return plan.kind === "institute" || (plan.limits.seats ?? 0) > 0;
}

export function AdminPlansPage() {
  const [editing, setEditing] = useState<AdminPlan | null>(null);
  const { data, isLoading, error } = useQuery({ queryKey: ["admin", "plans"], queryFn: admin.plans });
  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;

  const candidates = data.filter((p) => !isInstitutePlan(p));
  const institutes = data.filter(isInstitutePlan);

  return (
    <>
      <PageHeader
        title="Plans"
        description="Candidate plans are sold to job seekers. Training institute plans sell seats for students."
      />
      <div className="space-y-6">
        <CandidatePlanGroup plans={candidates} onEdit={setEditing} />
        <InstitutePlanGroup plans={institutes} onEdit={setEditing} />
      </div>
      {editing && <PlanDialog plan={editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function CandidatePlanGroup({ plans, onEdit }: { plans: AdminPlan[]; onEdit: (plan: AdminPlan) => void }) {
  return (
    <Card title="Candidate plans">
      <p className="-mt-2 mb-4 text-sm text-slate-500">
        Sold to job seekers. Limits apply to that person's own applications and resumes.
      </p>
      {plans.length === 0 ? (
        <EmptyState title="No candidate plans yet" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {plans.map((p) => (
            <article key={p.code} className="flex flex-col rounded-xl bg-slate-50 p-5 ring-1 ring-slate-200">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">{p.name}</p>
                  <p className="text-xs text-slate-500">{p.code}</p>
                </div>
                {p.is_active ? <Badge tone="green">On sale</Badge> : <Badge>Hidden</Badge>}
              </div>
              <p className="mt-4 text-3xl font-semibold tracking-tight text-slate-900">
                {p.price_cents === 0 ? "Free" : formatMoney(p.price_cents, p.currency)}
                {p.price_cents > 0 && (
                  <span className="ml-1.5 text-sm font-normal text-slate-500">/ {p.interval}</span>
                )}
              </p>
              <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-slate-200 pt-4 text-sm">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Applications / month</dt>
                  <dd className="mt-1 font-medium text-slate-900">{p.limits.applications_per_month.toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Resumes</dt>
                  <dd className="mt-1 font-medium text-slate-900">{p.limits.resumes}</dd>
                </div>
              </dl>
              <p className="mt-3 text-xs text-slate-500">
                {p.subscribers === 1 ? "1 subscriber" : `${p.subscribers} subscribers`}
              </p>
              <Button size="sm" variant="secondary" className="mt-3 self-start" onClick={() => onEdit(p)}>Edit</Button>
            </article>
          ))}
        </div>
      )}
    </Card>
  );
}

function packageOf(plan: Pick<AdminPlan, "limits" | "price_cents">, seats = plan.limits.seats ?? 0) {
  const perApps = plan.limits.applications_per_month;
  const perResumes = plan.limits.resumes;
  return {
    seats,
    perApps,
    perResumes,
    packApps: perApps * seats,
    packResumes: perResumes * seats,
    amountCents: plan.price_cents * seats,
  };
}

function InstitutePlanGroup({ plans, onEdit }: { plans: AdminPlan[]; onEdit: (plan: AdminPlan) => void }) {
  return (
    <Card title="Training institute plans">
      <p className="-mt-2 mb-4 text-sm text-slate-500">
        Each plan has a minimum number of students. The amount charged is the per-student price times that minimum.
      </p>
      {plans.length === 0 ? (
        <EmptyState title="No campus plans yet" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {plans.map((p) => {
            const pack = packageOf(p);
            return (
              <article key={p.code} className="flex flex-col rounded-xl bg-slate-50 p-5 ring-1 ring-slate-200">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-900">{p.name}</p>
                    <p className="text-xs text-slate-500">{p.code}</p>
                  </div>
                  {p.is_active ? <Badge tone="green">On sale</Badge> : <Badge>Hidden</Badge>}
                </div>
                <div className="mt-4 flex items-end gap-2">
                  <GraduationCap className="mb-1 h-5 w-5 text-brand-600" aria-hidden />
                  <p className="text-3xl font-semibold tracking-tight text-slate-900">{pack.seats.toLocaleString()}</p>
                  <p className="mb-1 text-sm text-slate-500">minimum students</p>
                </div>
                <p className="mt-1 text-sm text-slate-600">
                  {p.price_cents === 0
                    ? "Free"
                    : `${formatMoney(p.price_cents, p.currency)} / student / ${p.interval}`}
                </p>
                <p className="mt-2 text-lg font-semibold text-slate-900">
                  Amount = {p.price_cents === 0 ? "Free" : `${formatMoney(pack.amountCents, p.currency)} / ${p.interval}`}
                </p>
                <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-slate-200 pt-4 text-sm">
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Per student</dt>
                    <dd className="mt-1 text-slate-900">
                      {pack.perApps.toLocaleString()} applications / month
                      <br />
                      {pack.perResumes.toLocaleString()} resume{pack.perResumes === 1 ? "" : "s"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Package × {pack.seats.toLocaleString()}
                    </dt>
                    <dd className="mt-1 text-slate-900">
                      {pack.packApps.toLocaleString()} applications / month
                      <br />
                      {pack.packResumes.toLocaleString()} resume{pack.packResumes === 1 ? "" : "s"}
                    </dd>
                  </div>
                </dl>
                <p className="mt-3 text-xs text-slate-500">
                  {p.subscribers === 1 ? "1 campus on this plan" : `${p.subscribers} campuses on this plan`}
                </p>
                <Button size="sm" variant="secondary" className="mt-3 self-start" onClick={() => onEdit(p)}>Edit</Button>
              </article>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function PlanDialog({ plan, onClose }: { plan: AdminPlan; onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const institute = isInstitutePlan(plan);
  const free = plan.price_cents === 0 && plan.code === "free";
  const [form, setForm] = useState({
    name: plan.name,
    price: String(plan.price_cents / 100),
    applications: String(plan.limits.applications_per_month),
    resumes: String(plan.limits.resumes),
    seats: String(plan.limits.seats ?? 1),
    is_active: plan.is_active,
    sort_order: plan.sort_order,
  });
  const set = (key: keyof typeof form) => (value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));
  const body: PlanUpdate = {
    name: form.name.trim(),
    price_cents: Math.round(Number(form.price) * 100),
    applications_per_month: Number(form.applications),
    resumes: Number(form.resumes),
    is_active: form.is_active,
    sort_order: form.sort_order,
    ...(institute ? { seats: Number(form.seats) } : {}),
  };
  const save = useMutation({
    mutationFn: () => admin.updatePlan(plan.code, body),
    onSuccess: () => {
      toast.success(`${body.name} saved.`);
      void client.invalidateQueries({ queryKey: ["admin", "plans"] });
      void client.invalidateQueries({ queryKey: ["plans"] });
      void client.invalidateQueries({ queryKey: ["institute", "plans"] });
      onClose();
    },
  });
  const errors = fieldErrors(save.error);
  const priceChanged = body.price_cents !== plan.price_cents;
  const numbers = [body.price_cents, body.applications_per_month, body.resumes, ...(institute ? [body.seats ?? 0] : [])];
  const invalid = !body.name || numbers.some((n) => !Number.isInteger(n) || n < 0) || (institute && (body.seats ?? 0) < 1);

  return (
    <Modal open onClose={onClose} title={`Edit ${plan.name}`} footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={invalid} loading={save.isPending} onClick={() => save.mutate()}>Save</Button>
      </>
    }>
      <div className="space-y-4">
        {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}
        <p className="text-sm text-slate-500">
          {institute
            ? "Price and limits are per student. Amount charged and the package totals are those figures times the minimum number of students."
            : "This plan is sold to individual candidates."}
        </p>
        <TextInput label="Name" value={form.name} onChange={set("name")} maxLength={100} error={errors.name} />
        <TextInput
          label={institute ? `Price per student / ${plan.interval} (${plan.currency})` : `Price per ${plan.interval} (${plan.currency})`}
          type="number" min={0} step="0.01" value={form.price}
          onChange={set("price")} disabled={free} error={errors.price_cents}
          hint={free ? "The Free plan stays free." : priceChanged && plan.subscribers > 0
            ? `New subscribers pay the new price. The ${plan.subscribers} current subscriber${plan.subscribers === 1 ? "" : "s"} keep their price until they change plans.`
            : undefined} />
        <div className="grid gap-4 sm:grid-cols-2">
          {institute && (
            <TextInput label="Minimum students" type="number" min={1} value={form.seats} onChange={set("seats")} error={errors.seats}
                       hint="The campus must buy at least this many student seats." />
          )}
          <TextInput
            label={institute ? "Applications per student / month" : "Applications per month"}
            type="number" min={0} value={form.applications} onChange={set("applications")}
            error={errors.applications_per_month} />
          <TextInput
            label={institute ? "Resumes per student" : "Resumes"}
            type="number" min={0} max={100} value={form.resumes} onChange={set("resumes")} error={errors.resumes} />
        </div>
        {institute && Number.isInteger(body.seats) && (body.seats ?? 0) > 0 && (
          <p className="text-sm text-slate-600">
            Amount = {formatMoney(body.price_cents * (body.seats ?? 0), plan.currency)} / {plan.interval}
            {" "}({body.seats} × {formatMoney(body.price_cents, plan.currency)}).{" "}
            Package: {(body.applications_per_month * (body.seats ?? 0)).toLocaleString()} applications / month and{" "}
            {(body.resumes * (body.seats ?? 0)).toLocaleString()} resumes.
          </p>
        )}
        <Toggle label="On sale" checked={form.is_active} onChange={set("is_active")}
                hint={free ? "Everyone falls back to the Free plan, so it can't be hidden."
                  : "Hidden plans can't be bought. People already on it keep it."} />
      </div>
    </Modal>
  );
}
