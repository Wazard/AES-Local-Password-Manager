"""Change the master password (re-keys the vault to a new Argon2id key)."""
import customtkinter as ctk

from UI.theme import FONT_FAMILY, COLOR_SUCCESS, COLOR_SUCCESS_HOVER, COLOR_DANGER, COLOR_MUTED
from UI.components import back_button


class ChangeMasterMixin:
    def show_change_master_screen(self):
        self.current_view = "changepw"
        self.clear_screen()
        back_button(self)
        ctk.CTkLabel(self.container, text=self.t("changepw.title"),
                     font=(FONT_FAMILY, 22, "bold")).pack(pady=(0, 16))

        form = ctk.CTkFrame(self.container, fg_color="transparent")
        form.pack(padx=40, fill="x")

        def field(label_key):
            ctk.CTkLabel(form, text=self.t(label_key), font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
            e = ctk.CTkEntry(form, show="*", height=38)
            e.pack(fill="x", pady=(2, 14))
            return e

        current = field("changepw.current")
        new = field("changepw.new")
        confirm = field("changepw.confirm")

        status = ctk.CTkLabel(self.container, text="", text_color=COLOR_DANGER,
                              wraplength=400, justify="left")
        status.pack(pady=(0, 4))

        def submit():
            if new.get() != confirm.get():
                status.configure(text=self.t("changepw.mismatch"), text_color=COLOR_DANGER)
                return
            result = self.change_master(current.get(), new.get())
            if result == "wrong_current":
                status.configure(text=self.t("changepw.wrong"), text_color=COLOR_DANGER)
            elif result == "weak":
                status.configure(text=self.t("auth.weak"), text_color=COLOR_DANGER)
            elif result == "save_failed":
                status.configure(text="Save failed.", text_color=COLOR_DANGER)
            elif result == "ok":
                status.configure(text=self.t("changepw.success"), text_color=COLOR_SUCCESS)
                self.after(900, self.show_dashboard)

        ctk.CTkButton(self.container, text=self.t("changepw.save"), fg_color=COLOR_SUCCESS,
                      hover_color=COLOR_SUCCESS_HOVER, height=40, width=220,
                      command=submit).pack(pady=24)
