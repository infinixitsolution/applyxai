import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Package, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { TextInput, Toggle } from "../../components/form";
import { ConfirmDialog, Modal } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { formatMoney } from "../../lib/format";
import { formatMockInterviewLimit, formatResumeLimit, RESUMES_UNLIMITED } from "../../lib/planLimits";
import { errorMessage, fieldErrors } from "../../services/api";
import { admin } from "../../services/endpoints";
import type { AdminPlan, PlanCreate, PlanKind, PlanUpdate } from "../../types";
import { Table, Td } from "./shared";

function isInstitutePlan(plan: AdminPlan) {
  return plan.kind === "institute" || (plan.limits.seats ?? 0) > 0;
}

function priceLabel(plan: AdminPlan) {
  if (plan.price_cents === 0) return "Free";
  const base = formatMoney(plan.price_cents, plan.currency);
  return isInstitutePlan(plan) ? `${base} / student / ${plan.interval}` : `${base} / ${plan.interval}`;
}

function packageOf(plan: AdminPlan) {
  const seats = plan.limits.seats ?? 0;
  return {
    seats,
    packApps: plan.limits.applications_per_month * seats,
    packMocks: (plan.limits.mock_interviews_per_month ?? 0) * seats,
    amountCents: plan.price_cents * seats,
  };
}

type DialogState =
  | { mode: "create"; kind: PlanKind }
  | { mode: "edit"; plan: AdminPlan }
  | null;

export function AdminPlansPage() {
  const [dialog, setDialog] = useState<DialogState>(null);
  const [deleting, setDeleting] = useState<AdminPlan | null>(null);
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
        <PlanListSection
          title="Candidate plans"
          hint="Sold to job seekers. Set applications, mock interviews, and new resumes per month."
          plans={candidates}
          institute={false}
          onAdd={() => setDialog({ mode: "create", kind: "personal" })}
          onEdit={(plan) => setDialog({ mode: "edit", plan })}
          onDelete={setDeleting}
        />
        <PlanListSection
          title="Training institute plans"
          hint="Each plan has a minimum number of students. The amount charged is the per-student price times that minimum."
          plans={institutes}
          institute
          onAdd={() => setDialog({ mode: "create", kind: "institute" })}
          onEdit={(plan) => setDialog({ mode: "edit", plan })}
          onDelete={setDeleting}
        />
      </div>
      {dialog && <PlanDialog state={dialog} onClose={() => setDialog(null)} />}
      {deleting && (
        <DeletePlanDialog plan={deleting} onClose={() => setDeleting(null)} />
      )}
    </>
  );
}

function PlanListSection({
  title,
  hint,
  plans,
  institute,
  onAdd,
  onEdit,
  onDelete,
}: {
  title: string;
  hint: string;
  plans: AdminPlan[];
  institute: boolean;
  onAdd: () => void;
  onEdit: (plan: AdminPlan) => void;
  onDelete: (plan: AdminPlan) => void;
}) {
  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          <p className="mt-1 text-sm text-slate-500">{hint}</p>
        </div>
        <Button size="sm" onClick={onAdd}>
          <Plus className="h-4 w-4" aria-hidden /> Add plan
        </Button>
      </div>
      {plans.length === 0 ? (
        <EmptyState icon={<Package className="h-10 w-10" />} title="No plans yet">
          Add a package to show it on the public pricing page when it is on sale.
        </EmptyState>
      ) : institute ? (
        <Table head={["Plan", "Price / student", "Min seats", "Package total", "Per student · × seats", "Subscribers", "Status", ""]}>
          {plans.map((p) => {
            const pack = packageOf(p);
            return (
              <tr key={p.code} className="hover:bg-slate-50/80">
                <Td>
                  <p className="font-medium text-slate-900">{p.name}</p>
                  <p className="text-xs text-slate-500">{p.code}</p>
                </Td>
                <Td className="whitespace-nowrap">{priceLabel(p)}</Td>
                <Td>{pack.seats.toLocaleString()}</Td>
                <Td className="whitespace-nowrap">
                  {p.price_cents === 0 ? "Free" : `${formatMoney(pack.amountCents, p.currency)} / ${p.interval}`}
                </Td>
                <Td className="text-sm text-slate-600">
                  {pack.packApps.toLocaleString()} apps / mo
                  <br />
                  {pack.packMocks.toLocaleString()} mock interviews / mo
                  <br />
                  {formatResumeLimit(p.limits.resumes)} resumes / mo per student
                </Td>
                <Td>{p.subscribers.toLocaleString()}</Td>
                <Td>{p.is_active ? <Badge tone="green">On sale</Badge> : <Badge>Hidden</Badge>}</Td>
                <Td className="whitespace-nowrap">
                  <div className="flex justify-end gap-1">
                    <Button size="sm" variant="secondary" onClick={() => onEdit(p)}>Edit</Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={`Delete ${p.name}`}
                      disabled={p.code === "free"}
                      onClick={() => onDelete(p)}
                    >
                      <Trash2 className="h-4 w-4 text-red-600" aria-hidden />
                    </Button>
                  </div>
                </Td>
              </tr>
            );
          })}
        </Table>
      ) : (
        <Table head={["Plan", "Price", "Applications / mo", "Mock interviews / mo", "Resumes / mo", "Subscribers", "Status", ""]}>
          {plans.map((p) => (
            <tr key={p.code} className="hover:bg-slate-50/80">
              <Td>
                <p className="font-medium text-slate-900">{p.name}</p>
                <p className="text-xs text-slate-500">{p.code}</p>
              </Td>
              <Td className="whitespace-nowrap">{priceLabel(p)}</Td>
              <Td>{p.limits.applications_per_month.toLocaleString()}</Td>
              <Td>{formatMockInterviewLimit(p.limits.mock_interviews_per_month ?? 0)}</Td>
              <Td>{formatResumeLimit(p.limits.resumes)}</Td>
              <Td>{p.subscribers.toLocaleString()}</Td>
              <Td>{p.is_active ? <Badge tone="green">On sale</Badge> : <Badge>Hidden</Badge>}</Td>
              <Td className="whitespace-nowrap">
                <div className="flex justify-end gap-1">
                  <Button size="sm" variant="secondary" onClick={() => onEdit(p)}>Edit</Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Delete ${p.name}`}
                    disabled={p.code === "free"}
                    onClick={() => onDelete(p)}
                  >
                    <Trash2 className="h-4 w-4 text-red-600" aria-hidden />
                  </Button>
                </div>
              </Td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  );
}

function PlanDialog({ state, onClose }: { state: NonNullable<DialogState>; onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const isCreate = state.mode === "create";
  const plan = isCreate ? null : state.plan;
  const institute = isCreate ? state.kind === "institute" : isInstitutePlan(state.plan);
  const free = !isCreate && plan!.price_cents === 0 && plan!.code === "free";

  const [form, setForm] = useState(() => {
    if (isCreate) {
      return {
        code: "",
        name: "",
        price: "",
        applications: institute ? "100" : "50",
        mock_interviews: institute ? "10" : "5",
        resumes: "20",
        seats: "10",
        is_active: true,
        sort_order: "100",
      };
    }
    return {
      code: plan!.code,
      name: plan!.name,
      price: String(plan!.price_cents / 100),
      applications: String(plan!.limits.applications_per_month),
      mock_interviews: String(plan!.limits.mock_interviews_per_month ?? 0),
      resumes: String(plan!.limits.resumes),
      seats: String(plan!.limits.seats ?? 1),
      is_active: plan!.is_active,
      sort_order: String(plan!.sort_order),
    };
  });

  const set = (key: keyof typeof form) => (value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));

  const body: PlanUpdate = {
    name: form.name.trim(),
    price_cents: Math.round(Number(form.price) * 100),
    applications_per_month: Number(form.applications),
    mock_interviews_per_month: Number(form.mock_interviews),
    resumes_per_month: Number(form.resumes),
    is_active: form.is_active,
    sort_order: Number(form.sort_order),
    ...(institute ? { seats: Number(form.seats) } : {}),
  };

  const save = useMutation({
    mutationFn: () => {
      if (isCreate) {
        const createBody: PlanCreate = {
          ...body,
          code: form.code.trim().toLowerCase(),
          kind: institute ? "institute" : "personal",
        };
        return admin.createPlan(createBody);
      }
      return admin.updatePlan(plan!.code, body);
    },
    onSuccess: () => {
      toast.success(isCreate ? "Plan created." : `${body.name} saved.`);
      void client.invalidateQueries({ queryKey: ["admin", "plans"] });
      void client.invalidateQueries({ queryKey: ["plans"] });
      void client.invalidateQueries({ queryKey: ["institute", "plans"] });
      onClose();
    },
  });

  const errors = fieldErrors(save.error);
  const priceChanged = !isCreate && body.price_cents !== plan!.price_cents;
  const numbers = [
    body.price_cents,
    body.applications_per_month,
    body.mock_interviews_per_month,
    body.resumes_per_month,
    ...(institute ? [body.seats ?? 0] : []),
  ];
  const codeOk = isCreate ? /^[a-z][a-z0-9_]*$/.test(form.code.trim()) : true;
  const invalid = !body.name || !codeOk || numbers.some((n) => !Number.isInteger(n) || n < 0) || (institute && (body.seats ?? 0) < 1);

  const title = isCreate
    ? `Add ${institute ? "institute" : "candidate"} plan`
    : `Edit ${plan!.name}`;

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={invalid} loading={save.isPending} onClick={() => save.mutate()}>
            {isCreate ? "Create plan" : "Save"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}
        <p className="text-sm text-slate-500">
          {institute
            ? "Price and limits are per student. Package totals are those figures times the minimum number of students."
            : "This plan is sold to individual candidates."}
        </p>
        {isCreate && (
          <TextInput
            label="Plan code"
            value={form.code}
            onChange={set("code")}
            maxLength={32}
            hint="Lowercase letters, numbers, and underscores. Shown in checkout URLs."
            error={errors.code}
          />
        )}
        <TextInput label="Name" value={form.name} onChange={set("name")} maxLength={100} error={errors.name} />
        <TextInput
          label={institute ? `Price per student / month (${isCreate ? "INR" : plan!.currency})` : `Price per month (${isCreate ? "INR" : plan!.currency})`}
          type="number"
          min={0}
          step="0.01"
          value={form.price}
          onChange={set("price")}
          disabled={free}
          error={errors.price_cents}
          hint={
            free
              ? "The Free plan stays free."
              : priceChanged && plan!.subscribers > 0
                ? `New subscribers pay the new price. The ${plan!.subscribers} current subscriber${plan!.subscribers === 1 ? "" : "s"} keep their price until they change plans.`
                : undefined
          }
        />
        <div className="grid gap-4 sm:grid-cols-2">
          {institute && (
            <TextInput
              label="Minimum students"
              type="number"
              min={1}
              value={form.seats}
              onChange={set("seats")}
              error={errors.seats}
              hint="The campus must buy at least this many student seats."
            />
          )}
          <TextInput
            label={institute ? "Applications per student / month" : "Applications per month"}
            type="number"
            min={0}
            value={form.applications}
            onChange={set("applications")}
            error={errors.applications_per_month}
          />
          <TextInput
            label={institute ? "Mock interviews per student / month" : "Mock interviews / month"}
            type="number"
            min={0}
            value={form.mock_interviews}
            onChange={set("mock_interviews")}
            error={errors.mock_interviews_per_month}
            hint="New live mock interview sessions started each calendar month."
          />
          <TextInput
            label={institute ? "Resumes per student / month" : "Resumes / month"}
            type="number"
            min={0}
            value={form.resumes}
            onChange={set("resumes")}
            error={errors.resumes_per_month}
            hint={`New resumes created each calendar month: uploads, styled copies, and AI-tailored versions. Auto-apply copies don't count. ${RESUMES_UNLIMITED.toLocaleString()} means unlimited.`}
          />
          <TextInput
            label="Sort order"
            type="number"
            min={0}
            value={form.sort_order}
            onChange={set("sort_order")}
            hint="Lower numbers appear first on the pricing page."
          />
        </div>
        {institute && Number.isInteger(body.seats) && (body.seats ?? 0) > 0 && (
          <p className="text-sm text-slate-600">
            Amount = {body.price_cents === 0 ? "Free" : `${formatMoney(body.price_cents * (body.seats ?? 0), isCreate ? "INR" : plan!.currency)} / ${isCreate ? "month" : plan!.interval}`}
            {" "}({body.seats} × {formatMoney(body.price_cents, isCreate ? "INR" : plan!.currency)}).{" "}
            Package: {(body.applications_per_month * (body.seats ?? 0)).toLocaleString()} applications / month and{" "}
            {(body.mock_interviews_per_month * (body.seats ?? 0)).toLocaleString()} mock interviews / month, and{" "}
            {formatResumeLimit(body.resumes_per_month)} resumes / month per student.
          </p>
        )}
        <Toggle
          label="On sale"
          checked={form.is_active}
          onChange={set("is_active")}
          hint={
            free
              ? "Everyone falls back to the Free plan, so it can't be hidden."
              : "Hidden plans can't be bought. People already on it keep it."
          }
        />
      </div>
    </Modal>
  );
}

function DeletePlanDialog({ plan, onClose }: { plan: AdminPlan; onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const remove = useMutation({
    mutationFn: () => admin.deletePlan(plan.code),
    onSuccess: () => {
      toast.success(`${plan.name} removed.`);
      void client.invalidateQueries({ queryKey: ["admin", "plans"] });
      void client.invalidateQueries({ queryKey: ["plans"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <ConfirmDialog
      open
      danger
      title={`Delete ${plan.name}?`}
      confirmLabel="Delete plan"
      loading={remove.isPending}
      onClose={onClose}
      onConfirm={() => remove.mutate()}
      message={
        plan.subscribers > 0
          ? "This plan has active subscribers. Hide it instead, or wait until no one is on it."
          : "This permanently removes the plan from the catalogue. It only works if nobody has ever subscribed to it."
      }
    />
  );
}
