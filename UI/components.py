"""Shared widgets: the app bar, buttons, fields, strength meter and modals.

Every screen is assembled from these so the look stays consistent and a
palette change in UI/palette.json propagates everywhere.
"""
import customtkinter as ctk

from UI import icons
from UI import keyboard
from UI import theme as T


focusable = keyboard.focusable  # for the CTk controls a screen makes itself


# --------------------------------------------------------------------------
# Buttons
# --------------------------------------------------------------------------
def _button(parent, text, command, fg, hover, text_color, **kw):
    kw.setdefault("height", T.H_BTN)
    kw.setdefault("corner_radius", T.R_BTN)
    kw.setdefault("font", T.font(T.S_BODY, "bold"))
    return keyboard.focusable(ctk.CTkButton(
        parent, text=text, command=command, fg_color=fg, hover_color=hover,
        text_color=text_color, **kw))


def primary_button(parent, text, command=None, **kw):
    return _button(parent, text, command, T.PRIMARY, T.PRIMARY_HOVER, T.ON_PRIMARY, **kw)


def secondary_button(parent, text, command=None, **kw):
    return _button(parent, text, command, T.SECONDARY, T.SECONDARY_HOVER,
                   T.ON_SECONDARY, **kw)


def danger_button(parent, text, command=None, **kw):
    return _button(parent, text, command, T.DANGER, T.DANGER_HOVER, T.ON_DANGER, **kw)


def accent_button(parent, text, command=None, **kw):
    return _button(parent, text, command, T.ACCENT, T.ACCENT_HOVER, T.BG, **kw)


def ghost_button(parent, text, command=None, **kw):
    """Borderless text button — used for tertiary links."""
    kw.setdefault("height", 28)
    kw.setdefault("font", T.font(T.S_BODY))
    kw.setdefault("anchor", "center")
    kw.setdefault("text_color", T.TEXT_SECONDARY)
    return keyboard.focusable(ctk.CTkButton(
        parent, text=text, command=command, fg_color="transparent",
        hover_color=T.CARD_HOVER, corner_radius=T.R_BTN, **kw))


def icon_button(parent, icon_name, command=None, size=34, icon_px=18,
                active=False, tint=None, tooltip=None, tab=True):
    """Square icon button. `active` gives it the primary fill (view toggles).
    `tab=False` leaves it out of the Tab order."""
    img = icons.load_tinted(icon_name, icon_px,
                            tint or (T.ON_PRIMARY if active else T.TEXT_SECONDARY))
    btn = ctk.CTkButton(
        parent, text="", image=img, width=size, height=size,
        corner_radius=T.R_BTN,
        fg_color=T.PRIMARY if active else "transparent",
        hover_color=T.PRIMARY_HOVER if active else T.CARD_HOVER,
        command=command)
    if tooltip:
        attach_tooltip(btn, tooltip)
    if tab:
        keyboard.focusable(btn)
    return btn


# --------------------------------------------------------------------------
# Tooltips (the toolbar is icon-only, so the icons need names)
# --------------------------------------------------------------------------
def attach_tooltip(widget, text):
    """`text` may be a callable, for widgets that outlive a language change."""
    state = {"win": None, "after": None}

    def show():
        state["after"] = None
        if not widget.winfo_exists():
            return
        # Only while the pointer is really on it: the dashboard is kept under
        # the other screens, and a tip must not pop up over one of those.
        try:
            under = widget.winfo_containing(*widget.winfo_pointerxy())
        except Exception:
            under = None
        if under is None or not (under is widget or
                                 str(under).startswith(str(widget) + ".")):
            return
        win = ctk.CTkToplevel(widget)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(fg_color=T.BORDER_STRONG)
        ctk.CTkLabel(win, text=text() if callable(text) else text,
                     font=T.font(T.S_SMALL), text_color=T.TEXT,
                     fg_color=T.CARD, corner_radius=6,
                     padx=8, pady=4).pack(padx=1, pady=1)
        win.update_idletasks()
        x = widget.winfo_rootx() + widget.winfo_width() // 2 - win.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        win.geometry("+%d+%d" % (x, y))
        state["win"] = win

    def enter(_e=None):
        state["after"] = widget.after(500, show)

    def leave(_e=None):
        if state["after"] is not None:
            try:
                widget.after_cancel(state["after"])
            except Exception:
                pass
            state["after"] = None
        if state["win"] is not None:
            try:
                state["win"].destroy()
            except Exception:
                pass
            state["win"] = None

    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", leave, add="+")
    widget.bind("<Destroy>", leave, add="+")


# --------------------------------------------------------------------------
# Page scaffolding
# --------------------------------------------------------------------------
class AppBar(ctk.CTkFrame):
    """The top bar. Built once and kept for the life of the window: each
    screen only says which parts it wants, so moving between screens doesn't
    pay for a fresh dropdown and icon buttons every time."""

    def __init__(self, app):
        super().__init__(app.container, height=T.H_BAR, fg_color=T.BG_BAR,
                         corner_radius=0)
        self.pack_propagate(False)
        self._app = app
        self._back_cmd = None
        self._slot_builder = None

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=(10, 0))
        self._back = ctk.CTkButton(
            left, text="←", width=34, height=34, corner_radius=T.R_BTN,
            font=T.font(17), fg_color="transparent",
            text_color=T.TEXT_SECONDARY, hover_color=T.CARD_HOVER,
            command=lambda: self._back_cmd is not None and self._back_cmd())
        keyboard.focusable(self._back)
        # Screen-specific controls (the dashboard's view toggles).
        self._slot = ctk.CTkFrame(left, fg_color="transparent")

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=(0, 10))
        self._lang = ctk.CTkOptionMenu(
            right, values=app.lang_manager.get_supported_languages(),
            command=app.change_language, width=68, height=30,
            font=T.font(T.S_LABEL), dropdown_font=T.font(T.S_LABEL),
            fg_color=T.SECONDARY, button_color=T.SECONDARY,
            button_hover_color=T.SECONDARY_HOVER)
        keyboard.focusable(self._lang)
        self._lang.pack(side="right", padx=(6, 0))

        # The vault-level destinations, which only exist while unlocked.
        self._nav = ctk.CTkFrame(right, fg_color="transparent")
        for icon, cmd, key in (
                ("settings.png", app.show_extension_screen, "extension.title"),
                ("file-backup.png", app.show_backup_screen, "backup.title"),
                ("passkey.png", app.show_change_master_screen, "changepw.title"),
                ("phone.png", app.show_phone_screen, "phone.title"),
        ):
            icon_button(self._nav, icon, cmd,
                        tooltip=lambda k=key: app.t(k)).pack(side="right", padx=2)

    def show(self, back=None, left_builder=None, show_nav=False):
        self._back_cmd = back
        self._back.pack_forget()
        self._slot.pack_forget()
        if back is not None:
            self._back.pack(side="left")
        if left_builder is not None:
            if left_builder != self._slot_builder:
                for widget in self._slot.winfo_children():
                    widget.destroy()
                left_builder(self._slot)
                self._slot_builder = left_builder
            self._slot.pack(side="left")
        if show_nav:
            self._nav.pack(side="right")
        else:
            self._nav.pack_forget()
        self._lang.set(self._app.current_lang)


def app_bar(app, back=None, left_builder=None, show_nav=False):
    """Set up the persistent top bar for the screen being shown.

    `back` is a callback for the ← button; `left_builder(frame)` can add
    controls on the left instead (the dashboard's view toggles). `show_nav`
    adds the vault-level destinations, which only exist while unlocked.
    """
    app.app_bar.show(back=back, left_builder=left_builder, show_nav=show_nav)
    return app.app_bar


def page(app, scroll=False, padx=None):
    """The content area under the app bar."""
    pad = T.PAD_SCREEN if padx is None else padx
    if scroll:
        frame = ctk.CTkScrollableFrame(app.screen, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=pad - 8, pady=(T.GAP_L, 0))
        return frame
    frame = ctk.CTkFrame(app.screen, fg_color="transparent")
    frame.pack(fill="both", expand=True, padx=pad, pady=(T.GAP_L, 0))
    return frame


def footer(app):
    """The sticky action bar at the bottom of the window."""
    bar = ctk.CTkFrame(app.screen, fg_color=T.BG_BAR, corner_radius=0)
    bar.pack(fill="x", side="bottom")
    inner = ctk.CTkFrame(bar, fg_color="transparent")
    inner.pack(fill="x", padx=T.PAD_SCREEN, pady=T.GAP)
    return inner


def _label(parent, text, size, weight, color, **kw):
    kw.setdefault("font", T.font(size, weight))
    kw.setdefault("text_color", color)
    return ctk.CTkLabel(parent, text=text, **kw)


def title(parent, text, **kw):
    return _label(parent, text, T.S_TITLE, "bold", T.TEXT, **kw)


def heading(parent, text, **kw):
    return _label(parent, text, T.S_HEADING, "bold", T.TEXT, **kw)


def field_label(parent, text, **kw):
    kw.setdefault("anchor", "w")
    return _label(parent, text, T.S_LABEL, "normal", T.TEXT_SECONDARY, **kw)


def hint(parent, text, **kw):
    kw.setdefault("wraplength", 460)
    kw.setdefault("justify", "left")
    kw.setdefault("anchor", "w")
    return _label(parent, text, T.S_SMALL, "normal", T.TEXT_MUTED, **kw)


def card(parent, **kw):
    kw.setdefault("corner_radius", T.R_CARD)
    return ctk.CTkFrame(parent, fg_color=T.CARD, border_width=T.BORDER_W,
                        border_color=T.BORDER, **kw)


def divider(parent):
    return ctk.CTkFrame(parent, height=1, fg_color=T.BORDER, corner_radius=0)


# --------------------------------------------------------------------------
# Fields
# --------------------------------------------------------------------------
def text_field(parent, placeholder="", value="", readonly=False, mono=False, **kw):
    kw.setdefault("height", T.H_INPUT)
    entry = ctk.CTkEntry(parent, placeholder_text=placeholder,
                         font=T.mono() if mono else T.font(), **kw)
    if value:
        entry.insert(0, value)
    if readonly:
        entry.configure(state="readonly")
    else:
        _focus_ring(entry)
    return entry


def _focus_ring(entry):
    entry.bind("<FocusIn>", lambda _e: entry.winfo_exists() and
               entry.configure(border_color=T.PRIMARY, fg_color=T.INPUT_BG_FOCUS), add="+")
    entry.bind("<FocusOut>", lambda _e: entry.winfo_exists() and
               entry.configure(border_color=T.BORDER, fg_color=T.INPUT_BG), add="+")


SECRET_STANDIN = "•" * 8  # what a not-yet-decrypted secret shows as


def secret_field(parent, value="", placeholder="", readonly=False, mono=True,
                 revealed=False, reveal=None):
    """A masked entry with a reveal toggle. Returns (row, entry).

    Given `reveal` (a callable returning the stored secret), the field does
    not hold the secret at all until it is needed: it shows a stand-in, and
    `reveal()` — the decryption — runs only when the user reveals the field
    or, if it is editable, starts editing it. A read-only field drops the
    plaintext again as soon as it is masked.

    Extra methods on the entry: `conceal()` masks it; `reset_secret(has)`
    puts back the stand-in (or empties it when there is no stored secret);
    `set_secret(text)` fills in a new value; `secret_loaded()` says whether
    the field holds a real value (typed, generated or decrypted).
    """
    row = ctk.CTkFrame(parent, fg_color="transparent")
    entry = text_field(row, placeholder=placeholder, value=value,
                       readonly=readonly, mono=mono)
    entry.configure(show="" if revealed else "•")
    entry.pack(side="left", fill="x", expand=True)

    state = {"shown": revealed, "loaded": reveal is None}
    # Not a Tab stop, like the reveal button of a Windows password box.
    btn = icon_button(row, "eye.png" if not revealed else "eye-off.png",
                      size=T.H_INPUT, icon_px=17, tab=False)
    keyboard.mark_secret(entry)

    def load():
        if not state["loaded"]:
            set_text(entry, reveal())
            state["loaded"] = True

    def unload(has_secret=True):
        set_text(entry, SECRET_STANDIN if has_secret else "")
        state["loaded"] = not has_secret  # nothing stored: nothing to decrypt

    def show(shown):
        if shown and reveal is not None:
            load()
        state["shown"] = shown
        entry.configure(show="" if shown else "•")
        btn.configure(image=icons.load_tinted(
            "eye-off.png" if shown else "eye.png", 17, T.TEXT_SECONDARY))
        if not shown and readonly and reveal is not None:
            unload()  # nothing to edit here, so no reason to keep it

    def conceal():
        """Mask again — a kept screen must not open on a revealed secret."""
        if state["shown"]:
            show(False)

    def reset_secret(has_secret=True):
        conceal()
        if reveal is not None:
            unload(has_secret)
        else:
            set_text(entry, "")

    def set_secret(text):
        set_text(entry, text)
        state["loaded"] = True

    btn.configure(command=lambda: show(not state["shown"]),
                  fg_color=T.SECONDARY, hover_color=T.SECONDARY_HOVER)
    btn.pack(side="left", padx=(T.GAP_S, 0))

    def remask(_event=None):
        # CTkEntry turns masking off while its placeholder shows and restores
        # it on focus from a saved copy; don't trust that copy with a secret.
        # Runs after CTkEntry's own FocusIn handler (bound first).
        if not getattr(entry, "_placeholder_text_active", False):
            entry._entry.configure(show="" if state["shown"] else "•")

    entry.bind("<FocusIn>", remask, add="+")
    if reveal is not None:
        unload()
        if not readonly:
            # Decrypted when the user clicks in or starts editing, not when
            # Tab merely passes through on the way to the Save button.
            def load_to_edit(event):
                if state["loaded"] or not keyboard.is_edit(event):
                    return
                inner = entry._entry
                whole = (inner.selection_present() and inner.index("sel.first") == 0
                         and inner.index("sel.last") == len(inner.get()))
                load()
                if whole:  # the stand-in was selected: typing replaces it all
                    inner.selection_range(0, "end")
                    inner.icursor("end")

            entry.bind("<Button-1>", lambda _e: load(), add="+")
            entry.bind("<KeyPress>", load_to_edit, add="+")
    entry.conceal = conceal
    entry.reset_secret = reset_secret
    entry.set_secret = set_secret
    entry.secret_loaded = lambda: state["loaded"]
    return row, entry


def set_text(entry, value):
    """Replace an entry's text, read-only ones included (a kept screen
    refills its fields on every visit)."""
    if not value and getattr(entry, "_placeholder_text_active", False):
        # Already empty, showing its placeholder. Re-activating the placeholder
        # would make CTkEntry save its current, placeholder-time `show` ("") over
        # the real one — which is how a password field ended up unmasked.
        return
    readonly = entry.cget("state") == "readonly"
    if readonly:
        entry.configure(state="normal")
    keyboard.forget_history(entry)  # Ctrl+Z mustn't bring back what was here
    entry.delete(0, "end")
    if value:
        entry.insert(0, value)
    else:
        # CTkEntry believes it has focus until its first FocusOut, and only
        # brings the placeholder back when it thinks it doesn't — so an emptied
        # field would show nothing at all. Tell it, unless it really has focus.
        try:
            focused = entry.focus_get()
        except Exception:
            focused = None
        if focused is not getattr(entry, "_entry", None) and hasattr(entry, "_entry_focus_out"):
            entry._entry_focus_out()
    if readonly:
        entry.configure(state="readonly")


def copy_button(app, parent, get_text, style="secondary", **kw):
    """COPY button that flashes, then counts the clipboard down to its wipe."""
    label = app.t("generator.copy")
    base_fg, base_hover, base_text = {
        "primary": (T.PRIMARY, T.PRIMARY_HOVER, T.ON_PRIMARY),
    }.get(style, (T.SECONDARY, T.SECONDARY_HOVER, T.ON_SECONDARY))
    kw.setdefault("width", 76)
    kw.setdefault("height", T.H_INPUT)
    kw.setdefault("font", T.font(T.S_LABEL, "bold"))
    btn = _button(parent, label, None, base_fg, base_hover, base_text, **kw)
    state = {"job": None}

    def restore():
        state["job"] = None
        if btn.winfo_exists():
            btn.configure(text=label, fg_color=base_fg, text_color=base_text)

    def countdown(left):
        if not btn.winfo_exists():
            return
        if left <= 0:
            restore()
            return
        btn.configure(text="%ds" % left, fg_color=base_fg, text_color=T.TEXT_MUTED)
        state["job"] = btn.after(1000, lambda: countdown(left - 1))

    def do_copy():
        if state["job"] is not None:
            try:
                btn.after_cancel(state["job"])
            except Exception:
                pass
        app.copy_to_clipboard(get_text())
        btn.configure(text=app.t("generator.copied"), fg_color=T.POSITIVE,
                      text_color=T.BG)
        seconds = max(int(app.clipboard_clear_ms / 1000), 1)
        state["job"] = btn.after(1200, lambda: countdown(seconds))

    btn.configure(command=do_copy)
    attach_tooltip(btn, app.t("details.copy_hint", n=int(app.clipboard_clear_ms / 1000)))
    return btn


# --------------------------------------------------------------------------
# Strength meter
# --------------------------------------------------------------------------
class StrengthMeter(ctk.CTkFrame):
    """Four segments that fill up with the score, plus an optional caption."""

    def __init__(self, parent, caption=True, segments=4, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self.bars = []
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        for i in range(segments):
            # width=1 matters: a CTkFrame defaults to 200px, which would make
            # pack hand the first segments all the space and clip the rest.
            seg = ctk.CTkFrame(row, width=1, height=5, corner_radius=3,
                               fg_color=T.TRACK)
            seg.pack(side="left", fill="x", expand=True,
                     padx=(0 if i == 0 else 4, 0))
            self.bars.append(seg)
        self.caption = None
        if caption:
            self.caption = ctk.CTkLabel(self, text="", font=T.font(T.S_SMALL),
                                        text_color=T.TEXT_MUTED, anchor="w")
            self.caption.pack(anchor="w", pady=(5, 0))

    def reset(self, text=""):
        """Empty track with a neutral caption (nothing typed yet)."""
        for seg in self.bars:
            seg.configure(fg_color=T.TRACK)
        if self.caption is not None:
            self.caption.configure(text=text, text_color=T.TEXT_MUTED)

    def set(self, score, text=""):
        """score: 0-4. 0 renders as an empty track."""
        color = T.STRENGTH_COLORS[max(0, min(score, 4))]
        filled = max(0, min(score, len(self.bars)))
        for i, seg in enumerate(self.bars):
            seg.configure(fg_color=color if i < filled else T.TRACK)
        if self.caption is not None:
            self.caption.configure(text=text, text_color=color if text else T.TEXT_MUTED)


# --------------------------------------------------------------------------
# Status line
# --------------------------------------------------------------------------
class StatusLine(ctk.CTkLabel):
    """A single line that shows neutral / positive / negative feedback."""

    def __init__(self, parent, **kw):
        kw.setdefault("font", T.font(T.S_LABEL))
        kw.setdefault("wraplength", 400)
        kw.setdefault("justify", "left")
        super().__init__(parent, text="", text_color=T.TEXT_MUTED, **kw)
        self._slot = None

    def pack_after(self, widget, **opts):
        """Take no room while empty, and appear right after `widget` when
        there is something to say — for forms where a blank line would leave
        a hole."""
        self._slot = (widget, opts)
        if self.cget("text"):
            self.pack(after=widget, **opts)

    def show(self, text, kind="muted"):
        self.configure(text=text, text_color={
            "positive": T.POSITIVE, "negative": T.NEGATIVE,
            "warning": T.WARNING, "muted": T.TEXT_MUTED,
        }.get(kind, T.TEXT_MUTED))
        if self._slot is not None and self.winfo_manager() != "pack":
            widget, opts = self._slot
            self.pack(after=widget, **opts)

    def clear(self):
        self.configure(text="")
        if self._slot is not None:
            self.pack_forget()


def status_dot(parent, text, on):
    """'● running' / '○ stopped' style indicator. `row.set(text, on)` updates it."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    dot = ctk.CTkLabel(row, text="", font=T.font(T.S_BODY), width=14)
    dot.pack(side="left")
    label = ctk.CTkLabel(row, text="", font=T.font(T.S_LABEL))
    label.pack(side="left", padx=(4, 0))

    def set_state(new_text, new_on):
        color = T.POSITIVE if new_on else T.TEXT_MUTED
        dot.configure(text="●" if new_on else "○", text_color=color)
        label.configure(text=new_text.lstrip("●○ "), text_color=color)

    set_state(text, on)
    row.set = set_state
    return row


def repack(shown, wanted, **pack_opts):
    """Make `wanted` (widgets of one parent) exactly what is packed, in that
    order, touching only what is out of place. Re-showing a hidden widget is
    the expensive part on Windows (it re-shows everything on it); moving one
    that is already showing is cheap. `shown` is what the last call returned."""
    keep = set(wanted)
    for widget in shown:
        if widget not in keep:
            widget.pack_forget()
    order = [w for w in shown if w in keep]  # the pack order right now
    for i, widget in enumerate(wanted):
        if i < len(order) and order[i] is widget:
            continue
        if widget in order:
            order.remove(widget)
        opts = dict(pack_opts)
        if i < len(order):
            opts["before"] = order[i]
        elif order:
            opts["after"] = order[-1]
        widget.pack(**opts)
        order.insert(i, widget)
    return list(wanted)


# --------------------------------------------------------------------------
# In-app modal (replaces the Windows message boxes)
# --------------------------------------------------------------------------
def modal(app, title_text, message, buttons, icon_color=None):
    """Covers the window with a centred dialog.

    `buttons` is a list of (label, style, callback); style is one of
    "primary", "danger", "secondary". The modal closes before the callback
    runs. Esc triggers the last button (the cancel slot by convention).
    """
    overlay = ctk.CTkFrame(app.container, fg_color=T.BG, corner_radius=0)
    overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
    overlay.lift()
    overlay._sv_modal = True  # Tab and Enter stay inside it
    try:
        previous = app.focus_get()
    except Exception:
        previous = None

    panel = ctk.CTkFrame(overlay, fg_color=T.CARD, corner_radius=T.R_CARD,
                         border_width=T.BORDER_W, border_color=T.BORDER_STRONG)
    panel.place(relx=0.5, rely=0.5, anchor="center")

    body = ctk.CTkFrame(panel, fg_color="transparent")
    body.pack(padx=T.GAP_L + 4, pady=T.GAP_L)

    heading(body, title_text, text_color=icon_color or T.TEXT).pack(anchor="w")
    ctk.CTkLabel(body, text=message, font=T.font(T.S_BODY),
                 text_color=T.TEXT_SECONDARY, wraplength=320,
                 justify="left").pack(anchor="w", pady=(T.GAP_S, T.GAP_L))

    row = ctk.CTkFrame(body, fg_color="transparent")
    row.pack(fill="x")

    def close_then(callback):
        def run():
            if overlay.winfo_exists():
                overlay.destroy()
            app.unbind("<Escape>")
            if previous is not None and previous.winfo_exists():
                previous.focus_set()
            if callback is not None:
                callback()
        return run

    maker = {"primary": primary_button, "danger": danger_button,
             "secondary": secondary_button}
    made = []
    for label, style, callback in buttons:
        btn = maker.get(style, secondary_button)(row, label, close_then(callback), width=96)
        btn.pack(side="right", padx=(T.GAP_S, 0))
        made.append((btn, style))

    if buttons:
        app.bind("<Escape>", lambda _e: close_then(buttons[-1][2])())
        # Enter takes the first button, unless that one destroys something:
        # then it takes the cancel slot, so a stray Enter can't delete.
        default = made[-1][0] if made[0][1] == "danger" else made[0][0]
        keyboard.set_default(overlay, default)
        default._canvas.focus_set()
    return overlay


def default_button(app, button):
    """Make `button` what Enter presses on the screen being built."""
    keyboard.set_default(app.screen, button)
    return button


def confirm(app, title_text, message, on_yes, yes_label=None, no_label=None,
            danger=True):
    modal(app, title_text, message, [
        (yes_label or app.t("modal.confirm"), "danger" if danger else "primary", on_yes),
        (no_label or app.t("modal.cancel"), "secondary", None),
    ], icon_color=T.DANGER if danger else T.PRIMARY)


def alert(app, title_text, message, kind="primary"):
    modal(app, title_text, message, [(app.t("modal.ok"), "primary", None)],
          icon_color={"warning": T.WARNING, "negative": T.DANGER}.get(kind, T.PRIMARY))


def idle_banner(app, seconds, on_stay):
    """Floating countdown shown just before the vault auto-locks."""
    frame = ctk.CTkFrame(app.container, fg_color=T.CARD, corner_radius=T.R_CARD,
                         border_width=T.BORDER_W, border_color=T.WARNING)
    frame.place(relx=0.5, rely=0.0, anchor="n", y=T.H_BAR + 10)
    frame.lift()

    inner = ctk.CTkFrame(frame, fg_color="transparent")
    inner.pack(padx=T.PAD_CARD, pady=T.GAP)

    label = ctk.CTkLabel(inner, text="", font=T.font(T.S_LABEL),
                         text_color=T.TEXT_SECONDARY)
    label.pack(side="left", padx=(0, T.GAP))
    secondary_button(inner, app.t("security.idle_stay"), on_stay,
                     height=30, width=110,
                     font=T.font(T.S_LABEL, "bold")).pack(side="left")

    def tick(left):
        if not frame.winfo_exists():
            return
        label.configure(text=app.t("security.idle_msg", n=max(left, 0)))
        if left > 0:
            frame.after(1000, lambda: tick(left - 1))

    tick(seconds)
    return frame
