# Billing — production scope

## Production (v1): Razorpay only

ApplyXAI production on EC2 is intended to bill through **Razorpay**:

- Set `PAYMENT_PROVIDER=razorpay` with live `PAYMENT_KEY_ID`, `PAYMENT_SECRET`, and `PAYMENT_WEBHOOK_SECRET`.
- Webhook URL: `https://applyxai.com/api/billing/webhook/razorpay` (subscription events enabled).
- After plan changes: `python -m backend.app.cli sync-plans` on the server.
- Checkout and subscription lifecycle: [DEVELOPMENT.md](./DEVELOPMENT.md#payments-razorpay).

The API **refuses to start** in `APP_ENV=production` without Razorpay configured (`backend/app/core/config.py`).

## Stripe (#31) — not production-ready

Admin may select **Stripe** in settings for future use. The [Stripe provider](../backend/app/services/payments/stripe_provider.py) returns **`STRIPE_NOT_READY` (501)** for checkout and webhooks until Checkout sessions and webhook verification are implemented.

**Do not** rely on Stripe for production revenue until BACKLOG #31 is marked Done.

## Development

- `PAYMENT_PROVIDER=null` with optional `PAYMENT_DEV_INSTANT_CHECKOUT=true` grants plans without a gateway (local only).
