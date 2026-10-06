import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { TextInput, Toggle } from "../../components/form";
import { Modal } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, Card, PageHeader, Spinner } from "../../components/ui";
import { formatMoney } from "../../lib/format";
import { errorMessage, fieldErrors } from "../../services/api";
import { admin } from "../../services/endpoints";
import type { AdminPlan, PlanUpdate } from "../../types";
import { Table, Td } from "./shared";

export function AdminPlansPage() {
  const [editing, setEditing] = useState<AdminPlan | null>(null);
  const { data, isLoading, error } = useQuery({ queryKey: ["admin", "plans"], queryFn: admin.plans });
  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;

  return (
    <>
      <PageHeader title="Plans" description="Prices and limits for every plan. Limit changes apply to everyone on the plan straight away." />
      <Card>
        <Table head={["Plan", "Price", "Applications / month", "Resumes", "Subscribers", "Visibility", ""]}>
          {data.map((p) => (
            <tr key={p.code}>
              <Td><p className="font-medium text-slate-900">{p.name}</p><p className="text-xs text-slate-500">{p.code}</p></Td>
              <Td className="whitespace-nowrap">{p.price_cents === 0 ? "Free" : `${formatMoney(p.price_cents, p.currency)} / ${p.interval}`}</Td>
              <Td>{p.limits.applications_per_month.toLocaleString()}</Td>
              <Td>{p.limits.resumes}</Td>
              <Td>{p.subscribers}</Td>
              <Td>{p.is_active ? <Badge tone="green">On sale</Badge> : <Badge>Hidden</Badge>}</Td>
              <Td><Button size="sm" variant="secondary" onClick={() => setEditing(p)}>Edit</Button></Td>
            </tr>
          ))}
        </Table>
      </Card>
      {editing && <PlanDialog plan={editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function PlanDialog({ plan, onClose }: { plan: AdminPlan; onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const free = plan.price_cents === 0 && plan.code === "free";
  const [form, setForm] = useState({
    name: plan.name, price: String(plan.price_cents / 100), applications: String(plan.limits.applications_per_month),
    resumes: String(plan.limits.resumes), is_active: plan.is_active, sort_order: plan.sort_order,
  });
  const set = (key: keyof typeof form) => (value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));
  const body: PlanUpdate = {
    name: form.name.trim(), price_cents: Math.round(Number(form.price) * 100),
    applications_per_month: Number(form.applications), resumes: Number(form.resumes),
    is_active: form.is_active, sort_order: form.sort_order,
  };
  const save = useMutation({
    mutationFn: () => admin.updatePlan(plan.code, body),
    onSuccess: () => {
      toast.success(`${body.name} saved.`);
      void client.invalidateQueries({ queryKey: ["admin", "plans"] });
      void client.invalidateQueries({ queryKey: ["plans"] });
      onClose();
    },
  });
  const errors = fieldErrors(save.error);
  const priceChanged = body.price_cents !== plan.price_cents;
  const invalid = !body.name || [body.price_cents, body.applications_per_month, body.resumes].some((n) => !Number.isInteger(n) || n < 0);

  return (
    <Modal open onClose={onClose} title={`Edit ${plan.name}`} footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={invalid} loading={save.isPending} onClick={() => save.mutate()}>Save</Button>
      </>
    }>
      <div className="space-y-4">
        {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}
        <TextInput label="Name" value={form.name} onChange={set("name")} maxLength={100} error={errors.name} />
        <TextInput label={`Price per ${plan.interval} (${plan.currency})`} type="number" min={0} step="0.01" value={form.price}
                   onChange={set("price")} disabled={free} error={errors.price_cents}
                   hint={free ? "The Free plan stays free." : priceChanged && plan.subscribers > 0
                     ? `New subscribers pay the new price. The ${plan.subscribers} current subscriber${plan.subscribers === 1 ? "" : "s"} keep their price until they change plans.`
                     : undefined} />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput label="Applications per month" type="number" min={0} value={form.applications} onChange={set("applications")}
                     error={errors.applications_per_month} />
          <TextInput label="Resumes" type="number" min={0} max={100} value={form.resumes} onChange={set("resumes")} error={errors.resumes} />
        </div>
        <Toggle label="On sale" checked={form.is_active} onChange={set("is_active")}
                hint={free ? "Everyone falls back to the Free plan, so it can't be hidden."
                  : "Hidden plans can't be bought. People already on it keep it."} />
      </div>
    </Modal>
  );
}
