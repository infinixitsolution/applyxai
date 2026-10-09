# Email setup (Amazon SES) — simple version

ApplyXAI sends mail as **`no-reply@applyxai.com`**. That needs **Amazon SES** in the same region as your server: **ap-southeast-2 (Sydney)**.

## Do this once (about 15 minutes)

### 1. Run the setup script on your PC

Open **PowerShell** (Start menu → PowerShell), then:

```powershell
cd c:\xampp\htdocs\applyxainew
.\scripts\complete_ses.ps1
```

- If asked, **sign in to AWS** in the browser (use the account where your EC2 server lives).
- The script creates SES for **applyxai.com**, prints **DNS records**, saves **`ses-smtp.env`**, and can copy SMTP settings to EC2.

### 2. Add DNS records at your domain registrar

Where you manage **applyxai.com** (GoDaddy, Namecheap, Cloudflare, Route 53, etc.):

1. AWS Console → **Amazon SES** → **Verified identities** → **applyxai.com**
2. Copy every **DKIM** CNAME record SES shows → paste into DNS
3. Add **SPF** (TXT on `@` or root):  
   `v=spf1 include:amazonses.com ~all`  
   (If you already have SPF, add `include:amazonses.com` inside the existing record.)

Wait until SES status is **Verified** (not Pending).

### 3. Leave sandbox (required for real users)

SES → **Account dashboard** → if it says **Sandbox**, click **Request production access** and submit the form (transactional mail for your app is a normal use case).

### 4. Test

1. Restart is done if you applied settings via the script; otherwise on the server:  
   `sudo systemctl restart applyxai-backend`
2. Log in as admin → **Settings → Email & SMTP** → send a test email to yourself.

---

## If the script fails

**“Unable to locate credentials”** — run `.\scripts\complete_ses.ps1` again and complete browser login, or create an IAM user with SES + CloudFormation access and run:

```powershell
aws configure
# Access Key, Secret Key, region ap-southeast-2
.\scripts\complete_ses.ps1
```

**Emails still not arriving** — almost always **DNS not verified** or still in **Sandbox** (only verified recipient addresses work in sandbox).

---

## Files (for reference)

| File | Purpose |
|------|--------|
| `scripts/complete_ses.ps1` | Main entry — login + deploy + optional EC2 update |
| `scripts/setup_ses.ps1` | CloudFormation deploy |
| `infra/ses-applyxai.yaml` | AWS template |
| `ses-smtp.env` | Generated locally — **never commit** |

Manual stack deploy and SMTP password derivation are documented in the script comments.
