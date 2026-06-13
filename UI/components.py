"""Small reusable widgets shared across screens."""
import customtkinter as ctk

from UI.theme import (FONT_FAMILY, COLOR_BG_CARD, COLOR_CARD_HOVER,
                      COLOR_SUCCESS, COLOR_ACCENT)


def back_button(app, command=None):
    """A ← button packed top-left. Defaults to returning to the dashboard."""
    ctk.CTkButton(app.container, text="←", width=36, height=36,
                  fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                  font=(FONT_FAMILY, 16, "bold"),
                  command=command or app.show_dashboard).pack(anchor="nw", padx=14, pady=14)


def copy_button(app, parent, get_text):
    """A small COPY button that flashes 'COPIED!' briefly when clicked."""
    btn = ctk.CTkButton(parent, text=app.t("generator.copy"), width=80, height=32)

    def do_copy():
        app.copy_to_clipboard(get_text())
        btn.configure(text=app.t("generator.copied"), fg_color=COLOR_SUCCESS)
        app.after(1200, lambda: btn.winfo_exists() and
                  btn.configure(text=app.t("generator.copy"), fg_color=COLOR_ACCENT))

    btn.configure(command=do_copy)
    return btn
