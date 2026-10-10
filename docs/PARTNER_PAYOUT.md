# Partner payout workflow (admin)

ApplyXAI accrues partner commissions when eligible institutes pay through Razorpay. Payouts are **requested by the partner** and **approved by an admin**; bank transfer is executed outside the app (manual or Razorpay X / bank file).

## Prerequisites

1. Partner **KYC verified** (or marked not required) and status **approved** or **active**.
2. Partner has saved **payout account** and **IFSC** on their tax profile.
3. Razorpay (or your finance process) configured for outbound transfers.

## Admin steps

1. Open **Admin → Partners → [partner] → Payouts**.
2. Review open payout requests; confirm accrued commission balance.
3. Set status to **Approved** only when KYC is complete (API enforces `KYC_REQUIRED` otherwise).
4. Execute the bank transfer via your finance tool; record reference in the payout **note**.
5. Mark **Paid** when the transfer settles.

## Automation (#33) — v1 scope

**In scope (shipped):** KYC gates on partner status, payout request/approve/paid workflow in admin API and UI, commission accrual on qualifying payments.

**Out of scope for v1 (by design):** Fully automated Razorpay X / bank API payout execution. Finance runs transfers manually (or via Razorpay dashboard) and marks payouts **Paid** in admin.

**Future (#33):** Integrate Razorpay X or payout APIs; webhook or poll for settlement; idempotent payout references. Track in [BACKLOG.md](./BACKLOG.md) until prioritized.
