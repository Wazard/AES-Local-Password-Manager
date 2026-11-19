"""Unlock screen. Doubles as vault creation on first run."""
import json
import customtkinter as ctk

from core import encryption
from core import storage_handler
from core import storage_compression
from core import password_strength
from UI import components as ui
from UI import theme as T
from UI.tray import TRAY_AVAILABLE

FIELD_W = 330


class AuthMixin:
    def show_auth_screen(self):
        self.current_view = "auth"
        self.logged_in = False
        self.clear_screen()
        ui.app_bar(self)

        first_run = not storage_handler.read_vault()
        body = ctk.CTkFrame(self.container, fg_color="transparent")
        body.pack(fill="both", expand=True)

        block = ctk.CTkFrame(body, fg_color="transparent")
        block.place(relx=0.5, rely=0.46, anchor="center")

        ui.title(block, self.t("auth.create_title") if first_run else "Secure Vault",
                 font=T.font(26, "bold")).pack()
        ctk.CTkLabel(
            block,
            text=self.t("auth.create_subtitle") if first_run else self.t("auth.subtitle"),
            font=T.font(T.S_LABEL), text_color=T.TEXT_MUTED,
            wraplength=FIELD_W, justify="center").pack(pady=(6, T.GAP_L + 4))

        ui.field_label(block, self.t("auth.master_label"), width=FIELD_W).pack(anchor="w")
        row, self.pass_entry = ui.secret_field(
            block, placeholder=self.t("auth.placeholder"), mono=False)
        self.pass_entry.configure(width=FIELD_W - T.H_INPUT - T.GAP_S)
        row.pack(pady=(4, 0))
        self.pass_entry.bind("<Return>", lambda _e: self.attempt_login())
        self.pass_entry.focus_set()

        # Vault creation is the one place a strength meter belongs on this screen.
        self.auth_meter = None
        if first_run:
            self.auth_meter = ui.StrengthMeter(block, width=FIELD_W)
            self.auth_meter.pack(fill="x", pady=(8, 0))
            self.auth_meter.reset(self.t("auth.requirement"))
            self.pass_entry.bind("<KeyRelease>", self._on_master_typed, add="+")

        self.status_label = ui.StatusLine(block, wraplength=FIELD_W, justify="center")
        self.status_label.pack(pady=(8, 0))
        if self.lock_reason == "idle":
            self.status_label.show(self.t("auth.locked_idle"), "warning")
        elif self.lock_reason == "tamper":
            self.status_label.show(self.t("security.tamper_title"), "negative")
        self.lock_reason = None

        ui.primary_button(
            block, self.t("auth.create_btn") if first_run else self.t("auth.login_btn"),
            self.attempt_login, width=FIELD_W, height=42).pack(pady=(T.GAP, T.GAP_S))
        ui.secondary_button(block, self.t("auth.generate_btn"), self.show_gen_pass_screen,
                            width=FIELD_W, height=42).pack()

        if first_run:
            ui.ghost_button(block, self.t("auth.import_btn"),
                            self.import_existing_vault, width=FIELD_W).pack(pady=(T.GAP, 0))

        tray_chk = ctk.CTkCheckBox(block, text=self.t("auth.tray"),
                                   variable=self.minimize_to_tray,
                                   font=T.font(T.S_LABEL), checkbox_width=18,
                                   checkbox_height=18)
        tray_chk.pack(pady=(T.GAP_L, 0))
        if not TRAY_AVAILABLE:
            tray_chk.configure(state="disabled")

    def _on_master_typed(self, _event=None):
        if self.auth_meter is None or not self.auth_meter.winfo_exists():
            return
        pwd = self.pass_entry.get()
        if not pwd:
            self.auth_meter.reset(self.t("auth.requirement"))
            return
        result = password_strength.evaluate(pwd)
        self.auth_meter.set(result["score"], self.t("strength.%d" % result["score"]))

    def attempt_login(self):
        pwd = self.pass_entry.get()
        raw_blob = storage_handler.read_vault()
        if not raw_blob:
            # Creating a new vault — enforce a minimum master-password strength.
            if not password_strength.evaluate(pwd)["ok"]:
                self.status_label.show(self.t("auth.weak"), "negative")
                return
            self.vault_key, self.vault_salt, self.vault_params = encryption.derive_new(pwd)
            self.ingest_vault({})
            self.show_dashboard()
            return
        try:
            payload, key, salt, params = encryption.open_vault(raw_blob, pwd)
            decompressed = storage_compression.decompress_data(payload)
            self.ingest_vault(json.loads(decompressed))
            self.vault_key, self.vault_salt, self.vault_params = key, salt, params
            self.status_label.show(self.t("auth.correct"), "positive")
            self.after(400, self.show_dashboard)
        except Exception:
            self.status_label.show(self.t("auth.wrong"), "negative")
        finally:
            pwd = None  # drop the plaintext master password
