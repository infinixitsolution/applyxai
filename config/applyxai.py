'''
ApplyXAI agent run extras (human Q&A patterns, platform AI proxy). Loaded from the run
config JSON section "applyxai" when APPLYXAI_RUN_CONFIG is set.
'''

ai_use_platform_proxy = False
run_id = ""
human_questions = []
ai_policy = {"deny_label_contains": []}
resume_mode = "default"

import config._overrides as _o

_o.apply(__name__, globals())
