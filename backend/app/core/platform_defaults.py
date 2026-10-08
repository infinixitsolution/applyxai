"""Default platform settings (CMS, notifications). Used by migrations and empty DB rows."""

PLATFORM_SETTINGS_KEY = "default"

DEFAULT_CMS: dict = {
    "branding": {
        "app_name": "ApplyXAI",
        "contact_email": "support@applyxai.example",
        "footer_line": "Built on the open-source Auto Job Applier (MIT).",
        "social_links": {"twitter": "", "linkedin": "", "github": ""},
    },
    "banner": {"enabled": False, "message": "", "tone": "info"},
    "landing": {
        "hero_badge": "Job search automation, under your control",
        "hero_title": "AI-Powered Job Search & Application Management",
        "hero_subtitle": (
            "Set your preferences once. ApplyXAI finds matching roles, fills in Easy Apply forms with your answers, "
            "and keeps a clear record of every application."
        ),
        "hero_cta_primary": "Get started free",
        "hero_cta_secondary": "See how it works",
        "hero_footnote": "No credit card needed for the free plan.",
        "features_heading": "Everything you need for a focused search",
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
        "pricing_subtitle": "Start free. Upgrade when you need more applications.",
        "faq_heading": "Frequently asked questions",
        "faq": [
            {"question": "Does ApplyXAI guarantee interviews or a job?", "answer": "No. ApplyXAI saves you time on repetitive applications. Whether you hear back depends on employers, your profile, and the roles you choose."},
            {"question": "Which job sites are supported?", "answer": "LinkedIn Easy Apply today. Jobs that use an external application site are recorded so you can finish them yourself."},
            {"question": "Do you store my LinkedIn password?", "answer": "No. The automation runs in a browser on your own computer, and you sign in there. ApplyXAI never receives your job-site password."},
            {"question": "Is automated applying allowed?", "answer": "Job sites set their own rules, and some limit automation. You're responsible for using ApplyXAI in line with the terms of the sites you use. Review applications and keep the volume reasonable."},
            {"question": "Can I cancel at any time?", "answer": "Yes. Paid plans can be cancelled at any time and stay active until the end of the billing period. See our refund policy for details."},
        ],
        "faq_contact_line": "Still have questions? Email us at {contact_email}.",
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
}
