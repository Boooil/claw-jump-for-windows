#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook: resets Claw Jump to idle."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claw_jump_common import send_event

raw_input = sys.stdin.read()
send_event("reset", raw_input)
