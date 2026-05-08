import os
import subprocess
import sys


def focus_terminal(source_app, tty=None, cwd=None, session_id=None):
    """Best-effort focus the terminal that ran Claude Code.

    Returns True if a terminal was found and focused, False otherwise.
    """
    if sys.platform == "darwin":
        return _focus_darwin(source_app, tty, cwd)
    elif sys.platform == "win32":
        return _focus_windows(source_app, cwd)
    else:
        return _focus_linux(source_app, cwd)


# ---- macOS ------------------------------------------------------------

def _focus_darwin(source_app, tty, cwd):
    # 1) Try to activate a specific iTerm / Terminal tab by tty
    if tty and source_app:
        lower = source_app.lower()
        if "iterm" in lower:
            if _darwin_osa_iterm_tty(tty):
                return True
        elif "terminal" in lower or "apple_terminal" in lower:
            if _darwin_osa_terminal_tty(tty):
                return True

    # 2) Activate the application by bundle id
    bundle_id = _darwin_bundle_id(source_app)
    if bundle_id and _darwin_activate_bundle(bundle_id):
        return True

    # 3) AppleScript activate by name
    app_name = _darwin_app_name(source_app)
    if app_name and _darwin_osa_activate(app_name):
        return True

    # 4) Fallback: open project directory
    if cwd and os.path.isdir(cwd):
        subprocess.run(["open", cwd], check=False)
        return True

    return False


def _darwin_osa_iterm_tty(tty):
    escaped = tty.replace('"', '\\"')
    for name in ("iTerm", "iTerm2"):
        script = (
            f'tell application "{name}"\n'
            f'  repeat with w in windows\n'
            f'    repeat with t in tabs of w\n'
            f'      repeat with s in sessions of t\n'
            f'        if tty of s is "{escaped}" then\n'
            f'          tell application "{name}" to activate\n'
            f'          tell w to set current tab to t\n'
            f'          tell w to set index to 1\n'
            f'          select s\n'
            f'          return true\n'
            f'        end if\n'
            f'      end repeat\n'
            f'    end repeat\n'
            f'  end repeat\n'
            f'end tell\n'
            f'return false'
        )
        try:
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
            if "true" in r.stdout:
                return True
        except Exception:
            pass
    return False


def _darwin_osa_terminal_tty(tty):
    escaped = tty.replace('"', '\\"')
    script = (
        f'tell application "Terminal"\n'
        f'  repeat with w in windows\n'
        f'    repeat with t in tabs of w\n'
        f'      if tty of t is "{escaped}" then\n'
        f'        activate\n'
        f'        set selected tab of w to t\n'
        f'        set index of w to 1\n'
        f'        return true\n'
        f'      end if\n'
        f'    end repeat\n'
        f'  end repeat\n'
        f'end tell\n'
        f'return false'
    )
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
        if "true" in r.stdout:
            return True
    except Exception:
        pass
    return False


def _darwin_bundle_id(source_app):
    if not source_app:
        return None
    lower = source_app.lower()
    if "iterm" in lower:
        return "com.googlecode.iterm2"
    if "apple_terminal" in lower or lower == "terminal":
        return "com.apple.Terminal"
    if "wezterm" in lower:
        return "com.github.wez.wezterm"
    if "warp" in lower:
        return "dev.warp.Warp-Stable"
    if "ghostty" in lower:
        return "com.mitchellh.ghostty"
    if "kitty" in lower:
        return "net.kovidgoyal.kitty"
    if "vscode" in lower:
        return "com.microsoft.VSCode"
    if "cursor" in lower:
        return "com.todesktop.230313mzl4w4u92"
    return None


def _darwin_app_name(source_app):
    if not source_app:
        return None
    lower = source_app.lower()
    if "iterm" in lower:
        return "iTerm"
    if "apple_terminal" in lower or lower == "terminal":
        return "Terminal"
    if "wezterm" in lower:
        return "WezTerm"
    if "warp" in lower:
        return "Warp"
    if "ghostty" in lower:
        return "Ghostty"
    if "kitty" in lower:
        return "kitty"
    return None


def _darwin_activate_bundle(bundle_id):
    script = (
        f'tell application "System Events"\n'
        f'  set theApp to first application process whose bundle identifier is "{bundle_id}"\n'
        f'  set frontmost of theApp to true\n'
        f'end tell'
    )
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3, check=False)
        return True
    except Exception:
        return False


def _darwin_osa_activate(app_name):
    script = f'tell application "{app_name}" to activate'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3, check=False)
        return True
    except Exception:
        return False


# ---- Windows ----------------------------------------------------------

def _focus_windows(source_app, cwd):
    # 1) Try to find and activate the terminal window by title
    title = _windows_terminal_title(source_app)
    if title and _win32_activate_by_title(title):
        return True

    # 2) Try launching Windows Terminal with focus
    if cwd and os.path.isdir(cwd):
        try:
            subprocess.run(["wt", "-d", cwd], check=False, timeout=3)
            return True
        except Exception:
            pass

    # 3) Fallback: open project directory in Explorer
    if cwd and os.path.isdir(cwd):
        os.startfile(cwd)
        return True

    return False


def _windows_terminal_title(source_app):
    if not source_app:
        return None
    lower = source_app.lower()
    if "vscode" in lower:
        return "Visual Studio Code"
    if "cursor" in lower:
        return "Cursor"
    if "windows_terminal" in lower or "wt" in lower:
        return "Windows Terminal"
    if "wezterm" in lower:
        return "WezTerm"
    return source_app


def _win32_activate_by_title(title_substring):
    try:
        import ctypes
        hwnd = ctypes.windll.user32.FindWindowW(None, None)
        # Enumerate top-level windows
        GW_HWNDNEXT = 2
        found = None
        while hwnd:
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_substring.lower() in buf.value.lower():
                    found = hwnd
                    break
            hwnd = ctypes.windll.user32.GetWindow(hwnd, GW_HWNDNEXT)
        if found:
            ctypes.windll.user32.SetForegroundWindow(found)
            return True
    except Exception:
        pass
    return False


# ---- Linux ------------------------------------------------------------

def _focus_linux(source_app, cwd):
    if cwd and os.path.isdir(cwd):
        try:
            subprocess.run(["xdg-open", cwd], check=False, timeout=3)
            return True
        except Exception:
            pass
    return False
