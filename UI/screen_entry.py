"""Add / modify form and the account detail view.

Both are kept screens (see PasswordManagerGUI.open_screen): built once, then
filled in for whichever account is being shown. Neither holds a decrypted
password unless the user asks for it — revealing it, copying it or editing it —
and whatever was decrypted is wiped as soon as the user moves on.
"""
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
        ui.app_bar(self, back=self.show_dashboard)
        self.open_screen("form", self._build_form, refresh=self._fill_form,
                         leave=self._wipe_form)

    def _build_form(self):
        f = self._form = {}
        body = ui.page(self, scroll=True)
        f["title"] = ui.title(body, "")
        f["title"].pack(anchor="w", padx=8)

        form = ctk.CTkFrame(body, fg_color="transparent")
        form.pack(fill="x", pady=(T.GAP_L, 0), padx=8)

        ui.field_label(form, self.t("forms.account")).pack(anchor="w")
        f["acc"] = ui.text_field(form, placeholder=self.t("forms.account_ph"))
        f["acc"].pack(fill="x", pady=(4, 0))  # editable: the name can be corrected
        f["acc_error"] = False

        f["acc_status"] = ui.StatusLine(form)
        f["acc_status"].pack(anchor="w", pady=(4, 0))

        ui.field_label(form, self.t("forms.username")).pack(anchor="w", pady=(T.GAP, 0))
        f["user"] = ui.text_field(form, placeholder=self.t("forms.username_ph"))
        f["user"].pack(fill="x", pady=(4, 0))

        ui.field_label(form, self.t("forms.password")).pack(anchor="w", pady=(T.GAP, 0))
        # Decrypted only if the user reveals or edits it: changing just the
        # username never brings the password out of the session store.
        pwd_row, f["pwd"] = ui.secret_field(
            form, reveal=lambda: self.get_password(self.active_service))
        pwd_row.pack(fill="x", pady=(4, 0))
        f["meter"] = ui.StrengthMeter(form, caption=False)
        f["meter"].pack(fill="x", pady=(8, 0))

        def fill_generated():
            f["pwd"].set_secret(password_generator.generate_secure_password())
            self._refresh_form_meter()

        ui.secondary_button(pwd_row, self.t("forms.generate"), fill_generated,
                            width=92, height=T.H_INPUT,
                            font=T.font(T.S_LABEL, "bold")).pack(side="left",
                                                                 padx=(T.GAP_S, 0))
        f["pwd"].bind("<KeyRelease>", lambda _e: self._refresh_form_meter(), add="+")
        f["pwd"].bind("<FocusIn>", lambda _e: self._refresh_form_meter(), add="+")
        # A click is what decrypts the stored password (see secret_field); this
        # runs after that, so the meter scores it straight away.
        f["pwd"].bind("<Button-1>", lambda _e: self._refresh_form_meter(), add="+")

        ui.field_label(form, self.t("forms.url")).pack(anchor="w", pady=(T.GAP_L, 0))
        f["url"] = ui.text_field(form, placeholder="example.com")
        f["url"].pack(fill="x", pady=(4, 0))

        bar = ui.footer(self)
        ui.default_button(self, ui.primary_button(
            bar, self.t("forms.save_account"), self._save_form, height=42)).pack(fill="x")

    def _refresh_form_meter(self):
        pwd = self._form["pwd"]
        # An untouched stored password stays encrypted, so it gets no score.
        value = pwd.get() if pwd.secret_loaded() else ""
        self._form["meter"].set(password_strength.evaluate(value)["score"] if value else 0)

    def _fill_form(self):
        f = self._form
        service = self.active_service
        entry = self.vault_data.get(service, {}) if service else {}
        f["title"].configure(text=self.t("forms.modify_title", service=service)
                             if service else self.t("forms.new_title"))
        self._clear_form_error()
        ui.set_text(f["acc"], service or "")
        ui.set_text(f["user"], entry.get("user", ""))
        f["pwd"].reset_secret(has_secret=bool(service))
        ui.set_text(f["url"], entry.get("url", ""))
        self._refresh_form_meter()

    def _wipe_form(self):
        f = self._form
        f["pwd"].reset_secret(has_secret=False)
        for key in ("acc", "user", "url"):
            ui.set_text(f[key], "")
        self._refresh_form_meter()

    def _clear_form_error(self):
        f = self._form
        if f["acc_error"]:
            f["acc"].configure(border_color=T.BORDER)
            f["acc_status"].clear()
            f["acc_error"] = False

    def _form_error(self, key):
        f = self._form
        f["acc_status"].show(self.t(key), "negative")
        f["acc"].configure(border_color=T.NEGATIVE)
        f["acc_error"] = True
        f["acc"].focus_set()

    def _save_form(self):
        f = self._form
        edit_service = self.active_service
        service = f["acc"].get().strip()
        if not service:
            self._form_error("forms.required")
            return
        if service != edit_service and service in self.vault_data:
            self._form_error("forms.duplicate")
            return
        if edit_service and service != edit_service:
            # Renaming: keep the entry where it is in the vault instead of
            # dropping the old key and appending a new one.
            if not data_handler.rename_entry(self.vault_data, edit_service, service):
                ui.alert(self, self.t("forms.rename_failed_title"),
                         self.t("forms.rename_failed", service=service),
                         kind="negative")
                return
            self.active_service = service
        existing = self.vault_data.get(service, {})
        if f["pwd"].secret_loaded():
            token = self.session.encrypt(f["pwd"].get())
        else:  # never revealed or edited: keep it exactly as stored
            token = existing.get("pass") or self.session.encrypt("")
        self.vault_data[service] = {
            "user": f["user"].get(),
            "pass": token,
            "url": f["url"].get().strip(),
            "created": existing.get("created", time.time()),
            "favourite": existing.get("favourite", False),
        }
        if self.save_vault():
            self.show_dashboard()

    # --- Account detail ---
    def show_details(self, service):
        self.active_service = service
        self.current_view = "details"
        ui.app_bar(self, back=self.show_dashboard, show_nav=True)
        self.open_screen("details", self._build_details, refresh=self._fill_details,
                         leave=self._wipe_details)

    def _build_details(self):
        d = self._details = {}
        body = ui.page(self, scroll=True)

        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x", padx=8)
        d["title"] = ui.title(head, "")
        d["title"].pack(anchor="w")
        d["created"] = ctk.CTkLabel(head, text="", font=T.font(T.S_SMALL),
                                    text_color=T.TEXT_MUTED)

        fields = ctk.CTkFrame(body, fg_color="transparent")
        fields.pack(fill="x", pady=(T.GAP_L, 0), padx=8)

        # URL
        ui.field_label(fields, self.t("details.url_label")).pack(anchor="w")
        url_row = ctk.CTkFrame(fields, fg_color="transparent")
        url_row.pack(fill="x", pady=(4, T.GAP))
        d["url"] = ui.text_field(url_row, readonly=True)
        d["url"].pack(side="left", fill="x", expand=True)
        d["url_muted"] = False

        # Username
        ui.field_label(fields, self.t("details.username_label").rstrip(":")).pack(anchor="w")
        user_row = ctk.CTkFrame(fields, fg_color="transparent")
        user_row.pack(fill="x", pady=(4, T.GAP))
        d["user"] = ui.text_field(user_row, readonly=True)
        d["user"].pack(side="left", fill="x", expand=True)
        ui.copy_button(self, user_row,
                       lambda: self.vault_data.get(self.active_service, {}).get("user", "")
                       ).pack(side="left", padx=(T.GAP_S, 0))

        # Password
        ui.field_label(fields, self.t("details.password_label").rstrip(":")).pack(anchor="w")
        # Masked stand-in until the eye is clicked; copying decrypts on click.
        pass_row, d["pass"] = ui.secret_field(
            fields, readonly=True, reveal=lambda: self.get_password(self.active_service))
        pass_row.pack(fill="x", pady=(4, 0))
        ui.copy_button(self, pass_row, lambda: self.get_password(self.active_service)).pack(
            side="left", padx=(T.GAP_S, 0))

        bar = ui.footer(self)
        ui.primary_button(bar, self.t("details.modify"),
                          lambda: self.show_add_screen(self.active_service),
                          height=42).pack(side="left", fill="x", expand=True)
        ui.danger_button(bar, self.t("details.delete"), self._confirm_delete,
                         height=42, width=120).pack(side="left", padx=(T.GAP_S, 0))

    def _fill_details(self):
        d = self._details
        service = self.active_service
        entry = self.vault_data[service]
        d["title"].configure(text=service)
        created = _format_date(entry.get("created"))
        if created:
            d["created"].configure(text=self.t("details.created", date=created))
            d["created"].pack(anchor="w", pady=(2, 0))
        else:
            d["created"].pack_forget()

        url = entry.get("url", "")
        ui.set_text(d["url"], url or self.t("details.no_url"))
        if d["url_muted"] != (not url):
            d["url"].configure(text_color=T.TEXT if url else T.TEXT_MUTED)
            d["url_muted"] = not url
        ui.set_text(d["user"], entry.get("user", ""))
        d["pass"].reset_secret()

    def _wipe_details(self):
        d = self._details
        d["pass"].reset_secret()

    def _confirm_delete(self):
        service = self.active_service

        def do_delete():
            if data_handler.delete_entry(self.vault_data, service):
                self.save_vault()
                self.show_dashboard()

        ui.confirm(self, self.t("details.delete"),
                   self.t("details.delete_confirm", service=service),
                   do_delete, yes_label=self.t("modal.delete"))
