"""Login screen + authentication flow."""
import json
import customtkinter as ctk

from core import encryption
from core import storage_handler
from core import storage_compression
from core import password_strength
from UI.theme import FONT_FAMILY, COLOR_SUCCESS, COLOR_SUCCESS_HOVER, COLOR_DANGER
from UI.tray import TRAY_AVAILABLE


class AuthMixin:
    def show_auth_screen(self):
        self.current_view = "auth"
        self.logged_in = False
        self.clear_screen()

        # Dynamically fetch languages from the JSON file
        available_langs = self.lang_manager.get_supported_languages()

        lang_menu = ctk.CTkOptionMenu(
            self.container,
            values=available_langs,
            command=self.change_language,
            width=70,
        )
        lang_menu.set(self.current_lang)
        lang_menu.place(relx=0.98, rely=0.02, anchor="ne")

        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        frame.place(relx=0.5, rely=0.4, anchor="center")

        ctk.CTkLabel(frame, text=self.t("auth.title"), font=(FONT_FAMILY, 28, "bold")).pack(pady=20)
        self.pass_entry = ctk.CTkEntry(frame, placeholder_text=self.t("auth.placeholder"),
                                       show="*", width=260, height=40)
        self.pass_entry.pack(pady=10)
        self.pass_entry.bind("<Return>", lambda _e: self.attempt_login())

        self.status_label = ctk.CTkLabel(frame, text="")
        self.status_label.pack()
        ctk.CTkButton(frame, text=self.t("auth.login_btn"), height=40, width=260,
                      fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                      command=self.attempt_login).pack(pady=(20, 8))

        # Generate a password without logging in.
        ctk.CTkButton(frame, text=self.t("auth.generate_btn"), height=40, width=260,
                      command=self.show_gen_pass_screen).pack(pady=(0, 16))

        # "Remind me" / keep running in the Windows tray on close.
        tray_chk = ctk.CTkCheckBox(frame, text=self.t("auth.tray"),
                                   variable=self.minimize_to_tray)
        tray_chk.pack(pady=(0, 4))
        if not TRAY_AVAILABLE:
            tray_chk.configure(state="disabled")

    def attempt_login(self):
        pwd = self.pass_entry.get()
        raw_blob = storage_handler.read_vault()
        if not raw_blob:
            # Creating a new vault — enforce a minimum master-password strength.
            if not password_strength.evaluate(pwd)["ok"]:
                self.status_label.configure(text=self.t("auth.weak"), text_color=COLOR_DANGER)
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
            self.status_label.configure(text=self.t("auth.correct"), text_color=COLOR_SUCCESS)
            self.after(500, self.show_dashboard)
        except Exception:
            self.status_label.configure(text=self.t("auth.wrong"), text_color=COLOR_DANGER)
        finally:
            pwd = None  # drop the plaintext master password
