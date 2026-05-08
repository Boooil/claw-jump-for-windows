#!/usr/bin/env python3
"""Claude Code Notification hook: notifies Claw Jump with the notification message."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claw_jump_common import send_event

raw_input = sys.stdin.read()

# Extract message before normalizing
try:
    raw = json.loads(raw_input)
    message = raw.get("message", "")
except Exception:
    message = ""

send_event("notification", raw_input, extra_fields={"message": message})
