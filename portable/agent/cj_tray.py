import sys
import tkinter as tk


class SystemTray:
    """Cross-platform system tray icon.

    Uses pystray when available (recommended), falls back to a minimal
    tkinter window when pystray is not installed.
    """

    def __init__(self, on_test=None, on_focus=None, on_reset=None, on_quit=None,
                 on_toggle_focus=None, focus_enabled=False):
        self._on_test = on_test
        self._on_focus = on_focus
        self._on_reset = on_reset
        self._on_quit = on_quit
        self._on_toggle_focus = on_toggle_focus
        self._focus_enabled = focus_enabled
        self._tray = None
        self._fallback_window = None

    def start(self):
        try:
            self._start_pystray()
        except Exception:
            self._start_fallback()

    def stop(self):
        if self._tray:
            self._tray.stop()
            self._tray = None
        if self._fallback_window:
            self._fallback_window.destroy()
            self._fallback_window = None

    # -- pystray path ---------------------------------------------------

    def _start_pystray(self):
        import pystray
        from PIL import Image, ImageDraw

        icon_img = self._make_tray_icon_pillow(32)

        menu = pystray.Menu(
            pystray.MenuItem("Test Jump", self._wrap(self._on_test), default=True),
            pystray.MenuItem("Focus Terminal", self._wrap(self._on_focus)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Click to Focus Terminal",
                self._wrap_toggle_focus(),
                checked=lambda item: self._focus_enabled,
            ),
            pystray.MenuItem("Reset", self._wrap(self._on_reset)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._wrap(self._on_quit)),
        )
        self._tray = pystray.Icon("claw-jump", icon_img, "Claw Jump", menu)
        self._tray.run_detached()

    @staticmethod
    def _make_tray_icon_pillow(size):
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        margin = size // 8
        cx = size // 2
        cy = size // 2
        # body
        bw, bh = size - 2 * margin, size // 2
        bx0, by0 = cx - bw // 2, cy - bh // 2
        draw.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=size // 6,
                               fill=(179, 69, 31))
        # ears
        ew, eh = size // 4, size // 3
        draw.rounded_rectangle([cx - bw // 2, by0 - eh // 2, cx - bw // 2 + ew, by0 + eh // 2],
                               radius=size // 8, fill=(156, 59, 26))
        draw.rounded_rectangle([cx + bw // 2 - ew, by0 - eh // 2, cx + bw // 2, by0 + eh // 2],
                               radius=size // 8, fill=(156, 59, 26))
        # eyes
        er = max(2, size // 12)
        draw.ellipse([cx - size // 6 - er, cy - er, cx - size // 6 + er, cy + er],
                     fill=(30, 30, 30))
        draw.ellipse([cx + size // 6 - er, cy - er, cx + size // 6 + er, cy + er],
                     fill=(30, 30, 30))
        return img

    def _wrap(self, callback):
        def handler(icon, item=None):
            if callback:
                callback()
        return handler

    def _wrap_toggle_focus(self):
        def handler(icon, item=None):
            self._focus_enabled = not self._focus_enabled
            if self._on_toggle_focus:
                self._on_toggle_focus(self._focus_enabled)
        return handler

    # -- tkinter fallback ------------------------------------------------

    def _start_fallback(self):
        self._fallback_window = tk.Toplevel()
        self._fallback_window.title("Claw Jump")
        self._fallback_window.geometry("180x195")
        self._fallback_window.resizable(False, False)
        self._fallback_window.attributes("-topmost", True)
        self._fallback_window.protocol("WM_DELETE_WINDOW", self._fallback_window.withdraw)

        tk.Label(self._fallback_window, text="Claw Jump", font=("", 12, "bold")).pack(pady=8)

        def mkbtn(text, cmd):
            tk.Button(self._fallback_window, text=text, command=cmd, width=20).pack(pady=2)

        mkbtn("Test Jump", self._on_test)
        mkbtn("Focus Terminal", self._on_focus)

        # toggle for click-to-focus
        self._focus_var = tk.BooleanVar(value=self._focus_enabled)
        tk.Checkbutton(
            self._fallback_window,
            text="Click to Focus Terminal",
            variable=self._focus_var,
            command=self._on_fallback_toggle_focus,
        ).pack(pady=2)

        mkbtn("Reset", self._on_reset)
        mkbtn("Quit", self._on_quit)

        # try to withdraw immediately so only the tray icon shows
        self._fallback_window.withdraw()

    def _on_fallback_toggle_focus(self):
        self._focus_enabled = self._focus_var.get()
        if self._on_toggle_focus:
            self._on_toggle_focus(self._focus_enabled)

    def show_fallback(self):
        if self._fallback_window:
            self._fallback_window.deiconify()
            self._fallback_window.lift()
