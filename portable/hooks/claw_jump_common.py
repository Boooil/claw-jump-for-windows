"""Common logic shared by Claw Jump hook scripts.

Parses Claude Code hook JSON from stdin and POSTs a normalized event
to the Claw Jump agent on 127.0.0.1:47653. Uses raw sockets to avoid
the heavy urllib import, keeping startup time minimal on Windows.
"""

import json
import os
import socket
import sys
from datetime import datetime, timezone


def send_event(event_name, raw_input, extra_fields=None):
    """Parse raw_input as Claude Code hook JSON and POST a normalized event."""
    try:
        if not raw_input or not raw_input.strip():
            sys.exit(0)
        raw = json.loads(raw_input)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    body = {
        "event": event_name,
        "sessionId": raw.get("session_id"),
        "cwd": raw.get("cwd"),
        "transcriptPath": raw.get("transcript_path"),
        "hookEventName": raw.get("hook_event_name"),
        "sourceApp": raw.get("source_app") or os.environ.get("TERM_PROGRAM"),
        "terminalTTY": os.environ.get("CLAW_JUMP_TTY"),
        "terminalSessionId": os.environ.get("TERM_SESSION_ID")
                            or os.environ.get("ITERM_SESSION_ID"),
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "platform": sys.platform,
    }
    if extra_fields:
        body.update(extra_fields)

    data = json.dumps(body).encode("utf-8")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        sock.connect(("127.0.0.1", 47653))
        req = (
            f"POST /event HTTP/1.1\r\n"
            f"Host: 127.0.0.1:47653\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(data)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("utf-8") + data
        sock.sendall(req)
        sock.recv(512)
        sock.close()
    except (OSError, socket.error, Exception):
        pass
