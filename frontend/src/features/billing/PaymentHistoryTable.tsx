import { CreditCard } from "lucide-react";
import { Badge, EmptyState } from "../../components/ui";
import { formatDate, formatMoney } from "../../lib/format";
import type { PaymentRecord } from "../../types";

export const PAYMENT_STATUS: Record<string, { label: string; tone: "green" | "red" | "amber" | "slate" }> = {
  captured: { label: "Paid", tone: "green" },
  authorized: { label: "Processing", tone: "amber" },
  created: { label: "Processing", tone: "amber" },
  failed: { label: "Failed", tone: "red" },
  refunded: { label: "Refunded", tone: "slate" },
};

export function PaymentHistoryTable({ payments, emptyTitle = "No payments yet" }: {
  payments: PaymentRecord[];
  emptyTitle?: string;
}) {
  if (payments.length === 0) {
    return (
      <EmptyState icon={<CreditCard className="h-6 w-6" />} title={emptyTitle}>
        Payments for paid plans appear here.
      </EmptyState>
    );
  }
  return (
    <div className="table-scroll -mx-2 sm:-mx-2">
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
                <td className="px-2 py-2">
                  {p.description || "Subscription"}
                  {p.method ? ` (${p.method.toUpperCase()})` : ""}
                </td>
                <td className="whitespace-nowrap px-2 py-2">{formatMoney(p.amount_cents, p.currency)}</td>
                <td className="px-2 py-2"><Badge tone={status.tone}>{status.label}</Badge></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
