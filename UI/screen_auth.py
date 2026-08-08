"""Login screen + authentication flow.

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
from UI.theme import (FONT_FAMILY, COLOR_SUCCESS, COLOR_SUCCESS_HOVER, COLOR_DANGER,
                      COLOR_BG_CARD, COLOR_CARD_HOVER, COLOR_MUTED)
from UI.tray import TRAY_AVAILABLE


class AuthMixin:
    def show_auth_screen(self):
        self.current_view = "auth"
        self.logged_in = False
        state = storage_handler.vault_state()
        if state != storage_handler.PRESENT and not self.creating_vault:
            self.show_no_vault_screen(state)
            return

        self.clear_screen()
        self._screen_chrome()
        creating = self.creating_vault

        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        frame.place(relx=0.5, rely=0.4, anchor="center")

        title = self.t("vault.create_title") if creating else self.t("auth.title")
        ctk.CTkLabel(frame, text=title, font=(FONT_FAMILY, 28, "bold")).pack(pady=20)
        self.pass_entry = ctk.CTkEntry(frame, placeholder_text=self.t("auth.placeholder"),
                                       show="*", width=260, height=40)
        self.pass_entry.pack(pady=10)
        self.pass_entry.bind("<Return>", lambda _e: self.attempt_login())

        self.status_label = ctk.CTkLabel(frame, text="")
        self.status_label.pack()
        ctk.CTkButton(frame, text=self.t("vault.create_btn") if creating else self.t("auth.login_btn"),
                      height=40, width=260,
                      fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                      command=self.attempt_login).pack(pady=(20, 8))

        if creating:
            ctk.CTkButton(frame, text=self.t("vault.back_btn"), height=36, width=260,
                          fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                          command=self.cancel_new_vault).pack(pady=(0, 16))
            return

        # Generate a password without logging in.
        ctk.CTkButton(frame, text=self.t("auth.generate_btn"), height=40, width=260,
                      command=self.show_gen_pass_screen).pack(pady=(0, 8))
        ctk.CTkLabel(frame, text="").pack(pady=(0, 8))

        # "Remind me" / keep running in the Windows tray on close.
        tray_chk = ctk.CTkCheckBox(frame, text=self.t("auth.tray"),
                                   variable=self.minimize_to_tray)
        tray_chk.pack(pady=(0, 4))
        if not TRAY_AVAILABLE:
            tray_chk.configure(state="disabled")

    def show_no_vault_screen(self, state):
        """No vault to log into: either it moved away or there has never been
        one. Both cases end here rather than at a login form, because a login
        form with nothing to open is what used to swallow relocated vaults."""
        from core import vault_location

        self.clear_screen()
        self._screen_chrome()

        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        frame.place(relx=0.5, rely=0.42, anchor="center")

        moved = state == storage_handler.MOVED
        ctk.CTkLabel(frame,
                     text=self.t("vault.missing_title") if moved else self.t("vault.new_title"),
                     font=(FONT_FAMILY, 26, "bold")).pack(pady=(0, 12))
        ctk.CTkLabel(frame,
                     text=self.t("vault.missing_body") if moved else self.t("vault.new_body"),
                     text_color=COLOR_MUTED, wraplength=340,
                     justify="left").pack(pady=(0, 10))
        if moved:
            ctk.CTkLabel(frame, text=storage_handler.vault_path(), text_color=COLOR_MUTED,
                         font=("Courier New", 11), wraplength=340,
                         justify="left").pack(pady=(0, 14))

        ctk.CTkButton(frame,
                      text=self.t("vault.locate_btn") if moved else self.t("auth.import_btn"),
                      height=40, width=300,
                      fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                      command=self.locate_vault).pack(pady=(0, 8))

        # A vault sitting at another place we know about (the data dir, the
        # OneDrive backup folder) — one click instead of a file dialog.
        suggestion = vault_location.found_elsewhere()
        if suggestion:
            ctk.CTkButton(frame, text=self.t("vault.use_found_btn"), height=36, width=300,
                          fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                          command=lambda: self.use_vault_at(suggestion)).pack(pady=(0, 4))
            ctk.CTkLabel(frame, text=suggestion, text_color=COLOR_MUTED,
                         font=("Courier New", 11), wraplength=300,
                         justify="left").pack(pady=(0, 8))

        ctk.CTkButton(frame, text=self.t("vault.create_btn"), height=36, width=300,
                      fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                      command=self.start_new_vault).pack(pady=(0, 8))
        ctk.CTkButton(frame, text=self.t("auth.generate_btn"), height=36, width=300,
                      fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                      command=self.show_gen_pass_screen).pack()

    def _screen_chrome(self):
        """The bits both pre-login screens carry: the language picker, and the
        version — so "did the update actually install?" has a visible answer."""
        # Dynamically fetch languages from the JSON file
        lang_menu = ctk.CTkOptionMenu(
            self.container,
            values=self.lang_manager.get_supported_languages(),
            command=self.change_language,
            width=70,
        )
        lang_menu.set(self.current_lang)
        lang_menu.place(relx=0.98, rely=0.02, anchor="ne")

        ctk.CTkLabel(self.container, text="v" + version.VERSION, text_color=COLOR_MUTED,
                     font=(FONT_FAMILY, 11)).place(relx=0.98, rely=0.98, anchor="se")

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
                self.status_label.configure(text=self.t("auth.weak"), text_color=COLOR_DANGER)
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
            self.status_label.configure(text=self.t("auth.correct"), text_color=COLOR_SUCCESS)
            self.after(500, self.show_dashboard)
        except Exception:
            self.status_label.configure(text=self.t("auth.wrong"), text_color=COLOR_DANGER)
        finally:
            pwd = None  # drop the plaintext master password
