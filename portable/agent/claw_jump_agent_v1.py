#!/usr/bin/env python3
"""Claw Jump Agent — cross-platform desktop notifier for Claude Code.

Starts an HTTP server on 127.0.0.1:47653 and displays a bouncing claw
character overlay when Claude Code completes a response.

Usage:
  python claw_jump_agent.py                   Start the background agent
  python claw_jump_agent.py emit <event>      Send an event to a running agent
  python claw_jump_agent.py --help            Show this help
"""

import json
import logging
import os
import socket
import sys

DEFAULT_PORT = 47653

log = logging.getLogger("claw-jump")


# ---------- emit mode (no heavy imports) ---------------------------------

def _emit_event(event_name):
    payload = {"event": event_name, "sourceApp": "cli"}
    body = json.dumps(payload).encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect(("127.0.0.1", DEFAULT_PORT))
        req = (
            f"POST /event HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{DEFAULT_PORT}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("utf-8") + body
        sock.sendall(req)
        resp = sock.recv(512)
        if not resp.startswith(b"HTTP/1.0 2") and not resp.startswith(b"HTTP/1.1 2"):
            print("Agent returned an unexpected response.", file=sys.stderr)
            return 1
    except ConnectionRefusedError:
        print("Claw Jump agent is not running.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Failed to contact agent: {exc}", file=sys.stderr)
        return 1
    finally:
        sock.close()
    return 0


# ---------- agent mode ---------------------------------------------------

def _run_agent():
    """Start the full desktop agent. Imports are deferred until needed."""
    import tkinter as tk

    from cj_config import load_config, save_config
    from cj_debug import dbg
    from cj_overlay import ClawOverlay
    from cj_server import EventServer
    from cj_terminal import focus_terminal
    from cj_tray import SystemTray

    config = load_config()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    log.info("Starting Claw Jump agent on port %d", config.get("port", DEFAULT_PORT))

    # tracked state
    last_stop_by_session = {}
    displayed_source_app = None
    displayed_tty = None
    displayed_cwd = None
    displayed_session_id = None
    focus_enabled = False
    in_session = False

    # tk root (hidden)
    root = tk.Tk()
    root.withdraw()
    root.title("ClawJumpAgent")

    # quit flag
    quitting = False

    def request_quit():
        """Thread-safe: ask the mainloop to stop."""
        nonlocal quitting
        if quitting:
            return
        quitting = True
        log.info("Shutting down Claw Jump agent…")
        root.quit()  # safe to call from any thread

    root.protocol("WM_DELETE_WINDOW", request_quit)

    # overlay window
    overlay = ClawOverlay(
        on_activate=None,  # set below after closure variables are defined
        offset_x=config.get("overlay_offset_x", 0),
        offset_y=config.get("overlay_offset_y", 0),
        has_offset=config.get("has_persisted_offset", False),
    )

    # ---- callbacks layered on closure state ---------------------------

    def handle_event(payload):
        nonlocal last_stop_by_session, in_session
        event_name = payload.get("event", "")
        dbg("agent", "handle_event event=%s in_session=%s", event_name, in_session)
        if not isinstance(event_name, str):
            return

        if event_name == "reset":
            in_session = True
            overlay.set_working()
            return

        if event_name == "working":
            overlay.set_working()
            return

        if event_name == "notification":
            if not in_session:
                return
            if _should_display(payload, last_stop_by_session):
                last_stop_by_session = _update_cooldown(
                    payload, last_stop_by_session)
                _cache_context(payload)
                message = _display_message(payload)
                tty = payload.get("terminalTTY", "<none>")
                log.info("Received notification: %s (tty=%s)", message, tty)
                overlay.set_waiting_user(message)

        elif event_name == "stop":
            in_session = False
            if _should_display(payload, last_stop_by_session):
                last_stop_by_session = _update_cooldown(
                    payload, last_stop_by_session)
                _cache_context(payload)
                tty = payload.get("terminalTTY", "<none>")
                log.info("Received stop event (tty=%s)", tty)
                overlay.set_completed()

        elif event_name == "test":
            overlay.set_completed()

    def on_server_event(payload):
        dbg("agent", "on_server_event event=%s", payload.get("event", "?"))
        root.after(0, handle_event, payload)

    def on_activate():
        nonlocal displayed_source_app, displayed_tty, displayed_cwd, displayed_session_id
        overlay.reset_to_idle(overlay._state_message)

        if not focus_enabled:
            log.debug("Click-to-focus is disabled.")
            return

        if not displayed_source_app and not displayed_cwd:
            # No terminal context yet (e.g. emit test) — nothing to focus
            log.debug("No tracked terminal context to focus.")
            return

        log.info("Focus requested: source=%s tty=%s cwd=%s",
                 displayed_source_app or "<none>",
                 displayed_tty or "<none>",
                 displayed_cwd or "<none>")
        focused = focus_terminal(
            source_app=displayed_source_app,
            tty=displayed_tty,
            cwd=displayed_cwd,
            session_id=displayed_session_id,
        )
        if not focused:
            log.info("Could not activate the tracked terminal.")

    def on_test():
        root.after(0, overlay.set_completed)

    def on_reset():
        root.after(0, overlay.set_idle)

    def on_quit():
        root.after(0, request_quit)

    def _save_offset():
        ox, oy = overlay.get_offset()
        config["overlay_offset_x"] = ox
        config["overlay_offset_y"] = oy
        config["has_persisted_offset"] = True
        save_config(config)

    def _cache_context(payload):
        nonlocal displayed_source_app, displayed_tty, displayed_cwd, displayed_session_id
        if payload.get("sourceApp"):
            displayed_source_app = payload["sourceApp"]
        if payload.get("cwd"):
            displayed_cwd = payload["cwd"]
        if payload.get("terminalTTY"):
            displayed_tty = payload["terminalTTY"]
        if payload.get("terminalSessionId"):
            displayed_session_id = payload["terminalSessionId"]

    def on_focus():
        root.after(0, on_activate)

    def on_toggle_focus(enabled):
        nonlocal focus_enabled
        focus_enabled = enabled
        log.info("Click-to-focus %s", "enabled" if enabled else "disabled")

    # wire up the activate callback now that on_activate is defined
    overlay._on_activate = on_activate

    # HTTP server
    server = EventServer(port=config.get("port", DEFAULT_PORT), callback=on_server_event)
    server.start()
    log.info("HTTP server listening on 127.0.0.1:%d", server.port)

    # system tray
    tray = SystemTray(
        on_test=on_test,
        on_focus=on_focus,
        on_reset=on_reset,
        on_quit=on_quit,
        on_toggle_focus=on_toggle_focus,
        focus_enabled=focus_enabled,
    )
    tray.start()

    print("Claw Jump agent running. Press Ctrl+C or use tray menu → Quit to stop.", flush=True)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        log.info("Interrupted by Ctrl+C")
        request_quit()

    # mainloop exited — clean shutdown
    _save_offset()
    server.stop()
    tray.stop()
    overlay.destroy()
    try:
        root.destroy()
    except tk.TclError:
        pass
    log.info("Claw Jump agent stopped.")


def _should_display(payload, last_stop_by_session):
    session_id = payload.get("sessionId") or ""
    event_name = payload.get("event", "")
    if not session_id:
        return True
    import time
    cooldown = 5.0 if event_name == "notification" else 8.0
    now = time.time()
    key = f"{event_name}:{session_id}"
    last = last_stop_by_session.get(key)
    if last and (now - last) < cooldown:
        return False
    return True


def _update_cooldown(payload, last_stop_by_session):
    import time
    session_id = payload.get("sessionId") or ""
    event_name = payload.get("event", "")
    key = f"{event_name}:{session_id}"
    last_stop_by_session[key] = time.time()
    return last_stop_by_session


def _display_message(payload):
    message = payload.get("message") or ""
    if message:
        return message[:56] if len(message) > 56 else message
    return "Claude needs your input"


# ---------- entry --------------------------------------------------------

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "emit":
        if len(sys.argv) < 3:
            print("Usage: python claw_jump_agent.py emit <event>", file=sys.stderr)
            sys.exit(1)
        sys.exit(_emit_event(sys.argv[2]))

    if len(sys.argv) >= 2 and sys.argv[1] in ("--help", "-h", "help"):
        print(__doc__)
        sys.exit(0)

    _run_agent()


if __name__ == "__main__":
    main()
