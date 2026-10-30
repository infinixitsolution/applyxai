import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ConfirmDialog } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, ButtonLink, Card, cx, PageHeader, ProgressBar, Spinner, surfaceCardClass } from "../../components/ui";
import { PaymentHistoryTable } from "../../features/billing/PaymentHistoryTable";
import { formatDate, formatMoney } from "../../lib/format";
import { formatResumeLimit } from "../../lib/planLimits";
import { CheckoutError, openRazorpayCheckout } from "../../lib/razorpay";
import { errorMessage } from "../../services/api";
import { billing, plans as plansApi } from "../../services/endpoints";
import type { BillingOverview, Plan, Subscription, TaxInvoiceRecord } from "../../types";

const BILLING_KEY = ["billing"];
const CONFIRM_POLL_MS = 3000;
const CONFIRM_WAIT_MS = 2 * 60 * 1000;

type Outcome = { plan: Plan; status: string };

function checkoutError(e: unknown): string {
  return e instanceof CheckoutError ? e.message : errorMessage(e);
}

function TaxInvoicesCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["billing", "invoices"],
    queryFn: () => billing.invoices({ page: 1, page_size: 10 }),
  });
  const items = data?.items ?? [];
  return (
    <Card title="Tax invoices" className="mt-6">
      {isLoading ? (
        <Spinner />
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">GST invoices appear here after a captured payment when GST is enabled.</p>
      ) : (
        <ul className="divide-y divide-slate-100 text-sm">
          {items.map((inv: TaxInvoiceRecord) => (
            <li key={inv.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                <span className="font-mono">{inv.invoice_number}</span>
                <span className="ml-2 capitalize text-slate-500">{inv.status}</span>
              </span>
              <span className="flex items-center gap-3">
                <span>{formatMoney(inv.total_cents, inv.currency)}</span>
                <a
                  href={billing.invoicePdfUrl(inv.id)}
                  className="font-medium text-brand-600 hover:underline"
                  download
                >
                  PDF
                </a>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function BillingPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
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

  useEffect(() => {
    const sessionId = params.get("session_id");
    const checkoutState = params.get("checkout");
    if (!sessionId || checkoutState !== "success") return;
    void (async () => {
      try {
        await billing.confirm({ payment_id: sessionId, subscription_id: sessionId, signature: sessionId });
        toast.success("Stripe checkout completed.");
        refresh();
      } catch (e) {
        toast.error(errorMessage(e));
      } finally {
        params.delete("session_id");
        params.delete("checkout");
        setParams(params, { replace: true });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get("session_id")]);

  const buy = useMutation({
    mutationFn: async (plan: Plan): Promise<Outcome> => {
      const started = await billing.checkout(plan.code);
      if (started.checkout?.url) {
        window.location.assign(started.checkout.url);
        return { plan, status: "pending" };
      }
      if (!started.checkout?.key || !started.checkout?.subscription_id) {
        throw new CheckoutError(
          "Checkout did not start. Enable Razorpay or Stripe under Admin → Settings → Payments, sync plans, then try again.",
        );
      }
      const paid = await openRazorpayCheckout(started.checkout);
      if (!paid) return { plan, status: "dismissed" };
      const confirmed = await billing.confirm({
        payment_id: paid.razorpay_payment_id, subscription_id: paid.razorpay_subscription_id,
        signature: paid.razorpay_signature,
      });
      return { plan, status: confirmed.subscription.status };
    },
    onSuccess: ({ plan, status }) => {
      refresh();
      if (status === "active" || status === "trialing") toast.success(`You're on the ${plan.name} plan now.`);
      else if (status !== "dismissed") setAwaiting(true);
    },
    onError: (e) => {
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
  const managed = !!data.managed_by_institute;
  const campusName = data.institute_name || "your institute";

  if (managed) {
    return (
      <>
        <PageHeader
          title="Billing"
          description={`Your plan is provided by ${campusName}. Personal billing starts if they release you from campus.`}
        />
        <Alert kind="info">
          Billing and subscription for this account are managed by <strong>{campusName}</strong>.
          You keep campus plan limits while assigned. If they release you, that campus package is cancelled and you must buy a candidate plan to apply.
        </Alert>
        <div className="mt-4 max-w-md">
          <CurrentPlan data={data} onCancel={() => undefined} managed />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Billing" description="Your plan, this month's usage, and your payments." />
      <div className="space-y-4">
        {!data.checkout_available && (
          <Alert kind="error">
            Paid upgrades need Razorpay or Stripe. An admin must open <strong>Settings → Payments</strong>, pick a
            provider, save API keys, then <strong>Sync plans</strong>. Until then, Switch/Upgrade will not open checkout.
          </Alert>
        )}
        {data.provider === "razorpay" && data.razorpay_mode === "test" && (
          <Alert kind="info">
            Razorpay <strong>test</strong> checkout — same flow as production, but no real money.
            In Checkout use card <strong>4111 1111 1111 1111</strong> (any future expiry/CVV) or UPI <strong>success@razorpay</strong>.
          </Alert>
        )}
        {data.provider === "razorpay" && data.checkout_live && (
          <Alert kind="info">Payments are processed by Razorpay with live keys. You will be charged in INR.</Alert>
        )}
        {data.provider === "stripe" && data.checkout_available && (
          <Alert kind="info">Payments are processed by Stripe Checkout. You will be redirected to Stripe to pay.</Alert>
        )}
        {awaiting && <Alert kind="info">Payment received. Confirming it{"\u2026"} This usually takes a few seconds.</Alert>}
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
                        checkoutAvailable={!!data.checkout_available}
                        onChoose={() => (sub ? setSwitchTo(p) : buy.mutate(p))} />
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Paid plans renew every month until you cancel. Cancelling keeps your plan until the end of the period
            you've paid for. Payments are handled by Razorpay or Stripe; ApplyXAI never sees your card or UPI details.
          </p>
        </div>
      </div>

      <Card
        title="Recent payments"
        className="mt-6"
        actions={
          <ButtonLink to="/app/payment-history" variant="ghost" size="sm">
            View all
          </ButtonLink>
        }
      >
        <PaymentHistoryTable payments={data.payments} />
        {data.payments.length > 0 && (
          <p className="mt-3 text-xs text-slate-500">
            <Link to="/app/payment-history" className="font-medium text-brand-700 hover:underline">
              Open full payment history
            </Link>
          </p>
        )}
      </Card>

      <TaxInvoicesCard />

      <ConfirmDialog
        open={switchTo !== null} onClose={() => setSwitchTo(null)} title={`Switch to ${switchTo?.name ?? ""}?`}
        confirmLabel={switchTo && sub ? `Pay ${formatMoney(switchTo.price_cents, switchTo.currency)}` : "Continue"}
        loading={buy.isPending}
        onConfirm={() => {
          if (!switchTo) return;
          const plan = switchTo;
          setSwitchTo(null);
          buy.mutate(plan);
        }}
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

function CurrentPlan({ data, onCancel, managed }: { data: BillingOverview; onCancel: () => void; managed?: boolean }) {
  const { usage: u, subscription: sub } = data;
  return (
    <Card title="Current plan">
      <div className="flex items-center justify-between gap-2">
        <p className="text-2xl font-semibold">{u.plan_name}</p>
        {managed ? <Badge tone="brand">Campus</Badge>
          : !sub ? <Badge>Free</Badge>
          : sub.provider === COMPLIMENTARY ? <Badge tone="brand">Complimentary</Badge>
          : sub.cancel_at_period_end ? <Badge tone="amber">Cancelled</Badge> : <Badge tone="green">Active</Badge>}
      </div>
      <p className="mt-1 text-sm text-slate-600">
        {managed
          ? `Provided by ${data.institute_name || "your institute"}. Personal billing is locked while this seat is active.`
          : planLine(sub)}
      </p>
      <div className="mt-4 space-y-4">
        <ProgressBar label="Applications this month" usageKind="applications" value={u.applications.used} max={u.applications.limit} />
        {u.mock_interviews && (
          <ProgressBar
            label="Mock interviews this month"
            usageKind="mock_interviews"
            value={u.mock_interviews.used}
            max={u.mock_interviews.limit}
          />
        )}
        <ProgressBar label="Resumes" usageKind="resumes" value={u.resumes.used} max={u.resumes.limit} />
      </div>
      <p className="mt-4 text-xs text-slate-500">Usage resets on {formatDate(u.resets_at)}.</p>
      {!managed && sub && !sub.cancel_at_period_end && (
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

function PlanCard({ plan: p, sub, busy, loading, checkoutAvailable, onChoose }: {
  plan: Plan; sub: Subscription | null; busy: boolean; loading: boolean; checkoutAvailable: boolean; onChoose: () => void;
}) {
  const current = (sub ? sub.plan.code : "free") === p.code;
  return (
    <div className={cx(surfaceCardClass, "p-5", current ? "ring-2 ring-brand-600" : "")}>
      <div className="flex items-center justify-between">
        <p className="font-semibold">{p.name}</p>
        {current && <Badge tone="brand">Current</Badge>}
      </div>
      <p className="mt-2 text-xl font-semibold">
        {p.price_cents === 0 ? "Free" : formatMoney(p.price_cents, p.currency)}
        {p.price_cents > 0 && <span className="text-sm font-normal text-slate-500"> / {p.interval}</span>}
      </p>
      <p className="mt-2 text-sm text-slate-600">
        {p.limits.applications_per_month.toLocaleString()} applications / month &middot;{" "}
        {(p.limits.mock_interviews_per_month ?? 0).toLocaleString()} mock interviews / month &middot;{" "}
        {formatResumeLimit(p.limits.resumes)} resumes / month
      </p>
      {!current && p.price_cents > 0 && (
        <Button
          className="mt-4 w-full"
          variant={sub ? "secondary" : "primary"}
          loading={loading}
          disabled={busy || !checkoutAvailable}
          onClick={onChoose}
          title={checkoutAvailable ? undefined : "Configure Razorpay in Admin → Settings → Payments first"}
        >
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

