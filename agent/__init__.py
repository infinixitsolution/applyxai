"""
ApplyXAI desktop agent: runs the automation engine on the user's own computer for runs
started from the ApplyXAI web app. LinkedIn sign-in happens in the browser window it opens,
so ApplyXAI never sees the LinkedIn password.

    python -m agent pair --server https://app.example.com
    python -m agent run
"""

AGENT_VERSION = "1.1.2"
