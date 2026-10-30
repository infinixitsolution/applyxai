import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CreditCard } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Pagination } from "../../components/Pagination";
import { Alert, ButtonLink, Card, PageHeader, Spinner, cx } from "../../components/ui";
import { PAYMENT_STATUS, PaymentHistoryTable } from "../../features/billing/PaymentHistoryTable";
import { errorMessage } from "../../services/api";
import { billing } from "../../services/endpoints";
import { FilterChip, FilterChipBrand } from "../admin/shared";

const PAGE_SIZE = 25;
const PAYMENT_FILTERS = ["", "captured", "failed", "refunded"] as const;

export function PaymentHistoryPage() {
  const [status, setStatus] = useState<(typeof PAYMENT_FILTERS)[number]>("");
  const [page, setPage] = useState(1);
  const query = { status: status || undefined, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["billing", "payments", query],
    queryFn: () => billing.payments(query),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader
        title="Payment history"
        description="Charges for your subscriptions and upgrades, as reported by the payment provider."
        actions={
          <ButtonLink to="/app/billing" variant="secondary" size="sm">
            <CreditCard className="h-4 w-4" aria-hidden /> Billing
          </ButtonLink>
        }
      />
      <Card>
        <span className="mb-2 block text-sm font-medium text-slate-700">Status</span>
        <div className="flex flex-wrap gap-2">
          <FilterChip active={status === ""} onClick={() => { setStatus(""); setPage(1); }}>All</FilterChip>
          {PAYMENT_FILTERS.filter(Boolean).map((s) => {
            const label = PAYMENT_STATUS[s]?.label ?? s;
            return (
              <FilterChipBrand key={s} active={status === s} onClick={() => { setStatus(status === s ? "" : s); setPage(1); }}>
                {label}
              </FilterChipBrand>
            );
          })}
        </div>
      </Card>

      <div className="mt-6">
        {isLoading ? <Spinner /> : error || !data ? (
          <Alert kind="error">{errorMessage(error)}</Alert>
        ) : (
          <Card className={cx(isFetching && "opacity-70 transition-opacity")}>
            <p className="mb-4 text-sm text-slate-600">
              Showing <span className="font-medium text-slate-900">{data.items.length}</span> of{" "}
              <span className="font-medium text-slate-900">{data.total.toLocaleString()}</span> payments
            </p>
            <PaymentHistoryTable payments={data.items} />
            {data.total > 0 && (
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            )}
          </Card>
        )}
      </div>
      <p className="mt-4 text-xs text-slate-500">
        Need to change your plan? Go to <Link to="/app/billing" className="font-medium text-brand-700 hover:underline">Billing</Link>.
      </p>
    </>
  );
}
