# Email (Hostinger SMTP)

ApplyXAI sends all mail (verification, password reset, notifications, live-interview tokens) from the
**`noreply@applyxai.com`** mailbox on Hostinger.

## Settings

| Field | Value |
|---|---|
| Host | `smtp.hostinger.com` |
| Port | `465` (SSL) |
| Username | `noreply@applyxai.com` |
| Password | the mailbox password from Hostinger → Emails |
| From | `ApplyXAI <noreply@applyxai.com>` |

Enter these in **Admin → Settings → Email & SMTP** and turn SMTP on. They are stored in the database (the
password encrypted) and take priority over `.env`. The `SMTP_*` values in the server `.env` are only a fallback.

The From address must be the same mailbox as the username. Hostinger refuses any other sender with
`553 5.7.1 Sender address rejected: not owned by user`.

## Test

Admin → Settings → Email & SMTP → **Send test**. "Accepted by mail server" means Hostinger took the message.
If it never arrives, check spam and that `applyxai.com` has Hostinger's SPF and DKIM records in DNS.

## Changing the password

Change it in Hostinger → Emails, then enter the new one in Admin → Settings → Email & SMTP and save.
Update `SMTP_PASSWORD` in `/home/ubuntu/applyxai/.env` too if you rely on the fallback.
