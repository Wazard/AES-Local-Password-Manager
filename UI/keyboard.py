"""Windows keyboard conventions for the whole window.

Tk's entry already handles Ctrl+A, the clipboard, Home/End and
Shift-selection. This adds what it lacks:

* Ctrl+Backspace / Ctrl+Delete erase a word; Ctrl+Z / Ctrl+Y undo and redo.
* Ctrl+Left/Right (and Shift to select) use Windows' word boundaries, and
  in a masked field jump to the start or end, like a Windows password box.
  Stepping word by word would give away where the spaces are.
* Tab / Shift+Tab reach buttons, checkboxes, menus and sliders, not just
  text fields, and stay on the screen being shown (the dashboard is kept
  mapped under the others). Space or Enter uses the control that has focus.
* Enter anywhere else runs the screen's default action (`set_default`).
"""
import tkinter as tk

import customtkinter as ctk

from UI import theme as T

UNDO_LIMIT = 100


# --------------------------------------------------------------------------
# Text fields
# --------------------------------------------------------------------------
def _is_word(ch):
    return ch.isalnum() or ch == "_"


def _word_start(text, i):
    """Where Ctrl+Left lands: back over spaces, then over one run of letters
    or of punctuation, so "name@mail.com" goes in steps."""
    while i > 0 and text[i - 1].isspace():
        i -= 1
    if i > 0:
        word = _is_word(text[i - 1])
        while i > 0 and not text[i - 1].isspace() and _is_word(text[i - 1]) == word:
            i -= 1
    return i


def _next_word(text, i):
    """Where Ctrl+Right lands: past this run, then past the spaces after it."""
    n = len(text)
    if i < n and not text[i].isspace():
        word = _is_word(text[i])
        while i < n and not text[i].isspace() and _is_word(text[i]) == word:
            i += 1
    while i < n and text[i].isspace():
        i += 1
    return i


def _word_target(w, forward):
    text, i = w.get(), w.index("insert")
    if w.cget("show"):  # masked: one word, as far as anyone can tell
        return len(text) if forward else 0
    return _next_word(text, i) if forward else _word_start(text, i)


def _move_word(event, forward, select):
    w = event.widget
    pos = _word_target(w, forward)
    if select:
        w.tk.call("::tk::EntryKeySelect", w._w, pos)
    else:
        w.tk.call("::tk::EntrySetCursor", w._w, pos)
    return "break"


def _delete_word(event, forward):
    w = event.widget
    if w.cget("state") == "normal":
        if w.selection_present():
            w.delete("sel.first", "sel.last")
        else:
            i, j = w.index("insert"), _word_target(w, forward)
            if i != j:
                w.delete(min(i, j), max(i, j))
        w.tk.call("::tk::EntrySeeInsert", w._w)
    return "break"


class _History:
    __slots__ = ("states", "at", "typing")

    def __init__(self, text, cursor):
        self.states = [(text, cursor)]
        self.at = 0
        self.typing = False


_histories = {}  # tk.Entry -> _History


def _record(w):
    """Note the field's text if it changed. Runs after every key, so a run of
    typed characters becomes one undo step, as in Windows."""
    if w.cget("state") != "normal":
        return
    text, cursor = w.get(), w.index("insert")
    h = _histories.get(w)
    if h is None:
        _histories[w] = _History(text, cursor)
        return
    last = h.states[h.at][0]
    if text == last:
        return
    typed = (len(text) == len(last) + 1 and cursor > 0
             and text[:cursor - 1] + text[cursor:] == last
             and not text[cursor - 1].isspace())
    del h.states[h.at + 1:]
    if typed and h.typing and h.at > 0:
        h.states[h.at] = (text, cursor)
    else:
        h.states.append((text, cursor))
        h.at += 1
        if len(h.states) > UNDO_LIMIT:
            del h.states[0]
            h.at -= 1
    h.typing = typed


def _step(event, redo):
    w = event.widget
    if w.cget("state") != "normal":
        return "break"
    _record(w)  # a change whose key is still held down
    h = _histories.get(w)
    target = None if h is None else h.at + (1 if redo else -1)
    if target is not None and 0 <= target < len(h.states):
        h.at, h.typing = target, False
        text, cursor = h.states[target]
        w.delete(0, "end")
        w.insert(0, text)
        w.icursor(cursor)
        w.selection_clear()
        w.tk.call("::tk::EntrySeeInsert", w._w)
    return "break"


def _on_shift_z(event):
    # Ctrl+Shift+Z is redo; a bare Ctrl+Z with Caps Lock on arrives as "Z" too.
    return _step(event, redo=bool(event.state & 0x1))


def forget_history(entry):
    """Drop a field's undo steps: its text was replaced or wiped, and Ctrl+Z
    must not bring back a password that was cleared."""
    w = getattr(entry, "_entry", entry)
    _histories.pop(w, None)
    try:
        if w.focus_get() is w:
            _histories[w] = _History(w.get(), w.index("insert"))
    except Exception:
        pass


def _on_focus_out(event):
    # A secret's undo steps are secrets too: they go once the field is left.
    if getattr(event.widget, "_sv_secret", False):
        _histories.pop(event.widget, None)


def mark_secret(entry):
    entry._entry._sv_secret = True


def is_edit(event):
    """Would this key change a field's text? (Not Tab, arrows, Ctrl+C...)"""
    if event.keysym in ("BackSpace", "Delete"):
        return True
    if event.state & 0x4 and event.keysym.lower() in ("v", "x"):
        return True
    # Ctrl+letter gives a control character; AltGr+key a printable one.
    return bool(event.char) and event.char.isprintable()


# --------------------------------------------------------------------------
# Focusable controls
# --------------------------------------------------------------------------
def _ring(widget):
    """(show, hide) for the focus indicator of a CTk control."""
    def safe(fn):
        def run(_event=None):
            if widget.winfo_exists():
                fn()
        return run

    if isinstance(widget, ctk.CTkButton):
        saved = {}

        def show():
            saved.update(border_width=widget.cget("border_width"),
                         border_color=widget.cget("border_color"))
            widget.configure(border_width=2, border_color=T.TEXT)

        def hide():
            if saved:
                widget.configure(**saved)
                saved.clear()
        return safe(show), safe(hide)

    if isinstance(widget, (ctk.CTkCheckBox, ctk.CTkRadioButton)):
        saved = {}

        def show():
            font = widget.cget("font")
            saved.update(font=font, text_color=widget.cget("text_color"))
            if isinstance(font, tuple):
                widget.configure(font=font + ("underline",))
            widget.configure(text_color=T.TEXT)

        def hide():
            if saved:
                widget.configure(**saved)
                saved.clear()
        return safe(show), safe(hide)

    if isinstance(widget, ctk.CTkOptionMenu):
        saved = {}

        def show():
            saved.update(fg_color=widget.cget("fg_color"),
                         button_color=widget.cget("button_color"))
            hover = widget.cget("button_hover_color")
            widget.configure(fg_color=hover, button_color=hover)

        def hide():
            if saved:
                widget.configure(**saved)
                saved.clear()
        return safe(show), safe(hide)

    if isinstance(widget, ctk.CTkSlider):
        saved = {}

        def show():
            saved.update(button_color=widget.cget("button_color"))
            widget.configure(button_color=T.TEXT)

        def hide():
            if saved:
                widget.configure(**saved)
                saved.clear()
        return safe(show), safe(hide)

    return (lambda _e=None: None), (lambda _e=None: None)


def _enabled(widget):
    try:
        return widget.cget("state") != "disabled"
    except Exception:
        return True


def _slide(widget, delta=None, to=None):
    lo, hi = widget._from_, widget._to
    step = (hi - lo) / widget._number_of_steps if widget._number_of_steps else (hi - lo) / 20
    value = to if to is not None else widget.get() + delta * step
    value = min(max(value, min(lo, hi)), max(lo, hi))
    if value != widget.get():
        widget.set(value)
        if widget._command is not None:
            widget._command(widget.get())


def focusable(widget):
    """Put a CTk control in the Tab order, with a visible focus ring and the
    keys Windows uses on it. Returns the widget."""
    canvas = widget._canvas
    canvas._sv_owner = widget
    canvas.configure(takefocus=1)
    show, hide = _ring(widget)
    canvas.bind("<FocusIn>", show, add="+")
    canvas.bind("<FocusOut>", hide, add="+")

    def use(action):
        def run(_event=None):
            if _enabled(widget):
                action()
            return "break"
        return run

    if isinstance(widget, ctk.CTkButton):
        for key in ("<space>", "<Return>", "<KP_Enter>"):
            canvas.bind(key, use(widget.invoke))
    elif isinstance(widget, ctk.CTkCheckBox):
        canvas.bind("<space>", use(widget.toggle))
    elif isinstance(widget, ctk.CTkRadioButton):
        canvas.bind("<space>", use(widget.invoke))
    elif isinstance(widget, ctk.CTkOptionMenu):
        for key in ("<space>", "<Return>", "<KP_Enter>", "<Alt-Down>", "<F4>"):
            canvas.bind(key, use(widget._open_dropdown_menu))
    elif isinstance(widget, ctk.CTkSlider):
        for key, delta in (("<Left>", -1), ("<Down>", -1), ("<Right>", 1), ("<Up>", 1),
                           ("<Prior>", 4), ("<Next>", -4)):
            canvas.bind(key, use(lambda d=delta: _slide(widget, d)))
        canvas.bind("<Home>", use(lambda: _slide(widget, to=widget._from_)))
        canvas.bind("<End>", use(lambda: _slide(widget, to=widget._to)))
    return widget


def set_default(scope, action):
    """What Enter does on `scope` (a screen frame or a modal) when the focus
    isn't on a control of its own: a CTk button, or any callable."""
    scope._sv_default = action
    return action


# --------------------------------------------------------------------------
# Window-level wiring
# --------------------------------------------------------------------------
def _scope(app):
    """The frames the keyboard may reach: a modal alone, while one is up;
    otherwise the app bar, the screen on top and anything floating over it
    (the idle banner)."""
    extra = []
    for child in app.container.winfo_children():
        if child is app.app_bar or child is app.host:
            continue
        if getattr(child, "_sv_modal", False):
            return [child]
        extra.append(child)
    screen = getattr(app, "screen", None)
    return [app.app_bar] + ([screen] if screen is not None else []) + extra


def _inside(widget, roots):
    path = str(widget)
    return any(path == str(r) or path.startswith(str(r) + ".") for r in roots)


def _reachable(widget, roots):
    if not _inside(widget, roots):
        return False
    owner = getattr(widget, "_sv_owner", None)
    return _enabled(owner) if owner is not None else True


def _scroll_into_view(widget):
    """Scroll a scrollable page so the control Tab just reached is visible."""
    frame = widget.master
    while frame is not None and not isinstance(frame, ctk.CTkScrollableFrame):
        frame = frame.master
    if frame is None:
        return
    canvas = frame._parent_canvas
    total = frame.winfo_height()
    if total <= 0:
        return
    top = widget.winfo_rooty() - frame.winfo_rooty()
    bottom = top + widget.winfo_height()
    view_top, view_h = canvas.canvasy(0), canvas.winfo_height()
    margin = 8
    if top < view_top:
        canvas.yview_moveto(max(top - margin, 0) / total)
    elif bottom > view_top + view_h:
        canvas.yview_moveto(max(bottom + margin - view_h, 0) / total)


def traverse(app, forward=True):
    """Move the focus to the next (or previous) control on the screen shown."""
    roots = [r for r in _scope(app) if r.winfo_exists()]
    if not roots:
        return
    try:
        current = app.focus_get()
    except Exception:
        current = None
    start = current if current is not None and _inside(current, roots) else roots[0]
    step = "tk_focusNext" if forward else "tk_focusPrev"
    path = str(start)
    for _ in range(2000):  # the cycle covers the whole window at most once
        path = app.tk.call(step, path)
        if not path:
            return
        path = str(path)
        try:
            widget = app.nametowidget(path)
        except KeyError:
            continue
        if _reachable(widget, roots):
            # TabToWindow also selects an entry's text, as Windows does.
            app.tk.call("tk::TabToWindow", path)
            _scroll_into_view(widget)
            return
        if path == str(start):
            return


def run_default(app):
    roots = _scope(app)
    scope = roots[0] if getattr(roots[0], "_sv_modal", False) else getattr(app, "screen", None)
    action = getattr(scope, "_sv_default", None) if scope is not None else None
    if action is None:
        return
    if hasattr(action, "invoke"):  # a button
        if action.winfo_exists() and _enabled(action):
            action.invoke()
    else:
        action()


def install(app):
    """Wire the conventions above into the window. Call once."""
    entry_keys = {
        # Tk routes Ctrl(+Shift)+Left/Right through these virtual events, which
        # win over a plain key binding, so it's these that are replaced.
        "<<PrevWord>>": lambda e: _move_word(e, False, False),
        "<<NextWord>>": lambda e: _move_word(e, True, False),
        "<<SelectPrevWord>>": lambda e: _move_word(e, False, True),
        "<<SelectNextWord>>": lambda e: _move_word(e, True, True),
        "<Control-BackSpace>": lambda e: _delete_word(e, False),
        "<Control-Delete>": lambda e: _delete_word(e, True),
        "<Control-z>": lambda e: _step(e, redo=False),
        "<Control-Z>": _on_shift_z,
        "<Control-y>": lambda e: _step(e, redo=True),
        "<Control-Y>": lambda e: _step(e, redo=True),
    }
    for sequence, handler in entry_keys.items():
        app.bind_class("Entry", sequence, handler)
    app.bind_class("Entry", "<KeyRelease>", lambda e: _record(e.widget), add="+")
    app.bind_class("Entry", "<FocusOut>", _on_focus_out, add="+")
    app.bind_class("Entry", "<Destroy>", lambda e: _histories.pop(e.widget, None), add="+")

    def tab(forward):
        def run(_event):
            traverse(app, forward)
            return "break"
        return run

    app.bind("<Tab>", tab(True))
    app.bind("<Shift-Tab>", tab(False))

    def enter(_event):
        run_default(app)

    app.bind("<Return>", enter)
    app.bind("<KP_Enter>", enter)
