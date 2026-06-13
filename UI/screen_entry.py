"""Add / modify form and the account detail view."""
import time
import customtkinter as ctk
from tkinter import messagebox

from core import data_handler
from core import password_generator
from UI.theme import (FONT_FAMILY, COLOR_BG_CARD, COLOR_SUCCESS, COLOR_SUCCESS_HOVER,
                      COLOR_DANGER, COLOR_DANGER_HOVER)
from UI.components import back_button, copy_button


class EntryMixin:
    # --- Add / Modify ---
    def show_add_screen(self, edit_service=None):
        self.active_service = edit_service
        self.current_view = "modify" if edit_service else "add"
        self.clear_screen()
        title = (self.t("forms.new_title") if not edit_service
                 else self.t("forms.modify_title", service=edit_service))

        back_button(self)
        ctk.CTkLabel(self.container, text=title, font=(FONT_FAMILY, 22, "bold")).pack(pady=10)

        form = ctk.CTkFrame(self.container, fg_color="transparent")
        form.pack(pady=20, padx=40, fill="x")

        ctk.CTkLabel(form, text=self.t("forms.account"), font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
        acc_entry = ctk.CTkEntry(form, height=38)
        acc_entry.pack(fill="x", pady=(2, 15))
        if edit_service:
            acc_entry.insert(0, edit_service)
            acc_entry.configure(state="disabled")

        ctk.CTkLabel(form, text=self.t("forms.username"), font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
        user_entry = ctk.CTkEntry(form, height=38)
        user_entry.pack(fill="x", pady=(2, 15))
        if edit_service:
            user_entry.insert(0, self.vault_data[edit_service]['user'])

        ctk.CTkLabel(form, text=self.t("forms.password"), font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
        pwd_frame = ctk.CTkFrame(form, fg_color="transparent")
        pwd_frame.pack(fill="x", pady=(2, 0))
        pwd_entry = ctk.CTkEntry(pwd_frame, height=38)
        pwd_entry.pack(side="left", fill="x", expand=True)
        if edit_service:
            pwd_entry.insert(0, self.vault_data[edit_service]['pass'])

        ctk.CTkButton(pwd_frame, text=self.t("forms.generate"), width=90, height=38,
                      command=lambda: [pwd_entry.delete(0, 'end'),
                                       pwd_entry.insert(0, password_generator.generate_secure_password())]
                      ).pack(side="right", padx=(8, 0))

        def save_action():
            service = acc_entry.get().strip()
            if not service:
                return
            existing = self.vault_data.get(service, {})
            self.vault_data[service] = {
                "user": user_entry.get(),
                "pass": pwd_entry.get(),
                "created": existing.get("created", time.time()),
            }
            if self.save_vault():
                self.show_dashboard()

        ctk.CTkButton(self.container, text=self.t("forms.save"), fg_color=COLOR_SUCCESS,
                      hover_color=COLOR_SUCCESS_HOVER, height=40, width=200,
                      command=save_action).pack(pady=30)

    # --- Account detail ---
    def show_details(self, service):
        self.active_service = service
        self.current_view = "details"
        self.clear_screen()
        back_button(self)
        ctk.CTkLabel(self.container, text=service, font=(FONT_FAMILY, 24, "bold")).pack(pady=20)

        detail_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        detail_frame.pack(padx=40, fill="x")

        # Username row
        ctk.CTkLabel(detail_frame, text=self.t("details.username_label"),
                     font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
        user_row = ctk.CTkFrame(detail_frame, fg_color="transparent")
        user_row.pack(fill="x", pady=(2, 18))
        user_disp = ctk.CTkEntry(user_row, fg_color=COLOR_BG_CARD, border_width=0, height=38)
        user_disp.insert(0, self.vault_data[service]['user'])
        user_disp.configure(state="readonly")
        user_disp.pack(side="left", fill="x", expand=True)
        copy_button(self, user_row, lambda: self.vault_data[service]['user']).pack(side="right", padx=(8, 0))

        # Password row
        ctk.CTkLabel(detail_frame, text=self.t("details.password_label"),
                     font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
        pass_row = ctk.CTkFrame(detail_frame, fg_color="transparent")
        pass_row.pack(fill="x", pady=(2, 0))
        pass_disp = ctk.CTkEntry(pass_row, fg_color=COLOR_BG_CARD, border_width=0, height=38,
                                 font=("Courier New", 14))
        pass_disp.insert(0, self.vault_data[service]['pass'])
        pass_disp.configure(state="readonly")
        pass_disp.pack(side="left", fill="x", expand=True)
        copy_button(self, pass_row, lambda: self.vault_data[service]['pass']).pack(side="right", padx=(8, 0))

        btn_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=40)
        ctk.CTkButton(btn_frame, text=self.t("details.modify"), fg_color=COLOR_SUCCESS,
                      hover_color=COLOR_SUCCESS_HOVER,
                      command=lambda: self.show_add_screen(service)).pack(side="left", padx=10)

        def delete_action():
            if messagebox.askyesno("Confirm", self.t("details.delete_confirm", service=service)):
                if data_handler.delete_entry(self.vault_data, service):
                    self.save_vault()
                    self.show_dashboard()

        ctk.CTkButton(btn_frame, text=self.t("details.delete"), fg_color=COLOR_DANGER,
                      hover_color=COLOR_DANGER_HOVER, command=delete_action).pack(side="left", padx=10)
