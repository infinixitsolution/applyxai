"""Default platform settings (CMS, notifications). Used by migrations and empty DB rows."""

PLATFORM_SETTINGS_KEY = "default"

DEFAULT_CMS: dict = {
    "branding": {
        "app_name": "ApplyXAI",
        "contact_email": "support@applyxai.example",
        "footer_line": "",
        "social_links": {"twitter": "", "linkedin": "", "github": ""},
    },
    "banner": {"enabled": False, "message": "", "tone": "info"},
    "landing": {
        "hero_badge": "LinkedIn Easy Apply automation",
        "hero_title": "Apply on LinkedIn with AI — safely, from your browser.",
        "hero_subtitle": "Set preferences once. Tailor when you want. Track every application.",
        "hero_cta_primary": "Start applying free",
        "hero_cta_secondary": "See how it works",
        "hero_footnote": "LinkedIn only today. You sign in locally — we never see your password.",
        "features_heading": "Everything for a focused LinkedIn search",
        "features": [
            {"icon": "sliders", "title": "Precise job preferences", "text": "Pick titles, locations, experience levels, job types, and work settings with the same filters LinkedIn uses."},
            {"icon": "bot", "title": "Automated Easy Apply", "text": "The automation fills in application forms with your saved answers and your chosen resume, and records every outcome."},
            {"icon": "filter", "title": "Smart skipping", "text": "Skip roles with words you don't want, companies you'd rather avoid, or jobs that won't sponsor a visa."},
            {"icon": "file-text", "title": "Resume management", "text": "Keep several resumes for different roles and choose a default for each run."},
            {"icon": "bar-chart", "title": "Application tracking", "text": "See every application, its status, and why anything failed. Export the full history to CSV whenever you like."},
            {"icon": "shield", "title": "Your data, protected", "text": "Encrypted sessions, strict per-account data isolation, and your job-site password never leaves your computer."},
        ],
        "steps_heading": "How it works",
        "steps": [
            {"title": "Create your profile", "text": "Add your details, upload a resume, and answer the common screening questions once."},
            {"title": "Set your preferences", "text": "Choose the roles, locations, and filters that fit what you're looking for."},
            {"title": "Run the automation", "text": "It searches and applies in your browser while you watch, and you can pause or stop it at any time."},
            {"title": "Track the results", "text": "Review applications, failures, and monthly usage on your dashboard."},
        ],
        "pricing_heading": "Simple, transparent pricing",
        "pricing_subtitle": "All plans include LinkedIn Easy Apply automation and application history.",
        "faq_heading": "Frequently asked questions",
        "faq": [
            {"question": "Does ApplyXAI guarantee interviews or a job?", "answer": "No. ApplyXAI saves you time on repetitive applications. Whether you hear back depends on employers, your profile, and the roles you choose."},
            {"question": "Which job sites are supported?", "answer": "LinkedIn Easy Apply only. Jobs that redirect to an external site are saved in your history so you can finish them manually."},
            {"question": "Do you store my LinkedIn password?", "answer": "No. Automation runs in Chrome on your computer. You sign in to LinkedIn there; ApplyXAI never receives your password or OTP codes."},
            {"question": "Is automated applying allowed on LinkedIn?", "answer": "LinkedIn's terms restrict some automated activity. You are responsible for compliant use — review submissions and keep volume reasonable."},
            {"question": "Can I cancel at any time?", "answer": "Yes. Paid plans can be cancelled at any time and stay active until the end of the billing period. See our refund policy for details."},
        ],
        "faq_contact_line": "Still have questions? Email us at {contact_email}.",
    },
    "seo": {
        "site_url": "https://applyxai.com",
        "default_title": "ApplyXAI — LinkedIn Easy Apply automation",
        "title_suffix": "",
        "default_description": (
            "ApplyXAI automates LinkedIn Easy Apply — AI resume tailoring, screening answers, "
            "and application tracking from your own browser."
        ),
        "default_keywords": "LinkedIn Easy Apply, job search automation, AI resume, application tracking, ApplyXAI",
        "og_image_url": "https://applyxai.com/mascot.png",
        "twitter_card": "summary_large_image",
        "robots_index": True,
        "robots_disallow": ["/app/", "/admin/", "/onboarding"],
        "google_site_verification": "",
        "bing_site_verification": "",
        "pages": {
            "home": {
                "title": "",
                "description": "",
                "noindex": False,
            },
            "login": {
                "title": "Sign in",
                "description": "Sign in to your ApplyXAI account to manage LinkedIn Easy Apply automation.",
                "noindex": True,
            },
            "register": {
                "title": "Create account",
                "description": "Create a free ApplyXAI account and start automating LinkedIn Easy Apply.",
                "noindex": False,
            },
            "privacy": {
                "title": "Privacy Policy",
                "description": "How ApplyXAI collects, uses, and protects your data.",
                "noindex": False,
            },
            "terms": {
                "title": "Terms of Service",
                "description": "Terms for using the ApplyXAI job application automation platform.",
                "noindex": False,
            },
            "refund": {
                "title": "Refund Policy",
                "description": "ApplyXAI subscription refund policy.",
                "noindex": False,
            },
        },
    },
    "legal": {
        "privacy_md": """This policy explains what ApplyXAI collects, why, and the choices you have.

## What we collect

- Account details: name, email address, and a hashed password (we never store your password itself).
- Profile and preferences you enter, such as job titles, locations, and answers to screening questions.
- Resumes you upload.
- Application records created by the automation: job titles, companies, links, and outcomes.
- Billing records from our payment provider. We don't store card numbers.

## What we don't collect

We never receive your LinkedIn or other job-site passwords. The automation runs in a browser on your own computer, and you sign in there.

## How we use it

We use your data to provide the service, run your automation with your settings, show your history, process payments, and send account emails. We don't sell personal data.

## Retention and deletion

We keep your data while your account is active. You can export your applications at any time. To delete your account and data, contact us.

## Contact

Questions about privacy: contact us at the support email on our website.""",
        "terms_md": """By using ApplyXAI you agree to these terms.

## The service

ApplyXAI helps you manage and automate job applications. We don't guarantee interviews, offers, or any particular result.

## Your responsibilities

- Provide accurate information in your profile, answers, and resumes. Applications are sent in your name.
- Follow the terms of service of every job site you use with ApplyXAI. Some sites restrict automated activity, and you're responsible for how you use the automation.
- Keep your account secure and don't share it.

## Acceptable use

Don't use ApplyXAI to send spam or misleading applications, to get around security measures on other sites, or to break any law.

## Plans and limits

Each plan has monthly limits. Usage resets on the first day of each month (UTC).

## Liability

The service is provided "as is". To the extent permitted by law, we aren't liable for indirect losses or for actions taken by third-party sites.""",
        "refund_md": """You can cancel a paid plan at any time. It stays active until the end of the current billing period, and you won't be charged again.

## Changing plans

When you switch to a different paid plan, the new plan starts as soon as its payment goes through and your previous plan ends at the same moment. Unused days on the previous plan aren't refunded or carried over.

## Refunds

If you were charged by mistake, or the service didn't work for you because of a fault on our side, contact us within 7 days of the charge and we'll review a refund.

## How to ask

Email us with your account email and the payment date.""",
    },
}

DEFAULT_NOTIFICATIONS: dict = {
    "run_finished": {
        "email": False,
        "label": "Automation run finished",
        "description": "When a job search run completes (success, failure, or stop).",
    },
    "limit_reached": {
        "email": False,
        "label": "Monthly application limit",
        "description": "When a run stops because the plan's monthly application limit was reached.",
    },
    "plan_active": {
        "email": False,
        "label": "Plan activated",
        "description": "When a paid subscription becomes active.",
    },
    "payment_failed": {
        "email": False,
        "label": "Payment failed",
        "description": "When a subscription renewal payment fails.",
    },
    "plan_ended": {
        "email": False,
        "label": "Plan ended",
        "description": "When a subscription expires or is cancelled at period end.",
    },
    "plan_cancelled": {
        "email": False,
        "label": "Plan cancellation scheduled",
        "description": "When the user cancels renewal at period end.",
    },
    "plan_granted": {
        "email": False,
        "label": "Complimentary plan granted",
        "description": "When an admin grants a complimentary plan.",
    },
    "admin_broadcast": {
        "email": False,
        "label": "Admin announcement",
        "description": "One-off messages sent from the admin console.",
    },
    "institute_invite": {
        "email": False,
        "label": "Institute invitation",
        "description": "When a training institute invites you to join with a reserved seat.",
    },
    "institute_invite_accepted": {
        "email": False,
        "label": "Invite accepted",
        "description": "When a candidate accepts an institute invitation (institute admins).",
    },
    "partner_commission": {
        "email": False,
        "label": "Partner commission",
        "description": "When commission is accrued on your partner account.",
    },
    "job_applied": {
        "email": False,
        "label": "Job application submitted",
        "description": "When ApplyXAI successfully submits an Easy Apply application for you.",
    },
    "daily_report": {
        "email": False,
        "label": "Daily application summary",
        "description": "A once-per-day email with how many jobs you applied to and other outcomes.",
    },
}

# Editable copy for auth emails and notification events (merged with DB overrides).
DEFAULT_EMAIL_TEMPLATES: dict = {
    "auth": {
        "verify_email": {
            "subject": "Verify your {app_name} email",
            "body": (
                "Welcome to {app_name}!\n\nConfirm your email address:\n{link}\n\n"
                "This link expires in {verification_hours} hours. "
                "If you didn't create an account, ignore this email."
            ),
            "html": "",
        },
        "password_reset": {
            "subject": "Reset your {app_name} password",
            "body": (
                "Someone asked to reset the password for this {app_name} account.\n\n"
                "Choose a new password:\n{link}\n\n"
                "This link expires in {password_reset_minutes} minutes. "
                "If it wasn't you, ignore this email; your password is unchanged."
            ),
            "html": "",
        },
        "account_exists": {
            "subject": "Your {app_name} account",
            "body": (
                "Someone tried to register a new {app_name} account with this email, "
                "but you already have one.\n\nForgot your password? Reset it here:\n{link}\n\n"
                "If this wasn't you, you can ignore this email."
            ),
            "html": "",
        },
        "institute_invite": {
            "subject": "{institute_name} invited you to {app_name}",
            "body": (
                "{institute_name} reserved a seat for you on {app_name}.\n\n"
                "Accept the invitation:\n{link}\n\n"
                "Create an account with this email if you don't have one yet, then open the link."
            ),
            "html": "",
        },
    },
    "events": {
        "run_finished": {
            "in_app_title": "{title}",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: {title}",
            "email_body": "{title}\n\n{message}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "limit_reached": {
            "in_app_title": "Monthly application limit reached",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: Monthly application limit reached",
            "email_body": "Monthly application limit reached\n\n{message}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "plan_active": {
            "in_app_title": "Your {plan_name} plan is active",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: Your {plan_name} plan is active",
            "email_body": "Your {plan_name} plan is active\n\n{message}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "payment_failed": {
            "in_app_title": "Your payment didn't go through",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: Payment failed",
            "email_body": "Your payment didn't go through\n\n{message}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "plan_ended": {
            "in_app_title": "Your {plan_name} plan has ended",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: Your {plan_name} plan has ended",
            "email_body": "Your {plan_name} plan has ended\n\n{message}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "plan_cancelled": {
            "in_app_title": "Your {plan_name} plan is cancelled",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: Plan cancellation scheduled",
            "email_body": "Your {plan_name} plan is cancelled\n\n{message}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "plan_granted": {
            "in_app_title": "You've been given the {plan_name} plan",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: Complimentary {plan_name} plan",
            "email_body": "You've been given the {plan_name} plan\n\n{message}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "admin_broadcast": {
            "in_app_title": "{title}",
            "in_app_body": "{body}",
            "email_subject": "{app_name}: {title}",
            "email_body": "{title}\n\n{body}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "institute_invite": {
            "in_app_title": "{institute_name} invited you",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: {institute_name} invitation",
            "email_body": "{institute_name} invited you\n\n{message}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "institute_invite_accepted": {
            "in_app_title": "{candidate_email} accepted your invitation",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: Invitation accepted",
            "email_body": "{candidate_email} accepted your invitation\n\n{message}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "partner_commission": {
            "in_app_title": "Commission earned",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: Commission earned",
            "email_body": "Commission earned\n\n{message}\n\nOpen in {app_name}:\n{link_url}",
            "email_html": "",
        },
        "job_applied": {
            "in_app_title": "Applied to {job_title}",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: Applied to {job_title} at {company}",
            "email_body": (
                "Application submitted\n\n"
                "{message}\n\n"
                "Role: {job_title}\n"
                "Company: {company}\n"
                "Location: {location}\n\n"
                "View your applications:\n{link_url}"
            ),
            "email_html": "",
        },
        "daily_report": {
            "in_app_title": "Daily summary for {report_date}",
            "in_app_body": "{message}",
            "email_subject": "{app_name}: Daily summary for {report_date}",
            "email_body": (
                "Your application activity for {report_date}\n\n"
                "{message}\n\n"
                "{summary}\n\n"
                "Open your dashboard:\n{link_url}"
            ),
            "email_html": "",
        },
    },
}

DEFAULT_PAYMENTS: dict = {
    "provider": "null",
    "key_id": "",
}

DEFAULT_AI: dict = {
    "enabled": False,
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "models": {
        "fast": "gpt-4o-mini",
        "strong": "gpt-4o",
        "embedding": "text-embedding-3-small",
    },
    "features": {"applications": True, "resume": True},
}
