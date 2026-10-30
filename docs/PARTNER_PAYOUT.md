# Partner payout workflow (admin)

ApplyXAI accrues partner commissions when eligible institutes pay through Razorpay (or Stripe). Payouts are **requested by the partner** and **approved by an admin**.

## Prerequisites

1. Partner **KYC verified** (or marked not required) and status **approved** or **active**.
2. Partner has saved **payout account** and **IFSC** on their tax profile.
3. For **Pay now**: `RAZORPAYX_ACCOUNT_NUMBER` in `.env` (optional `RAZORPAYX_KEY_ID` / `RAZORPAYX_KEY_SECRET`; otherwise Razorpay payment keys are reused).

## Admin steps

1. Open **Admin → Partners → [partner] → Payouts**.
2. Review open payout requests; confirm accrued commission balance.
3. Set status to **Approved** only when KYC is complete (API enforces `KYC_REQUIRED` otherwise).
4. **Pay now** (RazorpayX) records `provider_transfer_id` and marks the payout **Paid**.
5. If RazorpayX is not configured, execute a bank transfer, put the transfer id in the payout **note**, then **Mark paid**. Auto-mark paid only happens after a confirmed transfer id from Pay now.

## Automation (#33)

**Shipped:** KYC gates, request/approve/paid workflow, RazorpayX **Pay now**, manual bank-transfer fallback.

Candidate-to-candidate referral codes (`C…` on `/r/{code}`) do **not** accrue partner commissions.
