"""Unlock screen + authentication flow.

Three states, decided by `storage_handler.vault_state()`:
  present — the normal login form
  moved   — the vault is gone from where it was; offer to find it again
  absent  — first run; offer to create a vault or open an existing one

Creating a vault is always a deliberate choice. Typing a master password into
the login form never creates one, so a vault that has merely been moved can't
be replaced by an empty one.
"""
import json
import customtkinter as ctk

from core import encryption
from core import storage_handler
from core import storage_compression
from core import password_strength
from core import version
from UI import components as ui
from UI import theme as T
from UI.tray import TRAY_AVAILABLE

FIELD_W = 330


class AuthMixin:
    def show_auth_screen(self):
        self.current_view = "auth"
        self.logged_in = False
        state = storage_handler.vault_state()
        if state != storage_handler.PRESENT and not self.creating_vault:
            self.show_no_vault_screen(state)
            return

        self.clear_screen()
        ui.app_bar(self)
        creating = self.creating_vault

        body = ctk.CTkFrame(self.screen, fg_color="transparent")
        body.pack(fill="both", expand=True)
        self._version_label()

        block = ctk.CTkFrame(body, fg_color="transparent")
        block.place(relx=0.5, rely=0.46, anchor="center")

        ui.title(block, self.t("vault.create_title") if creating else "Secure Vault",
                 font=T.font(26, "bold")).pack()
        ctk.CTkLabel(
            block,
            text=self.t("auth.create_subtitle") if creating else self.t("auth.subtitle"),
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
        if creating:
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
            block, self.t("vault.create_btn") if creating else self.t("auth.login_btn"),
            self.attempt_login, width=FIELD_W, height=42).pack(pady=(T.GAP, T.GAP_S))

        if creating:
            ui.ghost_button(block, self.t("vault.back_btn"), self.cancel_new_vault,
                            width=FIELD_W).pack()
            return

        ui.secondary_button(block, self.t("auth.generate_btn"), self.show_gen_pass_screen,
                            width=FIELD_W, height=42).pack()

        tray_chk = ctk.CTkCheckBox(block, text=self.t("auth.tray"),
                                   variable=self.minimize_to_tray,
                                   font=T.font(T.S_LABEL), checkbox_width=18,
                                   checkbox_height=18)
        tray_chk.pack(pady=(T.GAP_L, 0))
        if not TRAY_AVAILABLE:
            tray_chk.configure(state="disabled")

    def show_no_vault_screen(self, state):
        """No vault to log into: either it moved away or there has never been
        one. Both cases end here rather than at a login form, because a login
        form with nothing to open is what used to swallow relocated vaults."""
        from core import vault_location

        self.current_view = "auth"
        self.clear_screen()
        ui.app_bar(self)

        body = ctk.CTkFrame(self.screen, fg_color="transparent")
        body.pack(fill="both", expand=True)
        self._version_label()

        block = ctk.CTkFrame(body, fg_color="transparent")
        block.place(relx=0.5, rely=0.46, anchor="center")

        moved = state == storage_handler.MOVED
        ui.title(block,
                 self.t("vault.missing_title") if moved else self.t("vault.new_title"),
                 font=T.font(26, "bold")).pack()
        ctk.CTkLabel(
            block,
            text=self.t("vault.missing_body") if moved else self.t("vault.new_body"),
            font=T.font(T.S_LABEL), text_color=T.TEXT_MUTED,
            wraplength=FIELD_W, justify="center").pack(pady=(6, T.GAP))

        if moved:
            path_card = ui.card(block)
            path_card.pack(fill="x", pady=(0, T.GAP))
            ctk.CTkLabel(path_card, text=storage_handler.vault_path(),
                         font=T.mono(T.S_SMALL), text_color=T.TEXT_SECONDARY,
                         wraplength=FIELD_W - 2 * T.GAP, justify="left").pack(
                             padx=T.GAP, pady=T.GAP)

        locate = (self.t("vault.locate_btn") if moved else self.t("auth.import_btn"),
                  self.locate_vault)
        create = (self.t("vault.create_btn"), self.start_new_vault)
        # Moved: finding the vault again is what the user wants. First run:
        # there is nothing to find, so creating one leads.
        first, second = (locate, create) if moved else (create, locate)

        ui.primary_button(block, first[0], first[1],
                          width=FIELD_W, height=42).pack(pady=(0, T.GAP_S))
        ui.secondary_button(block, second[0], second[1],
                            width=FIELD_W, height=42).pack()

        # A vault sitting at another place we know about (the data dir, the
        # OneDrive backup folder) — one click instead of a file dialog.
        suggestion = vault_location.found_elsewhere()
        if suggestion:
            ui.secondary_button(block, self.t("vault.use_found_btn"),
                                lambda: self.use_vault_at(suggestion),
                                width=FIELD_W, height=42).pack(pady=(T.GAP_S, 0))
            ctk.CTkLabel(block, text=suggestion, font=T.mono(T.S_SMALL),
                         text_color=T.TEXT_MUTED, wraplength=FIELD_W,
                         justify="center").pack(pady=(4, 0))

        ui.ghost_button(block, self.t("auth.generate_btn"), self.show_gen_pass_screen,
                        width=FIELD_W).pack(pady=(T.GAP, 0))

    def _version_label(self):
        """Shown on both pre-login screens, so "did the update actually
        install?" has a visible answer. Lifted, because it is placed over the
        body frame rather than inside it."""
        label = ctk.CTkLabel(self.screen, text="v" + version.VERSION,
                             text_color=T.TEXT_MUTED, font=T.font(T.S_SMALL))
        label.place(relx=0.98, rely=0.98, anchor="se")
        label.lift()

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
            if not self.creating_vault:
                # The vault disappeared between screens — never quietly turn
                # that into a new, empty one.
                self.show_auth_screen()
                return
            # Creating a new vault — enforce a minimum master-password strength.
            if not password_strength.evaluate(pwd)["ok"]:
                self.status_label.show(self.t("auth.weak"), "negative")
                return
            self.vault_key, self.vault_salt, self.vault_params = encryption.derive_new(pwd)
            self.ingest_vault({})
            self.creating_vault = False
            self.save_vault()  # write it out, so the location is recorded now
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
