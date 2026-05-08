"""Desktop overlay window with claw character and jump animation.

Replaces the macOS CJOverlayView.m + CJAppDelegate.m window management
using tkinter Canvas (cross-platform).
"""

import math
import os
import random
import sys
import tkinter as tk

from cj_debug import dbg


# ---------- geometry constants (matching original CJOverlayView.m) ----------

WIN_W = 220
WIN_H = 320

PEDESTAL_W = 104
PEDESTAL_H = 132
PEDESTAL_Y = 34

MASCOT_W = 92
MASCOT_H = 78
BODY_W = 68
BODY_H = 48
BODY_X = 12
BODY_Y = 26

LEFT_TAB_W = 12
LEFT_TAB_H = 30
LEFT_TAB_X = 4
LEFT_TAB_Y = 34

RIGHT_TAB_W = 12
RIGHT_TAB_H = 30
RIGHT_TAB_X = 76
RIGHT_TAB_Y = 34

LEG_W = 8
LEG_H = 24
LEG_Y = 2
LEG_OFFSETS = [18, 34, 50, 66]

EYE_R = 2.5
EYE_Y = 50
EYE_LEFT_X = 31
EYE_RIGHT_X = 53

AURA_W = 84
AURA_H = 84
AURA_X = 4
AURA_Y = -10

RING_W = 104
RING_H = 104
RING_X = -6
RING_Y = -20

SHADOW_W = 74
SHADOW_H = 16
SHADOW_Y = 28

MSG_BG_W = 172
MSG_BG_H = 22
MSG_BG_Y = 8

USB_W = 18
USB_H = 22
USB_PLUG_W = 7
USB_PLUG_H = 12

# idle / jump / waiting offsets relative to pedestal top
IDLE_OFFSET = -26    # mascot center Y relative to pedestal max Y
WAITING_OFFSET = 2
JUMP_OFFSET = 54

# animation timing
JUMP_DURATION = 0.82  # seconds
FPS = 60

# colours
C_PEDESTAL = "#91999E"       # silver-gray
C_PEDESTAL_FACE = "#C9CFD6"  # lighter overlay
C_PEDESTAL_BUTTON = "#B5B9BF"
C_PEDESTAL_BUTTON_BORDER = "#FFFFFF"
C_PEDESTAL_GLOW = "#F58529"  # orange pedestal glow during jump

C_USB_BODY = "#ABADB3"
C_USB_PLUG = "#575C63"

C_BODY_IDLE = "#B3451F"      # orange-red
C_TAB_IDLE = "#9C3B1A"       # darker
C_LEG_IDLE = "#A83F1C"

C_BODY_JUMP = "#F2CA47"      # golden
C_TAB_JUMP = "#EBAE29"
C_LEG_JUMP = "#F5BD2E"

C_SHADOW = "#000000"         # shadow (approximated with stipple on canvas)
C_MSG_BG = "#000000"
C_MSG_FG = "#FFFFFF"

C_AURA = "#FFD447"           # golden aura
C_RING = "#FFF29E"           # pulse ring
C_EYE = "#000000"

# transparent-colour key for borderless window
TRANS_KEY = "gray99"

# ---------- spinner verb list -----------------------------------------------

def _get_verbs_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "spinner_verbs_filtered.txt")
    return os.path.join(os.path.dirname(__file__), "spinner_verbs_filtered.txt")

_VERBS_PATH = _get_verbs_path()

def _load_spinner_verbs():
    try:
        with open(_VERBS_PATH, "r", encoding="utf-8") as f:
            verbs = [line.strip() for line in f if line.strip()]
        if verbs:
            return verbs
    except (OSError, IOError):
        pass
    return ["Working..."]

SPINNER_VERBS = _load_spinner_verbs()


# ---------- colour helpers -------------------------------------------------

def _lerp_rgb(c1_hex, c2_hex, t):
    """Linearly interpolate two hex colours (t in 0..1)."""
    t = max(0.0, min(1.0, t))

    def _to_rgb(h):
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    r1, g1, b1 = _to_rgb(c1_hex)
    r2, g2, b2 = _to_rgb(c2_hex)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------- overlay window ------------------------------------------------

class ClawOverlay:
    def __init__(self, on_activate=None, offset_x=0, offset_y=0, has_offset=False):
        self._on_activate = on_activate
        self._offset_x = offset_x
        self._offset_y = offset_y
        self._has_offset = has_offset

        self._anim_timer = None
        self._auto_reset_timer = None
        self._anim_data = None
        self._state_message = "目前无任务执行"

        self._make_window()

    # -- window creation ---------------------------------------------------

    def _make_window(self):
        self.root = tk.Toplevel()
        self.root.overrideredirect(True)
        self.root.geometry(f"{WIN_W}x{WIN_H}+{self._default_x()}+{self._default_y()}")
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANS_KEY)

        self.canvas = tk.Canvas(
            self.root,
            width=WIN_W,
            height=WIN_H,
            bg=TRANS_KEY,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()

        self._create_shapes()
        self._place_idle()

        # bindings
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self._drag_start_mouse = None
        self._drag_start_origin = None
        self._did_drag = False
        self._drag_threshold = 3  # px

        # keep window on top when screen layout changes
        self.root.bind("<FocusIn>", lambda e: self.root.attributes("-topmost", True))

    def _default_x(self):
        sw = self.root.winfo_screenwidth()
        x = sw - WIN_W - 24 + self._offset_x
        return max(0, min(x, sw - WIN_W))

    def _default_y(self):
        sh = self.root.winfo_screenheight()
        y = sh - WIN_H - 48 + self._offset_y  # ~taskbar height on Windows
        return max(0, min(y, sh - WIN_H))

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)

    def hide(self):
        self.root.withdraw()

    def destroy(self):
        self._cancel_animation("jump")
        self._cancel_animation("reset")
        self._cancel_auto_reset()
        if self.root:
            self.root.destroy()

    # -- shape creation ----------------------------------------------------

    def _create_shapes(self):
        c = self.canvas
        self._tagged = set()

        # shadow
        self._shadow = c.create_oval(0, 0, SHADOW_W, SHADOW_H,
                                     fill="", outline="", tags="shadow")
        self._tagged.add("shadow")

        # pedestal
        self._pedestal = c.create_rectangle(0, 0, PEDESTAL_W, PEDESTAL_H,
                                            fill=C_PEDESTAL, outline="", tags="pedestal")
        # pedestal face (lighter left strip)
        self._pedestal_face = c.create_rectangle(0, 0, 28, PEDESTAL_H,
                                                 fill=C_PEDESTAL_FACE, outline="", tags="pedestal")
        # pedestal glow (hidden in idle)
        gw = 54
        gh = 8
        self._pedestal_glow = c.create_rectangle(0, 0, gw, gh,
                                                 fill=C_PEDESTAL_GLOW, outline="", tags="glow")
        # pedestal button
        self._pedestal_button = c.create_rectangle(0, 0, 15, 15,
                                                   fill=C_PEDESTAL_BUTTON, outline=C_PEDESTAL_BUTTON_BORDER,
                                                   tags="pedestal")
        self._tagged.update(["pedestal", "glow"])

        # USB
        self._usb = c.create_rectangle(0, 0, USB_W, USB_H,
                                       fill=C_USB_BODY, outline="", tags="usb")
        self._usb_plug = c.create_rectangle(0, 0, USB_PLUG_W, USB_PLUG_H,
                                            fill=C_USB_PLUG, outline="", tags="usb")
        self._tagged.update(["usb"])

        # mascot container group (drawn directly on canvas)
        # aura
        self._aura = c.create_oval(0, 0, AURA_W, AURA_H,
                                   fill=C_AURA, outline="", tags="mascot")
        self._tagged.add("mascot")
        # ring
        self._ring = c.create_oval(0, 0, RING_W, RING_H,
                                   fill="", outline=C_RING, width=3, tags="mascot")
        # body
        self._body = c.create_rectangle(0, 0, BODY_W, BODY_H,
                                        fill=C_BODY_IDLE, outline="", tags="mascot")
        # left tab
        self._left_tab = c.create_rectangle(0, 0, LEFT_TAB_W, LEFT_TAB_H,
                                            fill=C_TAB_IDLE, outline="", tags="mascot")
        # right tab
        self._right_tab = c.create_rectangle(0, 0, RIGHT_TAB_W, RIGHT_TAB_H,
                                             fill=C_TAB_IDLE, outline="", tags="mascot")
        # legs
        self._legs = []
        for _ in range(4):
            leg = c.create_rectangle(0, 0, LEG_W, LEG_H,
                                     fill=C_LEG_IDLE, outline="", tags="mascot")
            self._legs.append(leg)
        # eyes
        self._eye_left = c.create_oval(0, 0, EYE_R * 2, EYE_R * 2,
                                       fill=C_EYE, outline="", tags="mascot")
        self._eye_right = c.create_oval(0, 0, EYE_R * 2, EYE_R * 2,
                                        fill=C_EYE, outline="", tags="mascot")

        # message
        self._msg_bg = c.create_rectangle(0, 0, MSG_BG_W, MSG_BG_H,
                                          fill=C_MSG_BG, outline="", tags="msg")
        self._msg_text = c.create_text(MSG_BG_W // 2, MSG_BG_H // 2,
                                       text="目前无任务执行",
                                       fill=C_MSG_FG, font=("", 10), tags="msg")
        self._tagged.add("msg")

        # set initial opacities via itemconfig (tkinter colours are opaque,
        # so we control visibility via state)
        self._set_glow_state(0.0)

    # -- coordinate system ---------------------------------------------------
    # The original macOS code uses a bottom-left origin (y increases upward).
    # tkinter uses top-left origin (y increases downward).
    # All internal calculations stay in macOS space; _mac2tk_* helpers flip
    # values to tkinter when talking to the Canvas.

    def _mac2tk_y(self, mac_y):
        """Convert a macOS y (distance from window bottom) to tkinter y."""
        return WIN_H - mac_y

    def _mac2tk_rect_y(self, mac_y, height):
        """Convert a macOS rect origin.y to tkinter rect top y."""
        return WIN_H - mac_y - height

    # -- layout ------------------------------------------------------------

    def _center_x(self):
        return WIN_W / 2.0

    def _pedestal_x(self):
        return self._center_x() - PEDESTAL_W / 2.0

    # ---------- all these are macOS coordinates (measured from bottom) -----

    def _pedestal_bottom_mac(self):
        return PEDESTAL_Y

    def _pedestal_top_mac(self):
        return PEDESTAL_Y + PEDESTAL_H

    def _mascot_origin_x(self):
        return self._center_x() - MASCOT_W / 2.0

    def _mascot_idle_y_mac(self):
        return self._pedestal_top_mac() + IDLE_OFFSET

    def _mascot_waiting_y_mac(self):
        return self._pedestal_top_mac() + WAITING_OFFSET

    def _mascot_jump_y_mac(self):
        return self._pedestal_top_mac() + JUMP_OFFSET

    def _current_mascot_y_mac(self):
        """Read current mascot Y (macOS space) from the body shape.

        The body's tk-top is body_top_tk = WIN_H - mascot_y_mac
          - MASCOT_H/2 + (MASCOT_H - BODY_Y - BODY_H)
          = WIN_H - mascot_y_mac - 39 + (78 - 74)
          = WIN_H - mascot_y_mac - 35

        So mascot_y_mac = WIN_H - body_top_tk - 35.
        """
        coords = self.canvas.coords(self._body)
        body_top_tk = coords[1]
        return WIN_H - body_top_tk - 35

    def _place_idle(self):
        self._place_static(self._mascot_idle_y_mac())
        self._set_colors_idle()
        self._set_glow_state(0.0)
        self._set_aura_ring_state(0.0, 1.0, 0.0, 1.0)
        self._set_shadow(1.0, 0.18)

    def _place_static(self, mascot_y_mac):
        """Layout all elements. Coordinates in macOS space (y from bottom)
        are flipped to tkinter space (y from top) before setting on Canvas."""
        c = self.canvas
        cx = self._center_x()
        px = self._pedestal_x()

        # pedestal (macOS rect: bottom at PEDESTAL_Y, height PEDESTAL_H)
        ped_tk_y = self._mac2tk_rect_y(PEDESTAL_Y, PEDESTAL_H)
        c.coords(self._pedestal, px, ped_tk_y, px + PEDESTAL_W, ped_tk_y + PEDESTAL_H)
        c.coords(self._pedestal_face, px, ped_tk_y, px + 28, ped_tk_y + PEDESTAL_H)
        gw, gh = 54, 8
        gx = px + (PEDESTAL_W - gw) / 2.0
        gy = self._mac2tk_rect_y(self._pedestal_top_mac() - 6, gh)
        c.coords(self._pedestal_glow, gx, gy, gx + gw, gy + gh)
        # button (y=14 from pedestal bottom in macOS)
        btn_mac_y = PEDESTAL_Y + 14
        btn_tk_y = self._mac2tk_rect_y(btn_mac_y, 15)
        c.coords(self._pedestal_button, px + 14, btn_tk_y, px + 29, btn_tk_y + 15)

        # shadow (macOS: bottom at SHADOW_Y, height SHADOW_H)
        sw_x = cx - SHADOW_W / 2.0
        sw_tk_y = self._mac2tk_rect_y(SHADOW_Y, SHADOW_H)
        c.coords(self._shadow, sw_x, sw_tk_y, sw_x + SHADOW_W, sw_tk_y + SHADOW_H)

        # USB (macOS: bottom at PEDESTAL_Y + 16, height USB_H)
        usb_mac_bottom = PEDESTAL_Y + 16
        usb_x = px + PEDESTAL_W - 4
        usb_tk_y = self._mac2tk_rect_y(usb_mac_bottom, USB_H)
        c.coords(self._usb, usb_x, usb_tk_y, usb_x + USB_W, usb_tk_y + USB_H)
        # USB plug (macOS: bottom at usb_mac_bottom + 5, height USB_PLUG_H)
        plug_mac_bottom = usb_mac_bottom + 5
        plug_tk_y = self._mac2tk_rect_y(plug_mac_bottom, USB_PLUG_H)
        c.coords(self._usb_plug, usb_x - 5, plug_tk_y,
                 usb_x - 5 + USB_PLUG_W, plug_tk_y + USB_PLUG_H)

        # mascot container: macOS center y = mascot_y_mac (distance from window bottom)
        # Container bounds: 92 x 78. In macOS space:
        #   container bottom = mascot_y_mac - MASCOT_H/2
        #   container top    = mascot_y_mac + MASCOT_H/2
        # In tkinter:
        #   container top    = WIN_H - (mascot_y_mac + MASCOT_H/2)
        #   container bottom = WIN_H - (mascot_y_mac - MASCOT_H/2)
        mx = self._mascot_origin_x()
        mascot_top_tk = WIN_H - (mascot_y_mac + MASCOT_H / 2.0)

        # All mascot sub-elements: mac_y is distance from container bottom.
        # tk_y = mascot_top_tk + (MASCOT_H - (mac_y + element_h))
        def _sub_tk_y(mac_sub_y, h):
            return mascot_top_tk + (MASCOT_H - (mac_sub_y + h))

        # aura
        c.coords(self._aura,
                 mx + AURA_X, _sub_tk_y(AURA_Y, AURA_H),
                 mx + AURA_X + AURA_W, _sub_tk_y(AURA_Y, AURA_H) + AURA_H)
        # ring
        c.coords(self._ring,
                 mx + RING_X, _sub_tk_y(RING_Y, RING_H),
                 mx + RING_X + RING_W, _sub_tk_y(RING_Y, RING_H) + RING_H)
        # body
        c.coords(self._body,
                 mx + BODY_X, _sub_tk_y(BODY_Y, BODY_H),
                 mx + BODY_X + BODY_W, _sub_tk_y(BODY_Y, BODY_H) + BODY_H)
        # tabs
        c.coords(self._left_tab,
                 mx + LEFT_TAB_X, _sub_tk_y(LEFT_TAB_Y, LEFT_TAB_H),
                 mx + LEFT_TAB_X + LEFT_TAB_W, _sub_tk_y(LEFT_TAB_Y, LEFT_TAB_H) + LEFT_TAB_H)
        c.coords(self._right_tab,
                 mx + RIGHT_TAB_X, _sub_tk_y(RIGHT_TAB_Y, RIGHT_TAB_H),
                 mx + RIGHT_TAB_X + RIGHT_TAB_W, _sub_tk_y(RIGHT_TAB_Y, RIGHT_TAB_H) + RIGHT_TAB_H)
        # legs
        for i, leg in enumerate(self._legs):
            lx = mx + LEG_OFFSETS[i]
            c.coords(leg,
                     lx, _sub_tk_y(LEG_Y, LEG_H),
                     lx + LEG_W, _sub_tk_y(LEG_Y, LEG_H) + LEG_H)
        # eyes
        c.coords(self._eye_left,
                 mx + EYE_LEFT_X - EYE_R, _sub_tk_y(EYE_Y, EYE_R * 2),
                 mx + EYE_LEFT_X + EYE_R, _sub_tk_y(EYE_Y, EYE_R * 2) + EYE_R * 2)
        c.coords(self._eye_right,
                 mx + EYE_RIGHT_X - EYE_R, _sub_tk_y(EYE_Y, EYE_R * 2),
                 mx + EYE_RIGHT_X + EYE_R, _sub_tk_y(EYE_Y, EYE_R * 2) + EYE_R * 2)

        # message (macOS: bottom at MSG_BG_Y, height MSG_BG_H)
        msg_x = cx - MSG_BG_W / 2.0
        msg_tk_y = self._mac2tk_rect_y(MSG_BG_Y, MSG_BG_H)
        c.coords(self._msg_bg, msg_x, msg_tk_y, msg_x + MSG_BG_W, msg_tk_y + MSG_BG_H)
        c.coords(self._msg_text, msg_x + MSG_BG_W / 2.0, msg_tk_y + MSG_BG_H / 2.0)

    # -- colour helpers ----------------------------------------------------

    def _set_colors_idle(self):
        self.canvas.itemconfig(self._body, fill=C_BODY_IDLE)
        self.canvas.itemconfig(self._left_tab, fill=C_TAB_IDLE)
        self.canvas.itemconfig(self._right_tab, fill=C_TAB_IDLE)
        for leg in self._legs:
            self.canvas.itemconfig(leg, fill=C_LEG_IDLE)

    def _set_colors_jump(self):
        self.canvas.itemconfig(self._body, fill=C_BODY_JUMP)
        self.canvas.itemconfig(self._left_tab, fill=C_TAB_JUMP)
        self.canvas.itemconfig(self._right_tab, fill=C_TAB_JUMP)
        for leg in self._legs:
            self.canvas.itemconfig(leg, fill=C_LEG_JUMP)

    def _set_colors_interp(self, t):
        """Interpolate colours between idle and jump (t in 0..1)."""
        body_c = _lerp_rgb(C_BODY_IDLE, C_BODY_JUMP, t)
        tab_c = _lerp_rgb(C_TAB_IDLE, C_TAB_JUMP, t)
        leg_c = _lerp_rgb(C_LEG_IDLE, C_LEG_JUMP, t)
        self.canvas.itemconfig(self._body, fill=body_c)
        self.canvas.itemconfig(self._left_tab, fill=tab_c)
        self.canvas.itemconfig(self._right_tab, fill=tab_c)
        for leg in self._legs:
            self.canvas.itemconfig(leg, fill=leg_c)

    def _set_shadow(self, scale_x, opacity):
        """Approximate shadow: scale width and change opacity via fill colour."""
        cx = self._center_x()
        base_w = SHADOW_W
        new_w = base_w * scale_x
        sx = cx - new_w / 2.0
        sy = self._mac2tk_rect_y(SHADOW_Y, SHADOW_H)
        self.canvas.coords(self._shadow, sx, sy, sx + new_w, sy + SHADOW_H)
        # approximate opacity with gray
        if opacity < 0.1:
            self.canvas.itemconfig(self._shadow, fill="", outline="")
        else:
            v = int(255 * (1.0 - opacity * 0.8))
            c = f"#{v:02x}{v:02x}{v:02x}"
            self.canvas.itemconfig(self._shadow, fill=c, outline="")

    def _set_glow_state(self, opacity):
        if opacity < 0.01:
            self.canvas.itemconfig(self._pedestal_glow, state="hidden")
        else:
            self.canvas.itemconfig(self._pedestal_glow, state="normal")

    def _set_aura_ring_state(self, aura_opacity, aura_scale, ring_opacity, ring_scale):
        """Show/hide aura and ring based on opacity thresholds, adjusting scale."""
        # aura
        if aura_opacity < 0.01:
            self.canvas.itemconfig(self._aura, state="hidden")
        else:
            self.canvas.itemconfig(self._aura, state="normal")
            self._scale_aura(aura_scale)

        # ring
        if ring_opacity < 0.01:
            self.canvas.itemconfig(self._ring, state="hidden")
        else:
            self.canvas.itemconfig(self._ring, state="normal")
            self._scale_ring(ring_scale)

    def _scale_aura(self, scale):
        mx = self._mascot_origin_x()
        my_mac = self._current_mascot_y_mac()
        mascot_top_tk = WIN_H - (my_mac + MASCOT_H / 2.0)
        # macOS: aura bottom = my_mac - MASCOT_H/2 + AURA_Y, height AURA_H
        aura_mac_bottom = my_mac - MASCOT_H / 2.0 + AURA_Y
        aura_mac_center_y = aura_mac_bottom + AURA_H / 2.0
        aura_tk_center_y = WIN_H - aura_mac_center_y
        orig_cx = mx + AURA_X + AURA_W / 2.0
        hw = (AURA_W * scale) / 2.0
        hh = (AURA_H * scale) / 2.0
        self.canvas.coords(self._aura,
                           orig_cx - hw, aura_tk_center_y - hh,
                           orig_cx + hw, aura_tk_center_y + hh)

    def _scale_ring(self, scale):
        mx = self._mascot_origin_x()
        my_mac = self._current_mascot_y_mac()
        ring_mac_bottom = my_mac - MASCOT_H / 2.0 + RING_Y
        ring_mac_center_y = ring_mac_bottom + RING_H / 2.0
        ring_tk_center_y = WIN_H - ring_mac_center_y
        orig_cx = mx + RING_X + RING_W / 2.0
        hw = (RING_W * scale) / 2.0
        hh = (RING_H * scale) / 2.0
        self.canvas.coords(self._ring,
                           orig_cx - hw, ring_tk_center_y - hh,
                           orig_cx + hw, ring_tk_center_y + hh)

    # ---------- animation -------------------------------------------------

    # -- state machine -----------------------------------------------------

    def set_working(self):
        """Show a random spinner verb without animation."""
        dbg("overlay", "set_working")
        verb = random.choice(SPINNER_VERBS)
        if verb and verb[-1] not in "?!.'\"":
            verb += "..."
        self._state_message = verb
        self.reset_to_idle(verb)

    def set_waiting_user(self, notification_msg=""):
        """Jump animation then show 等待用户操作."""
        dbg("overlay", "set_waiting_user msg=%s", notification_msg[:30] if notification_msg else "")
        self._state_message = "等待用户操作"
        self._play_jump(notification_msg or "Claude needs your input")

    def set_completed(self):
        """Jump animation then show 目前无任务执行."""
        self._state_message = "目前无任务执行"
        self._play_jump("当前任务完成！")

    def set_idle(self):
        """Show 目前无任务执行 without animation."""
        self._state_message = "目前无任务执行"
        self.reset_to_idle()

    def _play_jump(self, message):
        """Internal: start jump animation. Uses _state_message for settle."""
        dbg("overlay", "_play_jump start msg=%s", message[:30] if message else "")
        self._cancel_animation("jump")
        self._cancel_animation("reset")
        self._cancel_auto_reset()
        self._set_message(message)
        self.show()

        start_y = self._current_mascot_y_mac()
        jump_y = self._mascot_jump_y_mac()
        waiting_y = self._mascot_waiting_y_mac()

        total_frames = int(JUMP_DURATION * FPS)
        self._anim_data = {
            "type": "jump",
            "frame": 0,
            "total": total_frames,
            "start_y": start_y,
            "jump_y": jump_y,
            "waiting_y": waiting_y,
            "interval": int(1000.0 / FPS),
        }
        self._anim_step()

    def _anim_step(self):
        data = self._anim_data
        if data is None:
            return

        frame = data["frame"]
        total = data["total"]
        t = frame / total if total > 0 else 1.0

        if data["type"] == "jump":
            self._jump_frame(t)
        elif data["type"] == "reset":
            self._reset_frame(t)

        data["frame"] += 1
        if frame < total:
            self._anim_timer = self.root.after(data["interval"], self._anim_step)
        else:
            if data["type"] == "jump":
                self._jump_finish()
            elif data["type"] == "reset":
                self._reset_finish()

    def _jump_frame(self, t):
        """One frame of the jump animation (t in 0..1)."""
        start_y = self._anim_data["start_y"]
        jump_y = self._anim_data["jump_y"]
        waiting_y = self._anim_data["waiting_y"]

        # position: keyTimes [0, 0.42, 1.0]
        if t < 0.42:
            pt = t / 0.42
            eased = 1.0 - (1.0 - pt) ** 3  # ease-out
            y = start_y + (jump_y - start_y) * eased
        else:
            pt = (t - 0.42) / 0.58
            eased = pt ** 2  # ease-in approx
            y = jump_y + (waiting_y - jump_y) * eased

        self._place_static(y)

        # shadow scale: 1.0 → 0.76 → 1.02 (same keyTimes)
        if t < 0.42:
            ss = 1.0 + (0.76 - 1.0) * (t / 0.42)
        else:
            ss = 0.76 + (1.02 - 0.76) * ((t - 0.42) / 0.58)

        # shadow opacity: 0.18 → 0.08 → 0.18
        so = 0.18 + (0.08 - 0.18) * min(t / 0.42, 1.0) if t < 0.42 else 0.08 + (0.18 - 0.08) * ((t - 0.42) / 0.58)
        self._set_shadow(ss, so)

        # pedestal glow: 0 → 1 → 0.28
        if t < 0.42:
            go = t / 0.42
        else:
            go = 1.0 + (0.28 - 1.0) * ((t - 0.42) / 0.58)
        self._set_glow_state(go)

        # aura opacity: 0 → 0.95 → 0.26
        if t < 0.42:
            ao = (t / 0.42) * 0.95
        else:
            ao = 0.95 + (0.26 - 0.95) * ((t - 0.42) / 0.58)
        # aura scale: 0.78 → 1.18 → 1.0
        if t < 0.42:
            asc = 0.78 + (1.18 - 0.78) * (t / 0.42)
        else:
            asc = 1.18 + (1.0 - 1.18) * ((t - 0.42) / 0.58)
        self._set_aura_ring_state(ao, asc, 0.0, 1.0)

        # ring opacity: 0 → 0.82 → 0  (keyTimes [0, 0.38, 1.0])
        if t < 0.38:
            ro = (t / 0.38) * 0.82
        else:
            ro = 0.82 * (1.0 - (t - 0.38) / 0.62)
        # ring scale: 0.72 → 1.0 → 1.34 (keyTimes [0, 0.36, 1.0])
        if t < 0.36:
            rsc = 0.72 + (1.0 - 0.72) * (t / 0.36)
        else:
            rsc = 1.0 + (1.34 - 1.0) * ((t - 0.36) / 0.64)
        self._set_aura_ring_state(ao, asc, ro, rsc)

        # body colour interpolation (leading the position slightly)
        ct = min(1.0, t * 1.4)
        self._set_colors_interp(ct)

    def _jump_finish(self):
        self._anim_data = None
        self.reset_to_idle(self._state_message)

    # -- reset -------------------------------------------------------------

    def reset_to_idle(self, message="目前无任务执行"):
        self._cancel_animation("jump")
        self._cancel_animation("reset")
        self._cancel_auto_reset()
        self._set_message(message)

        # If already idle (glow hidden), just update message — no animation
        if self.canvas.itemcget(self._pedestal_glow, "state") == "hidden":
            return

        start_y = self._current_mascot_y_mac()
        idle_y = self._mascot_idle_y_mac()

        total_frames = int(0.28 * FPS)  # 280ms settle
        self._anim_data = {
            "type": "reset",
            "frame": 0,
            "total": total_frames,
            "start_y": start_y,
            "idle_y": idle_y,
            "interval": int(1000.0 / FPS),
            "start_glow": 0.28,
            "start_aura": 0.26,
        }
        self._anim_step()

    def _reset_frame(self, t):
        start_y = self._anim_data["start_y"]
        idle_y = self._anim_data["idle_y"]
        eased = 1.0 - (1.0 - t) ** 2  # ease-out
        y = start_y + (idle_y - start_y) * eased
        self._place_static(y)

        # fade glow, aura
        sg = self._anim_data.get("start_glow", 0.28)
        sa = self._anim_data.get("start_aura", 0.26)
        self._set_glow_state(sg * (1.0 - t))
        self._set_aura_ring_state(sa * (1.0 - t), 1.0, 0.0, 1.0)

        # colour back to idle
        self._set_colors_interp(1.0 - t)
        self._set_shadow(1.0, 0.18)

    def _reset_finish(self):
        self._place_idle()
        self._anim_data = None

    # -- utilities ---------------------------------------------------------

    def _set_message(self, text):
        if not text:
            text = "Claude Code is ready"
        if len(text) > 56:
            text = text[:53] + "..."
        self.canvas.itemconfig(self._msg_text, text=text)

    def _cancel_animation(self, typ):
        if self._anim_data and self._anim_data.get("type") == typ:
            self._anim_data = None
        if self._anim_timer:
            self.root.after_cancel(self._anim_timer)
            self._anim_timer = None

    def _cancel_auto_reset(self):
        if self._auto_reset_timer:
            self.root.after_cancel(self._auto_reset_timer)
            self._auto_reset_timer = None

    # -- drag --------------------------------------------------------------

    def _on_click(self, event):
        self._drag_start_mouse = (event.x_root, event.y_root)
        self._drag_start_origin = (self.root.winfo_x(), self.root.winfo_y())
        self._did_drag = False

    def _on_drag(self, event):
        if self._drag_start_mouse is None:
            return
        dx = event.x_root - self._drag_start_mouse[0]
        dy = event.y_root - self._drag_start_mouse[1]
        if abs(dx) > self._drag_threshold or abs(dy) > self._drag_threshold:
            self._did_drag = True
        nx = self._drag_start_origin[0] + dx
        ny = self._drag_start_origin[1] + dy
        # clamp to screen
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        nx = max(0, min(nx, sw - WIN_W))
        ny = max(0, min(ny, sh - WIN_H))
        self.root.geometry(f"+{nx}+{ny}")

    def _on_release(self, event):
        if not self._did_drag and self._on_activate:
            self._on_activate()
        self._drag_start_mouse = None
        self._drag_start_origin = None
        self._did_drag = False

    # -- offset for persistence -------------------------------------------

    def get_offset(self):
        """Return (offset_x, offset_y) relative to default bottom-right."""
        default_x = WIN_W - WIN_W - 24  # actually let's compute properly
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        default_x = sw - WIN_W - 24
        default_y = sh - WIN_H - 48
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        return (cur_x - default_x, cur_y - default_y)
