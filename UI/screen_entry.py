"""Add / modify form and the account detail view."""
import time
import customtkinter as ctk

from core import data_handler
from core import password_generator
from core import password_strength
from UI import components as ui
from UI import theme as T


def _format_date(stamp):
    try:
        return time.strftime("%d %b %Y", time.localtime(float(stamp)))
    except (TypeError, ValueError):
        return ""


class EntryMixin:
    # --- Add / Modify ---
    def show_add_screen(self, edit_service=None):
        self.active_service = edit_service
        self.current_view = "modify" if edit_service else "add"
        self.clear_screen()
        ui.app_bar(self, back=self.show_dashboard)

        body = ui.page(self, scroll=True)
        title = (self.t("forms.new_title") if not edit_service
                 else self.t("forms.modify_title", service=edit_service))
        ui.title(body, title).pack(anchor="w", padx=8)

        form = ctk.CTkFrame(body, fg_color="transparent")
        form.pack(fill="x", pady=(T.GAP_L, 0), padx=8)

        ui.field_label(form, self.t("forms.account")).pack(anchor="w")
        acc_entry = ui.text_field(form, placeholder=self.t("forms.account_ph"),
                                  value=edit_service or "")
        acc_entry.pack(fill="x", pady=(4, 0))
        if edit_service:
            # The account name is the vault key, so it can't be edited; make
            # that visible rather than leaving a field that silently ignores you.
            acc_entry.configure(state="disabled", fg_color=T.BG,
                                text_color=T.TEXT_MUTED)

        acc_status = ui.StatusLine(form)
        acc_status.pack(anchor="w", pady=(4, 0))

        ui.field_label(form, self.t("forms.username")).pack(anchor="w", pady=(T.GAP, 0))
        user_entry = ui.text_field(
            form, placeholder=self.t("forms.username_ph"),
            value=self.vault_data[edit_service]["user"] if edit_service else "")
        user_entry.pack(fill="x", pady=(4, 0))

        ui.field_label(form, self.t("forms.password")).pack(anchor="w", pady=(T.GAP, 0))
        pwd_row, pwd_entry = ui.secret_field(
            form, value=self.get_password(edit_service) if edit_service else "")
        pwd_row.pack(fill="x", pady=(4, 0))
        meter = ui.StrengthMeter(form, caption=False)
        meter.pack(fill="x", pady=(8, 0))

        def refresh_meter(_event=None):
            value = pwd_entry.get()
            meter.set(password_strength.evaluate(value)["score"] if value else 0)

        def fill_generated():
            pwd_entry.delete(0, "end")
            pwd_entry.insert(0, password_generator.generate_secure_password())
            refresh_meter()

        ui.secondary_button(pwd_row, self.t("forms.generate"), fill_generated,
                            width=92, height=T.H_INPUT,
                            font=T.font(T.S_LABEL, "bold")).pack(side="left",
                                                                 padx=(T.GAP_S, 0))
        pwd_entry.bind("<KeyRelease>", refresh_meter, add="+")
        refresh_meter()

        ui.field_label(form, self.t("forms.url")).pack(anchor="w", pady=(T.GAP_L, 0))
        url_entry = ui.text_field(
            form, placeholder="example.com",
            value=self.vault_data[edit_service].get("url", "") if edit_service else "")
        url_entry.pack(fill="x", pady=(4, 0))

        def save_action():
            service = edit_service or acc_entry.get().strip()
            if not service:
                acc_status.show(self.t("forms.required"), "negative")
                acc_entry.configure(border_color=T.NEGATIVE)
                acc_entry.focus_set()
                return
            if not edit_service and service in self.vault_data:
                acc_status.show(self.t("forms.duplicate"), "negative")
                acc_entry.configure(border_color=T.NEGATIVE)
                acc_entry.focus_set()
                return
            existing = self.vault_data.get(service, {})
            self.vault_data[service] = {
                "user": user_entry.get(),
                "pass": self.session.encrypt(pwd_entry.get()),
                "url": url_entry.get().strip(),
                "created": existing.get("created", time.time()),
                "favourite": existing.get("favourite", False),
            }
            if self.save_vault():
                self.show_dashboard()

        bar = ui.footer(self)
        ui.primary_button(bar, self.t("forms.save_account"), save_action,
                          height=42).pack(fill="x")

    # --- Account detail ---
    def show_details(self, service):
        self.active_service = service
        self.current_view = "details"
        self.clear_screen()
        ui.app_bar(self, back=self.show_dashboard, show_nav=True)

        body = ui.page(self, scroll=True)
        entry = self.vault_data[service]

        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x", padx=8)
        ui.title(head, service).pack(anchor="w")
        created = _format_date(entry.get("created"))
        if created:
            ctk.CTkLabel(head, text=self.t("details.created", date=created),
                         font=T.font(T.S_SMALL), text_color=T.TEXT_MUTED).pack(anchor="w",
                                                                               pady=(2, 0))

        fields = ctk.CTkFrame(body, fg_color="transparent")
        fields.pack(fill="x", pady=(T.GAP_L, 0), padx=8)

        # URL
        ui.field_label(fields, self.t("details.url_label")).pack(anchor="w")
        url = entry.get("url", "")
        url_row = ctk.CTkFrame(fields, fg_color="transparent")
        url_row.pack(fill="x", pady=(4, T.GAP))
        url_disp = ui.text_field(url_row, value=url or self.t("details.no_url"),
                                 readonly=True)
        if not url:
            url_disp.configure(text_color=T.TEXT_MUTED)
        url_disp.pack(side="left", fill="x", expand=True)

        # Username
        ui.field_label(fields, self.t("details.username_label").rstrip(":")).pack(anchor="w")
        user_row = ctk.CTkFrame(fields, fg_color="transparent")
        user_row.pack(fill="x", pady=(4, T.GAP))
        ui.text_field(user_row, value=entry["user"], readonly=True).pack(
            side="left", fill="x", expand=True)
        ui.copy_button(self, user_row, lambda: self.vault_data[service]["user"]).pack(
            side="left", padx=(T.GAP_S, 0))

        # Password
        ui.field_label(fields, self.t("details.password_label").rstrip(":")).pack(anchor="w")
        pass_row, _pass_entry = ui.secret_field(
            fields, value=self.get_password(service), readonly=True)
        pass_row.pack(fill="x", pady=(4, 0))
        ui.copy_button(self, pass_row, lambda: self.get_password(service)).pack(
            side="left", padx=(T.GAP_S, 0))

        def delete_action():
            ui.confirm(self, self.t("details.delete"),
                       self.t("details.delete_confirm", service=service),
                       do_delete, yes_label=self.t("modal.delete"))

        def do_delete():
            if data_handler.delete_entry(self.vault_data, service):
                self.save_vault()
                self.show_dashboard()

        bar = ui.footer(self)
        ui.primary_button(bar, self.t("details.modify"),
                          lambda: self.show_add_screen(service),
                          height=42).pack(side="left", fill="x", expand=True)
        ui.danger_button(bar, self.t("details.delete"), delete_action,
                         height=42, width=120).pack(side="left", padx=(T.GAP_S, 0))
