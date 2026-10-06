import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CreditCard } from "lucide-react";
import { useEffect, useState } from "react";
import { ConfirmDialog } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, Card, cx, EmptyState, PageHeader, ProgressBar, Spinner } from "../../components/ui";
import { formatDate, formatMoney } from "../../lib/format";
import { CheckoutError, openRazorpayCheckout } from "../../lib/razorpay";
import { errorMessage } from "../../services/api";
import { billing, plans as plansApi } from "../../services/endpoints";
import type { BillingOverview, PaymentRecord, Plan, Subscription } from "../../types";

const BILLING_KEY = ["billing"];
const CONFIRM_POLL_MS = 3000;
const CONFIRM_WAIT_MS = 2 * 60 * 1000;

type Outcome = { plan: Plan; status: string };

function checkoutError(e: unknown): string {
  return e instanceof CheckoutError ? e.message : errorMessage(e);
}

export function BillingPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [awaiting, setAwaiting] = useState(false);
  const [switchTo, setSwitchTo] = useState<Plan | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const overview = useQuery({
    queryKey: BILLING_KEY, queryFn: billing.overview, refetchInterval: awaiting ? CONFIRM_POLL_MS : false,
  });
  const plans = useQuery({ queryKey: ["plans"], queryFn: plansApi.list, staleTime: 10 * 60 * 1000 });

  const refresh = () => {
    for (const key of [BILLING_KEY, ["usage"], ["dashboard"], ["notifications"], ["automation"], ["plans"]]) {
      void qc.invalidateQueries({ queryKey: key });
    }
  };

  useEffect(() => {
    if (!awaiting) return;
    if (overview.data && !overview.data.pending) {
      setAwaiting(false);
      refresh();
      return;
    }
    const timer = window.setTimeout(() => setAwaiting(false), CONFIRM_WAIT_MS);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [awaiting, overview.data]);

  const buy = useMutation({
    mutationFn: async (plan: Plan): Promise<Outcome> => {
      const started = await billing.checkout(plan.code);
      if (!started.checkout) return { plan, status: started.subscription.status };
      const paid = await openRazorpayCheckout(started.checkout);
      if (!paid) return { plan, status: "dismissed" };
      const confirmed = await billing.confirm({
        payment_id: paid.razorpay_payment_id, subscription_id: paid.razorpay_subscription_id,
        signature: paid.razorpay_signature,
      });
      return { plan, status: confirmed.subscription.status };
    },
    onSuccess: ({ plan, status }) => {
      setSwitchTo(null);
      refresh();
      if (status === "active" || status === "trialing") toast.success(`You're on the ${plan.name} plan now.`);
      else if (status !== "dismissed") setAwaiting(true);
    },
    onError: (e) => {
      setSwitchTo(null);
      refresh();
      toast.error(checkoutError(e));
    },
  });

  const cancel = useMutation({
    mutationFn: billing.cancel,
    onSuccess: () => {
      setConfirmCancel(false);
      refresh();
      toast.success("Your plan is cancelled. It stays active until the end of the period you've paid for.");
    },
    onError: (e) => { setConfirmCancel(false); toast.error(errorMessage(e)); },
  });

  if (overview.isLoading || plans.isLoading) return <Spinner />;
  if (!overview.data || !plans.data) return <Alert kind="error">{errorMessage(overview.error ?? plans.error)}</Alert>;
  const data = overview.data;
  const sub = data.subscription;
  const freePlan = plans.data.find((p) => p.price_cents === 0);

  return (
    <>
      <PageHeader title="Billing" description="Your plan, this month's usage, and your payments." />
      <div className="space-y-4">
        {data.provider === "null" && (
          <Alert kind="info">
            Test mode: online payments are switched off on this server, so choosing a plan activates it straight away
            without charging anything.
          </Alert>
        )}
        {awaiting && <Alert kind="info">Payment received. Confirming it with Razorpay{"\u2026"} This usually takes a few seconds.</Alert>}
        {!awaiting && data.pending && !sub && (
          <Alert kind="info">
            Your {data.pending.plan.name} checkout isn't finished. If you've paid, the plan switches on as soon as
            Razorpay confirms the payment.
          </Alert>
        )}
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        <CurrentPlan data={data} onCancel={() => setConfirmCancel(true)} />
        <div className="lg:col-span-2">
          <div className="grid gap-4 sm:grid-cols-2">
            {plans.data.map((p) => (
              <PlanCard key={p.code} plan={p} sub={sub} busy={buy.isPending} loading={buy.isPending && buy.variables?.code === p.code}
                        onChoose={() => (sub ? setSwitchTo(p) : buy.mutate(p))} />
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Paid plans renew every month until you cancel. Cancelling keeps your plan until the end of the period
            you've paid for. Payments are handled by Razorpay; ApplyXAI never sees your card or UPI details.
          </p>
        </div>
      </div>

      <PaymentHistory payments={data.payments} />

      <ConfirmDialog
        open={switchTo !== null} onClose={() => setSwitchTo(null)} title={`Switch to ${switchTo?.name ?? ""}?`}
        confirmLabel={switchTo && sub ? `Pay ${formatMoney(switchTo.price_cents, switchTo.currency)}` : "Continue"}
        loading={buy.isPending} onConfirm={() => switchTo && buy.mutate(switchTo)}
        message={switchTo && sub ? (
          <>
            Your {sub.plan.name} plan ends as soon as the payment for {switchTo.name} goes through, and unused days
            aren't refunded. You'll pay {formatMoney(switchTo.price_cents, switchTo.currency)} now, then every month
            until you cancel.
          </>
        ) : ""}
      />
      <ConfirmDialog
        open={confirmCancel} onClose={() => setConfirmCancel(false)} title="Cancel your plan?" danger
        confirmLabel="Cancel plan" loading={cancel.isPending} onConfirm={() => cancel.mutate()}
        message={sub ? (
          <>
            You keep {sub.plan.name} until {formatDate(sub.current_period_end)} and won't be charged again. After that
            you're on the Free plan
            {freePlan ? ` (${freePlan.limits.applications_per_month.toLocaleString()} applications a month)` : ""}.
          </>
        ) : ""}
      />
    </>
  );
}

/** Plans an admin gave away carry this provider; there's nothing to pay or cancel. */
const COMPLIMENTARY = "admin";

function CurrentPlan({ data, onCancel }: { data: BillingOverview; onCancel: () => void }) {
  const { usage: u, subscription: sub } = data;
  return (
    <Card title="Current plan">
      <div className="flex items-center justify-between gap-2">
        <p className="text-2xl font-semibold">{u.plan_name}</p>
        {!sub ? <Badge>Free</Badge>
          : sub.provider === COMPLIMENTARY ? <Badge tone="brand">Complimentary</Badge>
          : sub.cancel_at_period_end ? <Badge tone="amber">Cancelled</Badge> : <Badge tone="green">Active</Badge>}
      </div>
      <p className="mt-1 text-sm text-slate-600">{planLine(sub)}</p>
      <div className="mt-4 space-y-4">
        <ProgressBar label="Applications this month" value={u.applications.used} max={u.applications.limit} />
        <ProgressBar label="Resumes" value={u.resumes.used} max={u.resumes.limit} />
      </div>
      <p className="mt-4 text-xs text-slate-500">Usage resets on {formatDate(u.resets_at)}.</p>
      {sub && !sub.cancel_at_period_end && (
        <Button className="mt-4 w-full" variant="secondary" onClick={onCancel}>Cancel plan</Button>
      )}
    </Card>
  );
}

function planLine(sub: Subscription | null): string {
  if (!sub) return "Free, with no card needed. Upgrade any time.";
  const end = formatDate(sub.current_period_end);
  if (sub.provider === COMPLIMENTARY) return `Given to you by ApplyXAI until ${end}. No payment is needed.`;
  if (sub.cancel_at_period_end) return `Active until ${end}. You won't be charged again.`;
  return `Renews on ${end} for ${formatMoney(sub.plan.price_cents, sub.plan.currency)}.`;
}

function PlanCard({ plan: p, sub, busy, loading, onChoose }: {
  plan: Plan; sub: Subscription | null; busy: boolean; loading: boolean; onChoose: () => void;
}) {
  const current = (sub ? sub.plan.code : "free") === p.code;
  return (
    <div className={cx("rounded-xl bg-white p-5 ring-1", current ? "ring-2 ring-brand-600" : "ring-slate-200")}>
      <div className="flex items-center justify-between">
        <p className="font-semibold">{p.name}</p>
        {current && <Badge tone="brand">Current</Badge>}
      </div>
      <p className="mt-2 text-xl font-semibold">
        {p.price_cents === 0 ? "Free" : formatMoney(p.price_cents, p.currency)}
        {p.price_cents > 0 && <span className="text-sm font-normal text-slate-500"> / {p.interval}</span>}
      </p>
      <p className="mt-2 text-sm text-slate-600">
        {p.limits.applications_per_month.toLocaleString()} applications / month &middot; {p.limits.resumes} resume{p.limits.resumes === 1 ? "" : "s"}
      </p>
      {!current && p.price_cents > 0 && (
        <Button className="mt-4 w-full" variant={sub ? "secondary" : "primary"} loading={loading} disabled={busy} onClick={onChoose}>
          {sub ? `Switch to ${p.name}` : `Upgrade to ${p.name}`}
        </Button>
      )}
      {!current && p.price_cents === 0 && sub && (
        <p className="mt-4 text-xs text-slate-500">
          {sub.cancel_at_period_end ? "You move to Free when your plan ends." : "Cancel your plan to move to Free."}
        </p>
      )}
    </div>
  );
}

const PAYMENT_STATUS: Record<string, { label: string; tone: "green" | "red" | "amber" | "slate" }> = {
  captured: { label: "Paid", tone: "green" },
  authorized: { label: "Processing", tone: "amber" },
  created: { label: "Processing", tone: "amber" },
  failed: { label: "Failed", tone: "red" },
  refunded: { label: "Refunded", tone: "slate" },
};

function PaymentHistory({ payments }: { payments: PaymentRecord[] }) {
  return (
    <Card title="Payments" className="mt-6">
      {payments.length === 0 ? (
        <EmptyState icon={<CreditCard className="h-6 w-6" />} title="No payments yet">
          Payments for paid plans appear here.
        </EmptyState>
      ) : (
        <div className="-mx-2 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-2 py-2 font-medium">Date</th>
                <th className="px-2 py-2 font-medium">Description</th>
                <th className="px-2 py-2 font-medium">Amount</th>
                <th className="px-2 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {payments.map((p) => {
                const status = PAYMENT_STATUS[p.status] ?? { label: p.status || "Unknown", tone: "slate" as const };
                return (
                  <tr key={p.id}>
                    <td className="whitespace-nowrap px-2 py-2">{formatDate(p.paid_at)}</td>
                    <td className="px-2 py-2">{p.description || "Subscription"}{p.method ? ` (${p.method.toUpperCase()})` : ""}</td>
                    <td className="whitespace-nowrap px-2 py-2">{formatMoney(p.amount_cents, p.currency)}</td>
                    <td className="px-2 py-2"><Badge tone={status.tone}>{status.label}</Badge></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
